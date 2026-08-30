"""Storage operations for bon items."""
import copy
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bon.ids import get_siblings

# Known updated_by verbs, used by cmd_doctor for validation
KNOWN_VERBS = frozenset({
    "edited", "waited", "unwaited", "worked", "stepped",
    "cleared", "archived", "converted", "reopened", "reclaimed",
    "moved", "parked", "unparked", "released", "repaired",
})

# The message in a bottle: written into every board so an agent with none of
# our tooling (no plugin, no CLI, any vendor) knows how to read and write it.
# Vehicle-neutral by contract (docs/CONTRACT.md non-goals) — no harness-specific
# text. Git-tracked, unlike the prefix/backend markers: travelling with clones
# is its entire job.
BOARD_README = """\
# This is a bon board

This directory is a work tracker ("bon") used by human–AI partnerships.
It is the durable work memory for this repository: **outcomes** (desired
results) and **actions** (concrete steps), each carrying a brief —
why / what / done, plus optional how.

Everything an agent needs to work with it safely is below.
Tool and docs: https://github.com/spm1001/bon

## Reading (safe from any surface)

- `items.jsonl` — one self-describing JSON object per line. Key fields:
  `id`, `type` (outcome|action), `title`, `brief{why,how,what,done}`,
  `status` (open|done), `parent`, `waiting_for` (list of blocker ids),
  `someday` (revisit condition — item is parked, not ready).
- "Ready" = status open, empty/absent `waiting_for`, no `someday` (own or
  parent's).
- If `.bon/backend` contains `dolt`, items live in a shared database this
  clone can't reach — orient from prose instead (below); an items.jsonl
  here is a stale pre-migration ghost, not the board.
- Best orientation: read `understanding.md` and the newest handoff in
  `handoffs/` — each lives either in this directory or visibly at the
  repo/room root.

## Writing (through the tool, never by hand)

- With the CLI (`uv tool install git+https://github.com/spm1001/bon`):
  `bon list`, `bon show ID`, pipe JSON to `bon new`, `bon done ID --note`.
- Without the CLI: leave `items.jsonl` untouched. Append a `### Candidates`
  section to your session's handoff instead, proposing changes as
  provenance-tagged NEW/DONE/EDIT entries — the next tool-bearing session
  applies ("mints") them. Format:
  https://github.com/spm1001/bon/blob/main/docs/HANDOFF-CONTRACT.md
- Hand-edits break invariants the tool maintains: ID uniqueness, dedup,
  the blocker-release cascade, and merge semantics.
"""


class ValidationError(Exception):
    """Raised when item validation fails."""
    pass


class BonError(Exception):
    """Raised by error() for user-facing errors."""
    pass


def error(message: str) -> None:
    """Raise BonError with the given message."""
    raise BonError(message)


def warn(message: str) -> None:
    """Print warning message to stderr (does not exit)."""
    print(f"Warning: {message}", file=sys.stderr)


def refresh_bottle(bon_dir: Path) -> bool:
    """Bring a board's README.md (the bottle) to current BOARD_README wording.

    Returns True when it wrote — the file was missing or carried stale
    wording. The bottle is machine-owned: 29+ static copies shipped in the
    2026-07-21 backfill, so this is the single code path that converges them.
    """
    path = Path(bon_dir) / "README.md"
    if path.exists() and path.read_text() == BOARD_README:
        return False
    path.write_text(BOARD_README)
    return True


def _refresh_bottle_quietly(bon_dir: Path) -> None:
    """Refresh the bottle on the back of a save, like repos-table registration.

    A refresh failure must never break the save it rides.
    """
    try:
        refresh_bottle(bon_dir)
    except OSError:
        pass


_cached_data_dir: Path | None = None
_cached_backend: str | None = None


