"""CLI-owned git sync for JSONL boards (bon-guritu).

Team boards are JSONL-in-repo, and eight laptops that sleep mid-thought
fork boards silently if humans must remember a sync discipline. So every
mutating verb owns its own sync: fetch, rebase, merge at item grain,
write, commit, push — inside the CLI, loud on real conflict, never force.

Engagement is conservative and self-gating:
- JSONL backend only (Dolt boards never come here).
- items.jsonl must already be git-TRACKED — a fresh `bon init` board, a
  scratch board, or a repo that gitignores .bon/ never syncs. Committing
  the board file is the deliberate adoption step.
- The current branch must have a configured upstream.
- `.bon/sync` containing `off` (or BON_SYNC=off in the environment)
  disables sync — the robot-owned-repo boundary (~/notes: write the
  tree, let notes-sync carry every git write).

Failure philosophy: a sync failure must never lose the save. Offline or
deferred states degrade to "write + commit locally, warn once, push on a
future verb".

Conflict semantics are two-tier, by WHERE the colliding edit lives:

- IN-SESSION (this verb's in-memory change vs origin): hard stop — the
  item-grain merge aborts BEFORE the local write, so neither side's edit
  is silently dropped (the resena lesson at git grain).
- WHILE-APART (an already-COMMITTED local edit vs origin — the offline
  backlog, a deferred verb's commit, the push-retry race): the load
  snapshot can't see it, and git's union merge quietly kept both lines
  until load-time dedup silently picked the newest (refuted live by the
  2026-08-30 essayeur, three reproductions). Blocking the rebase would
  strand a teammate in git surgery — the exact failure this module
  exists to kill — so instead every integration is followed by
  resolve_union_artifacts(): newest wins (matching what every reader
  already showed), every displaced version is PRESERVED in the committed
  .bon/sync-conflicts.jsonl sidecar, and the collision is named loudly.
  A standing warning fires on every verb while the sidecar is non-empty,
  so the clone whose edit was displaced hears about it too.

One known quiet edge remains: a cross-clone archive-vs-edit collision
(delete on one side, modify on the other) unions to "the edit survives"
with no duplicate line to detect — the item resurfaces rather than
vanishing, which is the safe direction, but no cue fires.
"""
import os
import subprocess
import sys
from pathlib import Path

# Board files a sync commit may carry. Relative to the .bon directory.
_BOARD_FILES = ("items.jsonl", "archive.jsonl", "README.md", ".gitattributes",
                "sync-conflicts.jsonl")

_FETCH_TIMEOUT = 8
_PUSH_TIMEOUT = 20
_LOCAL_TIMEOUT = 10

GITATTRIBUTES_CONTENT = (
    "# bon board files merge line-wise: concurrent edits to different\n"
    "# items union cleanly; the CLI detects same-item collisions itself.\n"
    "*.jsonl merge=union\n"
)


class SyncContext:
    """State for one save's sync pass."""

    def __init__(self, root: Path, bon_dir: Path, remote: str,
                 remote_branch: str, upstream: str):
        self.root = root
        self.bon_dir = bon_dir
        self.remote = remote
        self.remote_branch = remote_branch
        self.upstream = upstream  # e.g. "origin/main"
        self.offline = False      # fetch failed — push later
        self.deferred = False     # behind but couldn't rebase — push later


def _warn(message: str) -> None:
    print(f"Warning: board sync: {message}", file=sys.stderr)