def _find_bon_dir() -> Path | None:
    """Walk up from CWD to find an existing .bon directory.

    Mirrors git rev-parse semantics: check each directory from CWD upward,
    stopping at a .git boundary (a nested repo without its own board must
    not adopt an outer repo's). At CWD any .bon directory counts; above it
    only a real board does — one with a prefix file — so bare handoff
    stashes like ~/.bon are never adopted on the way up.
    """
    cur = Path.cwd().resolve()
    for directory in (cur, *cur.parents):
        bon = directory / ".bon"
        if bon.is_dir():
            if directory == cur or (bon / "prefix").is_file():
                return bon
            # A cloned repo can carry knowledge files while its local
            # markers were gitignored — adopt it so check_initialized can
            # name the real problem instead of "Not initialized".
            if (directory / ".git").exists() and _looks_like_cloned_board(bon):
                return bon
        if (directory / ".git").exists():
            return None
    return None


def _looks_like_cloned_board(bon: Path) -> bool:
    """True when a .bon has git-tracked knowledge files but no prefix marker."""
    if (bon / "prefix").is_file():
        return False
    return (bon / "handoffs").is_dir() or (bon / "understanding.md").is_file()


def _derive_prefix_from_items(items_file: Path) -> str | None:
    """Best-effort board prefix from item IDs (the token before the first '-').

    A board's items all share its prefix, so the first parseable id suffices.
    Returns None when the file is unreadable or has no usable id.
    """
    try:
        with items_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item_id = item.get("id", "")
                if "-" in item_id:
                    return item_id.split("-", 1)[0]
    except OSError:
        return None
    return None


def _data_dir() -> Path:
    """Return the data directory as an absolute path.

    Walks up from CWD (stopping at a .git boundary) so subdirectory
    sessions find their repo's board; falls back to ./.bon when no board
    exists yet (pre-init). Caches on first call, so CWD changes
    mid-process can't cause reads/writes to target the wrong directory.
    """
    global _cached_data_dir
    if _cached_data_dir is not None:
        return _cached_data_dir

    _cached_data_dir = _find_bon_dir() or Path(".bon").resolve()
    return _cached_data_dir


def _reset_data_dir() -> None:
    """Reset cached data dir. For tests only."""
    global _cached_data_dir
    _cached_data_dir = None


def _get_backend() -> str:
    """Return the storage backend: 'jsonl' (default) or 'dolt'.

    Reads .bon/backend once per process and caches. Absent file = jsonl.
    """
    global _cached_backend
    if _cached_backend is not None:
        return _cached_backend
    backend_file = _data_dir() / "backend"
    if backend_file.exists():
        _cached_backend = backend_file.read_text().strip().lower()
    else:
        _cached_backend = "jsonl"
    return _cached_backend


def _reset_backend() -> None:
    """Reset cached backend. For tests only."""
    global _cached_backend
    _cached_backend = None


def items_path() -> Path:
    """Return the path to items.jsonl.

    Raises BonError in Dolt mode (no local file exists).
    """
    if _get_backend() == "dolt":
        raise BonError("items_path() not available in Dolt mode — items are in the database")
    return _data_dir() / "items.jsonl"


def _most_recent_timestamp(item: dict) -> str:
    """Return the most recent timestamp from an item for dedup comparison."""
    return (item.get("done_at") or item.get("archived_at")
            or item.get("updated_at") or item.get("created_at") or "")


def _normalise_waiting_for(items: list[dict]) -> list[dict]:
    """Normalise waiting_for from legacy string to list format.

    After this, waiting_for is always list[str] or None.
    """
    for item in items:
        wf = item.get("waiting_for")
        if isinstance(wf, str):
            item["waiting_for"] = [wf]
        elif wf is not None and not isinstance(wf, list):
            item["waiting_for"] = None
    return items


def load_items() -> list[dict]:
    """Load all items from JSONL (or Dolt) with validation.

    Deduplicates by ID, preferring the version with the most recent timestamp
    (done_at > archived_at > updated_at > created_at). This handles union merge artifacts where git keeps
    both old and new versions of an edited line.
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_load_items
        return _normalise_waiting_for(dolt_load_items())

    return _load_items_jsonl(_data_dir() / "items.jsonl")


# Board state as loaded, keyed by items.jsonl path. The git sync's
# item-grain merge diffs a save against this, so a write after a rebase
# can't clobber items another clone changed (the resena lesson at git
# grain). Deep-copied: cli.py mutates the loaded dicts in place.
_LOAD_SNAPSHOTS: dict[str, list[dict]] = {}


def _load_items_jsonl(path: Path, record_snapshot: bool = True) -> list[dict]:
    """Parse, validate, and dedup a specific items.jsonl file."""
    if not path.exists():
        if record_snapshot:
            _LOAD_SNAPSHOTS[str(path)] = []
        return []

    seen: dict[str, dict] = {}  # id -> item (best version wins)
    duplicates: set[str] = set()
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        # Detect git conflict markers
        if line.startswith(("<<<<<<", "======", ">>>>>>")):
            print(
                f"Warning: Git conflict marker on line {line_num} — "
                f"resolve merge conflicts in {path}",
                file=sys.stderr,
            )
            continue
        try:
            item = json.loads(line)
            validate_item(item)
            item_id = item["id"]
            if item_id in seen:
                duplicates.add(item_id)
                # Keep the version with the most recent timestamp
                if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                    seen[item_id] = item
            else:
                seen[item_id] = item
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Warning: Skipping malformed item on line {line_num}: {e}", file=sys.stderr)

    if duplicates:
        ids = ", ".join(sorted(duplicates))
        print(
            f"Warning: Duplicate IDs found (merge artifact?): {ids}",
            file=sys.stderr,
        )

    result = _normalise_waiting_for(list(seen.values()))
    if record_snapshot:
        _LOAD_SNAPSHOTS[str(path)] = copy.deepcopy(result)
    return result


def validate_item(item: dict, strict: bool = False) -> None:
    """Validate item has required fields. Raises ValidationError if invalid.

    Args:
        item: The item to validate
        strict: If True, also validates brief subfields (used for bon edit).
                If False, lenient validation for loading potentially old data.
    """
    required = ["id", "type", "title", "status"]
    for field in required:
        if field not in item:
            raise ValidationError(f"Missing required field: {field}")

    if item["type"] not in ("outcome", "action"):
        raise ValidationError(f"Invalid type: {item['type']}")

    if item["status"] not in ("open", "done"):
        raise ValidationError(f"Invalid status: {item['status']}")

    if strict:
        # Brief must exist and have all subfields
        if "brief" not in item:
            raise ValidationError("Missing required field: brief")
        brief = item.get("brief", {})
        for subfield in ["why", "what", "done"]:
            if subfield not in brief:
                raise ValidationError(f"Missing brief.{subfield}")


def save_items(items: list[dict]) -> None:
    """Save items atomically, sorted by ID for deterministic output.

    Deduplicates by ID before writing, keeping the version with the most
    recent timestamp. This prevents duplicate lines from any source
    (migrate, manual edits, agent mistakes).

    Deterministic order means two branches that touch different items
    produce minimal diffs, enabling clean git merges.
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_save_items
        dolt_save_items(items)
        _refresh_bottle_quietly(_data_dir())
        return
    path = _data_dir() / "items.jsonl"
    ctx = _presync_jsonl(path, items)
    if ctx is not None:
        items = ctx[1]
    _save_items_jsonl(path, items)
    _refresh_bottle_quietly(_data_dir())
    if ctx is not None:
        from bon.gitsync import finalize
        finalize(ctx[0])


def _presync_jsonl(path: Path, items: list[dict]):
    """Run the git sync's pre-write pass for a JSONL board (bon-guritu).

    Returns (ctx, items_to_write) when sync engages, else None. A
    same-item conflict raises BonError here — before anything is written,
    so neither side's edit is silently dropped. Any other sync failure
    degrades to an unsynced save: losing the sync must never lose the
    write.
    """
    from bon.gitsync import prepare, presync
    try:
        ctx = prepare(path)
        if ctx is None:
            return None
        merged = presync(
            ctx, items, _LOAD_SNAPSHOTS.get(str(path)),
            lambda: _load_items_jsonl(path, record_snapshot=False),
        )
        return (ctx, merged)
    except BonError:
        raise
    except (OSError, subprocess.SubprocessError) as e:
        warn(f"board sync: skipped ({e}) — saving locally.")
        return None