def _git(root: Path, *args: str, timeout: int = _LOCAL_TIMEOUT):
    """Run git in root, never prompting, capturing output."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def _board_paths(ctx: SyncContext) -> list[str]:
    """Existing board files as pathspecs relative to the repo root."""
    paths = []
    for name in _BOARD_FILES:
        p = ctx.bon_dir / name
        if p.exists():
            paths.append(os.path.relpath(p, ctx.root))
    return paths


def prepare(items_file: Path):
    """Decide whether sync applies to this board. Returns SyncContext or None.

    Every gate degrades to None — a board that doesn't meet the
    preconditions saves exactly as it always has, with no warnings.
    """
    if os.environ.get("BON_SYNC", "").strip().lower() in ("off", "0", "local"):
        return None
    bon_dir = items_file.parent
    marker = bon_dir / "sync"
    try:
        if marker.is_file() and marker.read_text().strip().lower() in ("off", "0", "local"):
            return None
    except OSError:
        return None

    try:
        top = _git(bon_dir, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return None
        root = Path(top.stdout.strip())

        rel_items = os.path.relpath(items_file.resolve(), root.resolve())
        tracked = _git(root, "ls-files", "--error-unmatch", rel_items)
        if tracked.returncode != 0:
            return None

        up = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if up.returncode != 0:
            return None
        upstream = up.stdout.strip()
        if "/" not in upstream:
            return None
        remote, remote_branch = upstream.split("/", 1)
    except (OSError, subprocess.SubprocessError):
        return None

    return SyncContext(root, bon_dir, remote, remote_branch, upstream)


def _commit_board(ctx: SyncContext, message: str) -> bool:
    """Stage and commit board files if any changed. Returns True on commit.

    `git add -f`: a tracked file under an ignored directory otherwise
    stages AND exits 1. `git commit -- <paths>` is a pathspec commit, so
    it can never sweep another session's staged non-board work.
    """
    paths = _board_paths(ctx)
    if not paths:
        return False
    status = _git(ctx.root, "status", "--porcelain", "--", *paths)
    if status.returncode != 0 or not status.stdout.strip():
        return False
    add = _git(ctx.root, "add", "-f", "--", *paths)
    if add.returncode != 0:
        _warn(f"could not stage board files: {add.stderr.strip()}")
        return False
    commit = _git(ctx.root, "commit", "--quiet", "-m", message, "--", *paths)
    if commit.returncode != 0:
        _warn(f"could not commit board files: {commit.stderr.strip()}")
        return False
    return True


def _fetch(ctx: SyncContext) -> bool:
    """Fetch the remote. False = offline.

    Deliberately no fetch-reuse window: a stale remote-tracking ref
    turns the loud same-item conflict into silent newest-wins for any
    edit landing inside the window (caught by this module's own test).
    One fetch per mutating verb is the price of the conflict guarantee.
    """
    try:
        result = _git(ctx.root, "fetch", "--quiet", ctx.remote, timeout=_FETCH_TIMEOUT)
        return result.returncode == 0
    except subprocess.SubprocessError:
        return False


def _behind_count(ctx: SyncContext) -> int:
    result = _git(ctx.root, "rev-list", "--count", f"HEAD..{ctx.upstream}")
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip() or 0)
    except ValueError:
        return 0


def _tree_dirty(ctx: SyncContext) -> bool:
    """Any uncommitted change to tracked files (untracked files don't count)."""
    status = _git(ctx.root, "status", "--porcelain", "--untracked-files=no")
    return status.returncode != 0 or bool(status.stdout.strip())


def merge_items(base: list[dict], ours: list[dict], theirs: list[dict]):
    """Three-way merge at item grain.

    base   — the board as this process loaded it
    ours   — the board this verb wants to write
    theirs — the board as it stands on disk after integrating origin

    Returns (merged_items, conflict_ids). A conflict is an item both
    sides changed (edit/edit, edit/delete, or add/add with different
    content) — those escalate to a human, correctly.
    """
    b = {i["id"]: i for i in base}
    o = {i["id"]: i for i in ours}
    t = {i["id"]: i for i in theirs}

    merged = dict(t)
    conflicts: list[str] = []

    for item_id, item in o.items():
        if item_id not in b:
            # We added it.
            if item_id in t and t[item_id] != item:
                conflicts.append(item_id)
            else:
                merged[item_id] = item
        elif item != b[item_id]:
            # We modified it.
            if item_id not in t:
                conflicts.append(item_id)  # they deleted, we modified
            elif t[item_id] != b[item_id] and t[item_id] != item:
                conflicts.append(item_id)  # both modified, differently
            else:
                merged[item_id] = item
    for item_id in b:
        if item_id not in o:
            # We deleted (archived) it.
            if item_id in t and t[item_id] != b[item_id]:
                conflicts.append(item_id)  # they modified, we deleted
            else:
                merged.pop(item_id, None)

    return list(merged.values()), sorted(set(conflicts))


def resolve_union_artifacts(ctx: SyncContext) -> bool:
    """Turn a silent newest-wins into a loud, lossless resolution.

    After a git-level integration (rebase here or in finalize, or a human's
    plain pull), a same-item edit made on two clones WHILE APART sits in
    items.jsonl as duplicate lines for one id — git's union driver kept
    both, and load-time dedup would silently drop the older on the next
    save. This scans the RAW file: materially-different duplicates are
    resolved by the loader's own rule (newest timestamp wins, so views
    never flicker), every displaced version is appended to the committed
    .bon/sync-conflicts.jsonl sidecar, and each collision is named loudly.
    Byte-identical duplicates (an interrupted run's residue) dedup silently.

    Returns True when it rewrote the file. Bails without touching anything
    on conflict markers or unparseable lines — those are the loader's
    warnings to make, and a rewrite would destroy the evidence.
    """
    import json

    from bon.storage import _most_recent_timestamp

    items_file = ctx.bon_dir / "items.jsonl"
    try:
        raw = items_file.read_text()
    except OSError:
        return False

    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("<<<<<<", "======", ">>>>>>")):
            return False
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            return False

    kept: dict[str, dict] = {}
    displaced: list[dict] = []
    collided: set[str] = set()
    for item in entries:
        item_id = item.get("id", "")
        if item_id in kept:
            if item == kept[item_id]:
                continue  # byte-identical residue — silent dedup
            collided.add(item_id)
            if _most_recent_timestamp(item) >= _most_recent_timestamp(kept[item_id]):
                displaced.append(kept[item_id])
                kept[item_id] = item
            else:
                displaced.append(item)
        else:
            kept[item_id] = item

    if not collided:
        return False

    sidecar = ctx.bon_dir / "sync-conflicts.jsonl"
    try:
        with open(sidecar, "a") as f:
            for item in displaced:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        tmp = items_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            for item in sorted(kept.values(), key=lambda i: i.get("id", "")):
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        tmp.rename(items_file)
    except OSError as e:
        _warn(f"could not resolve duplicate-item sync artifacts ({e})")
        return False

    for item_id in sorted(collided):
        _warn(f"'{item_id}' was edited on two clones while apart — kept the "
              "newest version; the displaced version is preserved in "
              ".bon/sync-conflicts.jsonl. Review with `bon show " + item_id +
              "`, re-apply anything missing, then delete the sidecar file.")
    return True


def _standing_conflict_cue(ctx: SyncContext) -> None:
    """Every clone keeps hearing about unreviewed sync conflicts.

    The clone whose edit was displaced never sees the resolving verb's
    warning — the sidecar travels to it in a commit. This fires on every
    verb, on every clone, until someone reviews and deletes the file.
    """
    sidecar = ctx.bon_dir / "sync-conflicts.jsonl"
    try:
        if sidecar.is_file() and sidecar.stat().st_size > 0:
            _warn("unreviewed sync conflicts in .bon/sync-conflicts.jsonl — "
                  "each line is an item version displaced by a while-apart "
                  "edit; review, re-apply anything missing, then delete the "
                  "file to clear this warning.")
    except OSError:
        pass


def presync(ctx: SyncContext, items: list[dict], snapshot: list[dict] | None,
            load_file) -> list[dict]:
    """Integrate origin before the write. Returns the item list to write.

    Raises BonError (via storage.error) on a same-item conflict, before
    anything is written — origin's version stays in the working tree and
    the verb's change is simply not applied.
    """
    from bon.storage import error

    # Ensure line-wise merges for board files, then bank any board state
    # a previous non-sync writer left uncommitted.
    ga = ctx.bon_dir / ".gitattributes"
    if not ga.exists():
        try:
            ga.write_text(GITATTRIBUTES_CONTENT)
        except OSError:
            pass
    _standing_conflict_cue(ctx)
    # Residue from a HUMAN's plain git pull (no bon verb ran the resolver)
    # can already be sitting in the file — resolve it before banking.
    resolve_union_artifacts(ctx)
    _commit_board(ctx, "bon: board state (pre-sync)")

    if not _fetch(ctx):
        ctx.offline = True
        _warn("could not reach the remote — saving and committing locally; "
              "a future verb will push.")
        return items

    if _behind_count(ctx) == 0:
        return items

    if _tree_dirty(ctx):
        ctx.deferred = True
        _warn("board is behind origin but the repo has uncommitted changes — "
              "saved and committed locally without rebasing; a future verb "
              "from a clean tree will sync.")
        return items

    rebase = _git(ctx.root, "rebase", "--quiet", ctx.upstream, timeout=30)
    if rebase.returncode != 0:
        _git(ctx.root, "rebase", "--abort", timeout=30)
        ctx.deferred = True
        _warn("rebase onto origin hit a conflict outside the board and was "
              "aborted — saved and committed locally; resolve the repo's "
              "divergence, then any verb will sync.")
        return items

    # The rebase just integrated any committed local backlog (offline
    # edits, deferred verbs) with origin's — a while-apart same-item edit
    # now sits as duplicate lines. Resolve loudly and losslessly BEFORE
    # reading the file as "theirs", or the loader's silent newest-wins
    # dedup decides the collision instead (the essayeur's attack 1).
    if resolve_union_artifacts(ctx):
        _commit_board(ctx, "bon: sync conflict resolution (displaced versions "
                           "in .bon/sync-conflicts.jsonl)")

    # The rebase may have changed the board under us: reconcile at item
    # grain rather than letting a whole-file write clobber origin's edits.
    theirs = load_file()
    if snapshot is None:
        # A save with no prior load in-process (migrate, import) is a
        # deliberate whole-board population — ours wins, as documented.
        return items

    merged, conflicts = merge_items(snapshot, items, theirs)
    if conflicts:
        ids = ", ".join(conflicts)
        error(
            f"Board sync conflict — item(s) changed both here and on origin: {ids}.\n"
            "Origin's version is now in your working tree; this command's "
            "change was NOT applied.\n"
            "Compare with `bon show <id>`, then re-run your command against "
            "the fresh board."
        )
    return merged


def finalize(ctx: SyncContext) -> None:
    """Commit the write and push. Never raises — the save already landed."""
    try:
        verb = sys.argv[1] if len(sys.argv) > 1 else "write"
        subject = " ".join(sys.argv[1:3])[:72].replace("\n", " ") or verb
        _commit_board(ctx, f"bon: {subject}")

        if ctx.offline or ctx.deferred:
            return

        # Refuse to publish non-board work as a side effect of a board verb.
        ahead = _git(ctx.root, "rev-list", "--count", f"{ctx.upstream}..HEAD")
        if ahead.returncode != 0 or int(ahead.stdout.strip() or 0) == 0:
            return
        changed = _git(ctx.root, "diff", "--name-only", f"{ctx.upstream}..HEAD")
        if changed.returncode != 0:
            return
        board_prefix = os.path.relpath(ctx.bon_dir, ctx.root).replace(os.sep, "/") + "/"
        for name in changed.stdout.splitlines():
            name = name.strip()
            if name and not name.startswith(board_prefix):
                _warn(f"unpushed commits touch non-board files ({name}) — "
                      "not pushing; push manually or from /close.")
                return

        for _ in range(3):
            push = _git(ctx.root, "push", "--quiet", ctx.remote,
                        f"HEAD:refs/heads/{ctx.remote_branch}", timeout=_PUSH_TIMEOUT)
            if push.returncode == 0:
                return
            # Push race: someone landed between our fetch and push.
            if not _fetch(ctx):
                break
            if _behind_count(ctx) == 0:
                break  # not a race — a real refusal (auth, protection)
            if _tree_dirty(ctx):
                break
            rebase = _git(ctx.root, "rebase", "--quiet", ctx.upstream, timeout=30)
            if rebase.returncode != 0:
                _git(ctx.root, "rebase", "--abort", timeout=30)
                break
            # The race rebase can union two same-item edits exactly like
            # presync's (the essayeur's attack 3) — resolve before re-push
            # so origin never carries a silent newest-wins.
            if resolve_union_artifacts(ctx):
                _commit_board(ctx, "bon: sync conflict resolution (displaced "
                                   "versions in .bon/sync-conflicts.jsonl)")
        _warn("push failed — board is committed locally; a future verb "
              "will push (check remote access / branch protection).")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        _warn(f"sync skipped after save ({e}) — board is written locally.")