def _save_items_jsonl(path: Path, items: list[dict]) -> None:
    """Dedup and atomically write items to a specific items.jsonl file."""
    seen: dict[str, dict] = {}
    duplicates: set[str] = set()
    for item in items:
        item_id = item.get("id", "")
        if item_id in seen:
            duplicates.add(item_id)
            if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                seen[item_id] = item
        else:
            seen[item_id] = item

    if duplicates:
        ids = ", ".join(sorted(duplicates))
        print(f"Warning: Deduplicated IDs on save: {ids}", file=sys.stderr)

    tmp = path.with_suffix(".tmp")

    with open(tmp, "w") as f:
        for item in sorted(seen.values(), key=lambda i: i.get("id", "")):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    tmp.rename(path)  # Atomic on POSIX


def load_prefix() -> str:
    """Load prefix from local .bon/prefix file, default to 'bon'.

    Even in Dolt mode, prefix is local — it scopes which items to load.

    Stripped on read: `bon init` writes the file without a trailing newline
    (cli.py), but a hand-written `echo crn > .bon/prefix` adds one, and the
    newline then lands INSIDE every id minted afterwards — `crn\\n-kemize`,
    which `bon show crn-kemize` cannot resolve. Cornichon carried three such
    ids for a week and the failure read as a missing item (bon-nuduta).
    Strip both ends: leading whitespace from a hand-edit is just as wrong,
    and a prefix is never legitimately padded.
    """
    path = _data_dir() / "prefix"
    if path.exists():
        return path.read_text().strip() or "bon"
    return "bon"


def find_by_id(items: list[dict], item_id: str, prefix: str | None = None) -> dict | None:
    """Find item by ID. Returns None if not found.

    Searches all items regardless of status (open or done).
    Case-sensitive. Tries exact match first, then prefix + id.

    Args:
        items: All items to search
        item_id: The ID to find (full or suffix)
        prefix: Current prefix for prefix-tolerant matching
    """
    # Exact match first
    for item in items:
        if item["id"] == item_id:
            return item

    # Prefix-tolerant: try prepending prefix
    if prefix and not item_id.startswith(prefix + "-"):
        prefixed = f"{prefix}-{item_id}"
        for item in items:
            if item["id"] == prefixed:
                return item

    return None


_creator_cache: str | None = None


def get_creator() -> str:
    """Get creator identifier for new items.

    Returns "{name}" for AI agents (common case), "{name}-tty" for humans typing directly.
    Result is cached after first call (git runs at most once per process).

    Name priority:
    1. BON_USER env var (explicit override)
    2. ARC_USER env var (transition fallback)
    3. git config user.name (most common)
    4. USER env var (fallback)
    5. "unknown" (last resort)
    """
    global _creator_cache
    if _creator_cache is not None:
        return _creator_cache

    # Get the human identity
    name = None

    # Explicit override (BON_USER preferred, ARC_USER fallback)
    if bon_user := os.environ.get("BON_USER"):
        name = bon_user
    elif arc_user := os.environ.get("ARC_USER"):
        # Deprecated old-codename fallback — remove this branch in v0.30+
        warn("ARC_USER is deprecated, use BON_USER (will be removed in v0.30+)")
        name = arc_user

    # Git user name
    if not name:
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                name = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # System user
    if not name:
        name = os.environ.get("USER", "unknown")

    # Suffix -tty if human is typing directly (rare case)
    if sys.stdin.isatty():
        _creator_cache = f"{name}-tty"
    else:
        _creator_cache = name

    return _creator_cache


def now_iso() -> str:
    """Current time in ISO8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_initialized() -> None:
    """Check if .bon/ is initialized here or in a parent (up to a .git boundary)."""
    data = _data_dir()
    if not data.is_dir():
        error(
            f"Not initialized: no .bon/ found from {data.parent} upward\n"
            "(the search stops at a .git boundary). Run `bon init` here, or cd\n"
            "into a directory whose repo has a board."
        )
    if _looks_like_cloned_board(data):
        items_file = data / "items.jsonl"
        if items_file.is_file():
            # A live items.jsonl with no prefix marker is a JSONL board whose
            # marker was lost — NOT a clone, NOT a Dolt board. The data is right
            # here; restore the marker. Do not reconnect to Dolt: that would flip
            # a live JSONL board and orphan this file (bon-zageme).
            derived = _derive_prefix_from_items(items_file)
            prefix_hint = derived or "<prefix>"
            error(
                f"{data} has a live items.jsonl but no .bon/prefix marker.\n"
                "This is a JSONL board whose prefix marker was lost — the data is\n"
                "right here, not in Dolt. Restore the marker (non-destructive —\n"
                f"completes the marker, touches nothing else) from {data.parent}:\n"
                f"  bon init --prefix {prefix_hint}\n"
                "(prefix derived from the item IDs in items.jsonl). Then commit\n"
                ".bon/prefix in the origin repo so it can't go missing again."
            )
        error(
            f"{data} has bon knowledge files (handoffs/understanding) and no\n"
            "items.jsonl or .bon/prefix marker — this looks like a fresh clone of a\n"
            "repo that gitignores its markers. The board data is safe; it lives in\n"
            "the Dolt server (or the origin's items.jsonl), not here. Reconnect from\n"
            f"{data.parent} with:\n"
            "  bon init --prefix <prefix> --backend dolt\n"
            "(non-destructive — completes the missing markers, touches nothing else).\n"
            "Better still: commit .bon/prefix and .bon/backend in the origin repo;\n"
            "the machine-local part of Dolt config is ~/.config/bon/dolt.toml."
        )


# ---------- cross-repo board access (bon move) ----------

def target_board(root: Path) -> dict:
    """Resolve another repo's board without touching this process's caches.

    Returns {"root", "dir", "prefix", "backend"}. Raises BonError when the
    target has no initialized board (no .bon/ or no prefix marker).
    """
    root = Path(root).expanduser().resolve()
    bon = root / ".bon"
    if not bon.is_dir() or not (bon / "prefix").is_file():
        raise BonError(
            f"Target not initialized: no .bon/ board with a prefix at {root}.\n"
            "Run `bon init` there first."
        )
    prefix = (bon / "prefix").read_text().strip()
    backend_file = bon / "backend"
    backend = backend_file.read_text().strip().lower() if backend_file.is_file() else "jsonl"
    return {"root": root, "dir": bon, "prefix": prefix, "backend": backend}


def load_items_at(board: dict) -> list[dict]:
    """Load items from another repo's board (both backends)."""
    if board["backend"] == "dolt":
        from bon.dolt import dolt_load_items
        return _normalise_waiting_for(dolt_load_items(prefix=board["prefix"]))
    return _load_items_jsonl(board["dir"] / "items.jsonl")


def save_items_at(board: dict, items: list[dict]) -> None:
    """Save items to another repo's board (both backends)."""
    if board["backend"] == "dolt":
        from bon.dolt import dolt_save_items
        # board_root: register the TARGET repo's identity, not cwd's (bon-nolido)
        dolt_save_items(items, prefix=board["prefix"], board_root=board["root"])
        _refresh_bottle_quietly(board["dir"])
        return
    path = board["dir"] / "items.jsonl"
    ctx = _presync_jsonl(path, items)
    if ctx is not None:
        items = ctx[1]
    _save_items_jsonl(path, items)
    _refresh_bottle_quietly(board["dir"])
    if ctx is not None:
        from bon.gitsync import finalize
        finalize(ctx[0])


def archive_ids_at(board: dict) -> set[str]:
    """Archived item IDs in another repo's board, for unique-ID generation."""
    if board["backend"] == "dolt":
        from bon.dolt import dolt_load_archive
        return {i["id"] for i in dolt_load_archive(prefix=board["prefix"]) if i.get("id")}
    ids: set[str] = set()
    path = board["dir"] / "archive.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return ids


def apply_reorder(items: list[dict], edited: dict, old_order: int, new_order: int):
    """Shift siblings to accommodate order change.

    Moving from 5 to 2: items at 2, 3, 4 shift to 3, 4, 5.
    Moving from 2 to 5: items at 3, 4, 5 shift to 2, 3, 4.
    """
    if old_order == new_order:
        return

    siblings = [i for i in get_siblings(items, edited["type"], edited.get("parent"))
                if i["id"] != edited["id"]]

    if new_order < old_order:
        # Moving up: shift items in [new, old) down by 1
        for s in siblings:
            if new_order <= s.get("order", 0) < old_order:
                s["order"] += 1
    else:
        # Moving down: shift items in (old, new] up by 1
        for s in siblings:
            if old_order < s.get("order", 0) <= new_order:
                s["order"] -= 1


def apply_reparent(items: list[dict], edited: dict, old_parent: str | None, new_parent: str | None):
    """Handle parent change: close gap in old parent, append to new parent.

    When an action moves from one outcome to another:
    1. Close the gap left behind (shift old siblings up)
    2. Append at end of new parent's children
    """
    if old_parent == new_parent:
        return

    old_order = edited.get("order", 1)

    # Close gap in old parent's children
    old_siblings = [i for i in items
                    if i["type"] == "action"
                    and i.get("parent") == old_parent
                    and i["id"] != edited["id"]]
    for s in old_siblings:
        if s.get("order", 0) > old_order:
            s["order"] -= 1

    # Append to end of new parent's children
    new_siblings = [i for i in items
                    if i["type"] == "action"
                    and i.get("parent") == new_parent
                    and i["id"] != edited["id"]]
    if new_siblings:
        max_order = max(s.get("order", 0) for s in new_siblings)
        edited["order"] = max_order + 1
    else:
        edited["order"] = 1


def get_session_identity() -> str:
    """Return the session identity for tactical steps.

    Identity is the .bon root (the directory holding .bon), not the bare
    CWD: walk-up discovery means every subdirectory of a project shares
    the board, so they must also share the one-active-tactical claim —
    otherwise two subdirs of one repo could claim two tacticals on the
    same board. Pre-init (no .bon found) this degrades to CWD, matching
    the old behavior.
    In JSONL mode: realpath of the .bon root.
    In Dolt mode: hostname:realpath — prevents false conflicts when two
    machines have the same absolute path.
    """
    path = os.path.realpath(_data_dir().parent)
    if _get_backend() == "dolt":
        import socket
        return f"{socket.gethostname()}:{path}"
    return path


def _tactical_is_active(item: dict) -> bool:
    """Check if an item has active (incomplete) tactical steps.

    A RELEASED tactical is not active: its progress is intact but nobody is
    holding the claim, so it must not block another action from being worked,
    must not be injected into a session's prompt, and must not read as
    orphaned. Gating here covers every caller at once — this is the single
    definition of "someone is working on this" (bon-kewimu).

    `released` lives INSIDE the tactical object rather than beside it as an
    item column. Same reasoning as the `someday` field, one level deeper: an
    older client rewriting the row round-trips `tactical` as one opaque JSON
    value, so a nested key survives a write by a version that has never heard
    of it — where a new top-level column would be stripped by the fixed
    _ITEM_COLUMNS list.
    """
    if item.get("status") != "open":
        return False
    tactical = item.get("tactical")
    if not tactical or tactical.get("released"):
        return False
    return tactical.get("current", 0) < len(tactical.get("steps", []))


def _matches_session(item_session: str | None, session: str | None) -> bool:
    """Check if an item's tactical session matches the requested session.

    - session=None: match only unscoped tacticals (no session field) — backward compat
    - session="/path": match tactical.session == path OR unscoped (legacy claimable)
    """
    if session is None:
        return item_session is None
    return item_session == session or item_session is None


def find_active_tactical(items: list[dict], session: str | None = None) -> dict | None:
    """Find the item with active tactical steps for a given session, or None."""
    for item in items:
        if not _tactical_is_active(item):
            continue
        item_session = item.get("tactical", {}).get("session")
        if _matches_session(item_session, session):
            return item
    return None


def find_any_active_tactical(items: list[dict]) -> list[dict]:
    """Find ALL items with active tactical steps, regardless of session.

    Used for cross-session conflict detection.
    """
    return [item for item in items if _tactical_is_active(item)]


def find_no_complete_tactical(items: list[dict], session: str | None = None) -> dict | None:
    """Find an open action where all tactical steps are done (--no-complete state)."""
    for item in items:
        if item.get("status") != "open" or not item.get("tactical"):
            continue
        tactical = item["tactical"]
        if tactical.get("released"):
            continue
        steps = tactical.get("steps", [])
        if not steps or tactical.get("current", 0) < len(steps):
            continue
        if _matches_session(tactical.get("session"), session):
            return item
    return None


def find_released_tactical(items: list[dict], session: str | None = None) -> dict | None:
    """Find a tactical this session released — progress intact, claim handed back.

    `--status` reports it rather than saying "no active tactical steps": a
    released tactical is deliberately parked work, and answering "nothing
    here" would make it invisible exactly when someone is asking what they
    were doing.
    """
    for item in items:
        if item.get("status") != "open":
            continue
        tactical = item.get("tactical")
        if not tactical or not tactical.get("released"):
            continue
        if _matches_session(tactical.get("session"), session):
            return item
    return None


def find_orphaned_tactical(items: list[dict], session: str) -> dict | None:
    """Find an item with active tactical steps whose session path no longer exists.

    Returns the first orphaned item found, or None. Only checks items
    whose session differs from the given session (current CWD).
    """
    for item in items:
        if not _tactical_is_active(item):
            continue
        item_session = item.get("tactical", {}).get("session")
        if item_session and item_session != session and not os.path.isdir(item_session):
            return item
    return None


def load_archive() -> list[dict]:
    """Load archived items from archive.jsonl (or Dolt archive table)."""
    if _get_backend() == "dolt":
        from bon.dolt import dolt_load_archive
        return dolt_load_archive()

    path = _data_dir() / "archive.jsonl"
    if not path.exists():
        return []

    items = []
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            items.append(item)
        except json.JSONDecodeError as e:
            print(f"Warning: Skipping malformed archive item on line {line_num}: {e}", file=sys.stderr)

    return items


def append_archive(items: list[dict]) -> None:
    """Append items to archive.jsonl (or Dolt archive table) atomically.

    Deduplicates by ID (keeping most recent via _most_recent_timestamp),
    same as save_items. Writes atomically with tmp+rename.
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_append_archive
        return dolt_append_archive(items)

    existing = load_archive()

    seen: dict[str, dict] = {}
    for item in existing + items:
        item_id = item.get("id", "")
        if item_id in seen:
            if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                seen[item_id] = item
        else:
            seen[item_id] = item

    path = _data_dir() / "archive.jsonl"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        for item in sorted(seen.values(), key=lambda i: i.get("id", "")):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    tmp.rename(path)  # Atomic on POSIX


def remove_from_archive(item_id: str, prefix: str | None = None) -> dict | None:
    """Remove an item from archive (JSONL or Dolt). Returns the item, or None if not found.

    Rewrites archive atomically (same pattern as save_items).
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_remove_from_archive
        return dolt_remove_from_archive(item_id, prefix)

    archived = load_archive()
    item = find_by_id(archived, item_id, prefix)
    if not item:
        return None

    remaining = [i for i in archived if i["id"] != item["id"]]
    path = _data_dir() / "archive.jsonl"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        for i in remaining:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")
    tmp.rename(path)

    return item


def validate_tactical(tactical: dict) -> None:
    """Validate tactical structure. Raises ValidationError if invalid."""
    if not isinstance(tactical.get("steps"), list):
        raise ValidationError("tactical.steps must be a list")
    if not tactical["steps"]:
        raise ValidationError("tactical.steps cannot be empty")
    if not all(isinstance(s, str) for s in tactical["steps"]):
        raise ValidationError("tactical.steps must contain strings")
    current = tactical.get("current", 0)
    if not isinstance(current, int) or current < 0:
        raise ValidationError("tactical.current must be non-negative integer")
    # session is optional; when present must be a non-empty string
    session = tactical.get("session")
    if session is not None and (not isinstance(session, str) or not session):
        raise ValidationError("tactical.session must be a non-empty string")
    # skipped is optional; when present must be dict with string keys and string values
    skipped = tactical.get("skipped")
    if skipped is not None:
        if not isinstance(skipped, dict):
            raise ValidationError("tactical.skipped must be a dict")
        for key, value in skipped.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidationError("tactical.skipped keys and values must be strings")
