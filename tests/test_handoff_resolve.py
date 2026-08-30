"""
Tests for the shared handoff / understanding.md resolver (scripts/lib-handoff.sh).

The resolver is the single source of truth that open-context.sh (READ) and
close-context.sh (WRITE) both source, so they cannot drift. It implements the
"visible substrate" convention: prose (handoffs/, understanding.md) lives
VISIBLE at the room where work happens; the board (.bon/items.jsonl) stays
hidden + repo-global.

These source the lib in a bash subprocess and call its functions directly, so
the tests assert the actual contract rather than reproduced logic. HOME is
isolated to a throwaway dir so the machine's real ~/.bon/handoffs never leaks
into results.

Two regression anchors:

- The 2026-06-17 stale-handoff bug — a newer handoff in a visible root
  handoffs/ was invisible to /open because it only checked .bon/handoffs/
  (bon-zopopu).
- bon-sedoze (Aug 2026), which retired the .bon/handoffs rung outright. That
  is a BREAKING change for any consumer whose pile still lives there, so the
  migration that converges them is tested here as hard as the resolution is:
  TestHandoffMigrateLegacy below is the guard, and its
  test_residue_is_discoverable_after_migration is the end-to-end that the
  retirement is only safe *because of*.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
LIB = REPO_ROOT / "scripts" / "lib-handoff.sh"


def call(func: str, start: Path, home: Path) -> str:
    """Source lib-handoff.sh, call `func <start>`, return stripped stdout.

    HOME is isolated so the global ~/.bon/handoffs fallback can't pull in the
    machine's real handoffs.
    """
    result = subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {func} "{start}"'],
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    return result.stdout.strip()


def lines(func: str, start: Path, home: Path) -> list[str]:
    out = call(func, start, home)
    return [ln for ln in out.splitlines() if ln]


def make_repo(
    root: Path,
    *,
    visible_handoffs: bool = False,
    bon_handoffs: bool = False,
    root_understanding: bool = False,
    bon_understanding: bool = False,
) -> Path:
    """Create a bon repo (with .bon/prefix + git) and optional prose dirs/files."""
    (root / ".bon").mkdir(parents=True, exist_ok=True)
    (root / ".bon" / "prefix").write_text("test")
    (root / ".bon" / "items.jsonl").write_text("")
    if bon_handoffs:
        (root / ".bon" / "handoffs").mkdir(exist_ok=True)
    if visible_handoffs:
        (root / "handoffs").mkdir(exist_ok=True)
    if root_understanding:
        (root / "understanding.md").write_text("root understanding")
    if bon_understanding:
        (root / ".bon" / "understanding.md").write_text("bon understanding")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    (h / ".claude").mkdir(parents=True)
    return h


# --- handoff_write_dir -------------------------------------------------------

class TestHandoffWriteDir:
    def test_visible_handoffs_preferred(self, tmp_path, home):
        """The 06-17 convention: a visible handoffs/ is where handoffs go."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True, bon_handoffs=True)
        assert call("handoff_write_dir", repo, home) == str(repo / "handoffs")

    def test_legacy_dir_is_never_chosen(self, tmp_path, home):
        """bon-sedoze: .bon/handoffs is not a rung, even when it is the only
        handoffs dir on disk. The pile there is migrated, not written to."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        assert call("handoff_write_dir", repo, home) == str(repo / "handoffs")

    def test_fresh_repo_defaults_to_visible_root(self, tmp_path, home):
        """No handoffs dir yet → the board root's visible handoffs/, created on
        write. This is the default a fresh `bon init` repo now gets."""
        repo = make_repo(tmp_path / "repo")
        assert call("handoff_write_dir", repo, home) == str(repo / "handoffs")

    def test_room_with_handoffs_writes_to_room(self, tmp_path, home):
        """Launched in a room that hosts its own handoffs/ → nearest-room wins."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        room = repo / "work" / "room"
        (room / "handoffs").mkdir(parents=True)
        assert call("handoff_write_dir", room, home) == str(room / "handoffs")

    def test_room_without_handoffs_falls_to_board_root(self, tmp_path, home):
        """A bare room (no handoffs/) falls back to the board root's visible dir."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        room = repo / "work" / "bare"
        room.mkdir(parents=True)
        assert call("handoff_write_dir", room, home) == str(repo / "handoffs")

    def test_no_board_falls_to_global(self, tmp_path, home):
        """Outside any board the global catch-all is still the honest answer —
        bon-vucumo kept that rung deliberately."""
        bare = tmp_path / "bare"
        bare.mkdir()
        subprocess.run(["git", "init", "-q", str(bare)], check=True)
        assert call("handoff_write_dir", bare, home) == str(home / ".bon" / "handoffs")


# --- handoff_read_dirs -------------------------------------------------------

class TestHandoffReadDirs:
    def test_room_listed_before_root(self, tmp_path, home):
        """READ sees every visible dir up the tree, nearest first, so a repo
        with prose at several levels ranks the genuinely-newest (the 06-17 fix)."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        room = repo / "work" / "room"
        (room / "handoffs").mkdir(parents=True)
        got = lines("handoff_read_dirs", room, home)
        assert got[0] == str(room / "handoffs")
        assert str(repo / "handoffs") in got

    def test_legacy_dir_is_not_read(self, tmp_path, home):
        """bon-sedoze: the retired rung. A pile sitting there is invisible to
        the reader — which is exactly why the migration below has to fire."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        got = lines("handoff_read_dirs", repo, home)
        assert str(repo / ".bon" / "handoffs") not in got

    def test_global_fallback_is_last(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        got = lines("handoff_read_dirs", repo, home)
        assert got[-1] == str(home / ".bon" / "handoffs")  # bon-vucumo: kept


# --- understanding_path ------------------------------------------------------

class TestUnderstandingPath:
    def test_visible_root_preferred(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", root_understanding=True, bon_understanding=True)
        assert call("understanding_path", repo, home) == str(repo / "understanding.md")

    def test_bon_fallback(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", bon_understanding=True)
        assert call("understanding_path", repo, home) == str(repo / ".bon" / "understanding.md")

    def test_nearest_room_understanding(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", bon_understanding=True)
        room = repo / "work" / "room"
        room.mkdir(parents=True)
        (room / "understanding.md").write_text("room understanding")
        assert call("understanding_path", room, home) == str(room / "understanding.md")

    def test_none_emits_nothing(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo")
        assert call("understanding_path", repo, home) == ""


# --- handoff_migrate_legacy (bon-sedoze) --------------------------------------

HANDOFF_BODY = "# Handoff — 2026-08-20\n\nsession_id: x\npurpose: {p}\nformat: fond-v1\n"


def call_migrate(start: Path, home: Path) -> dict:
    """Run handoff_migrate_legacy and read back the variables it sets.

    It prints nothing by design (reader and writer frame their output
    differently), so the contract under test is the three variables.
    """
    script = (
        f'set -euo pipefail; source "{LIB}"; handoff_migrate_legacy "{start}"; '
        'echo "N=$HANDOFF_MIGRATED_N"; '
        'echo "DEST=$HANDOFF_MIGRATED_DEST"; '
        'echo "FAILED=$HANDOFF_MIGRATED_FAILED"'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    out = {"_rc": result.returncode, "_stderr": result.stderr}
    for ln in result.stdout.splitlines():
        if "=" in ln:
            k, v = ln.split("=", 1)
            out[k] = v
    return out


def seed_legacy(repo: Path, name: str, purpose: str = "legacy") -> Path:
    legacy = repo / ".bon" / "handoffs"
    legacy.mkdir(parents=True, exist_ok=True)
    f = legacy / name
    f.write_text(HANDOFF_BODY.format(p=purpose))
    return f


def commit_all(repo: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@e.x", "-c", "user.name=T",
         "commit", "-qm", "seed"],
        check=True,
    )


class TestHandoffMigrateLegacy:
    def test_moves_pile_to_visible_root(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo")
        seed_legacy(repo, "2026-08-01-1200-aaaabbbb.md")
        seed_legacy(repo, "2026-08-20-0930-ccccdddd.md")

        got = call_migrate(repo, home)

        assert got["_rc"] == 0, got["_stderr"]
        assert got["N"] == "2"
        assert got["DEST"] == str(repo / "handoffs")
        assert got["FAILED"] == "0"
        assert sorted(p.name for p in (repo / "handoffs").iterdir()) == [
            "2026-08-01-1200-aaaabbbb.md",
            "2026-08-20-0930-ccccdddd.md",
        ]
        assert not (repo / ".bon" / "handoffs").exists()  # no empty husk left

    def test_residue_is_discoverable_after_migration(self, tmp_path, home):
        """THE end-to-end. Before: the pile sits in a dir the reader no longer
        consults, so the consumer's handoffs are silently gone. After: the file
        is inside a dir handoff_read_dirs returns. This is the assertion the
        rung retirement is safe because of — if it ever goes red, the retirement
        is a data-visibility bug for every external consumer."""
        repo = make_repo(tmp_path / "repo")
        seed_legacy(repo, "2026-08-20-0930-ccccdddd.md")

        # Red: the residue is in no read dir.
        before = lines("handoff_read_dirs", repo, home)
        assert str(repo / ".bon" / "handoffs") not in before

        call_migrate(repo, home)

        after = lines("handoff_read_dirs", repo, home)
        found = [d for d in after if (Path(d) / "2026-08-20-0930-ccccdddd.md").exists()]
        assert found == [str(repo / "handoffs")]

    def test_is_idempotent(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo")
        seed_legacy(repo, "a.md")
        first = call_migrate(repo, home)
        second = call_migrate(repo, home)

        assert first["N"] == "1"
        assert second["N"] == "0"  # nothing left to do, and no error
        assert second["FAILED"] == "0"
        assert [p.name for p in (repo / "handoffs").iterdir()] == ["a.md"]

    def test_absent_legacy_dir_is_a_noop(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        got = call_migrate(repo, home)
        assert got["N"] == "0"
        assert got["FAILED"] == "0"

    def test_no_board_is_a_noop(self, tmp_path, home):
        bare = tmp_path / "bare"
        bare.mkdir()
        got = call_migrate(bare, home)
        assert got["_rc"] == 0, got["_stderr"]
        assert got["N"] == "0"

    def test_tracked_move_is_staged_as_a_rename(self, tmp_path, home):
        """A tracked handoff moves with `git mv` so the rename is staged. A
        plain mv would leave the deletion unstaged and the addition untracked —
        one careless `git add .bon/` away from committing the file's removal."""
        repo = make_repo(tmp_path / "repo")
        seed_legacy(repo, "a.md")
        commit_all(repo)

        call_migrate(repo, home)

        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert status.startswith("R "), status
        assert "handoffs/a.md" in status

    def test_untracked_residue_still_moves(self, tmp_path, home):
        """The wholesale-`.bon/`-ignore case (bon-kizeje): git mv refuses a path
        it does not track, so the plain-mv path has to carry it."""
        repo = make_repo(tmp_path / "repo")
        (repo / ".gitignore").write_text(".bon/\n")
        seed_legacy(repo, "a.md")

        got = call_migrate(repo, home)

        assert got["N"] == "1"
        assert got["FAILED"] == "0"
        assert (repo / "handoffs" / "a.md").exists()

    def test_name_collision_keeps_both(self, tmp_path, home):
        """Never overwrite a handoff — it is the only record of a session."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        (repo / "handoffs" / "a.md").write_text(HANDOFF_BODY.format(p="VISIBLE"))
        seed_legacy(repo, "a.md", purpose="LEGACY")

        got = call_migrate(repo, home)

        assert got["N"] == "1"
        assert "VISIBLE" in (repo / "handoffs" / "a.md").read_text()
        assert "LEGACY" in (repo / "handoffs" / "a-legacy2.md").read_text()

    def test_identical_duplicate_is_dropped_not_doubled(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        (repo / "handoffs" / "a.md").write_text(HANDOFF_BODY.format(p="same"))
        seed_legacy(repo, "a.md", purpose="same")

        call_migrate(repo, home)

        assert [p.name for p in (repo / "handoffs").iterdir()] == ["a.md"]
        assert not (repo / ".bon" / "handoffs").exists()

    def test_room_launch_migrates_to_board_root_not_room(self, tmp_path, home):
        """Root-level history must not be relocated into whichever room the
        session happened to start in."""
        repo = make_repo(tmp_path / "repo")
        room = repo / "work" / "room"
        (room / "handoffs").mkdir(parents=True)
        seed_legacy(repo, "a.md")

        got = call_migrate(room, home)

        assert got["DEST"] == str(repo / "handoffs")
        assert (repo / "handoffs" / "a.md").exists()
        assert not (room / "handoffs" / "a.md").exists()

    def test_collision_search_refuses_rather_than_clobbers(self, tmp_path, home):
        """Pathological but unbounded: fill every -legacy2..99 slot and the
        search runs out. It must leave the file put and report incomplete —
        overwriting the hundredth would destroy the only copy of a session."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        (repo / "handoffs" / "a.md").write_text(HANDOFF_BODY.format(p="visible"))
        for i in range(2, 101):  # 2..100 — every slot the search can reach
            (repo / "handoffs" / f"a-legacy{i}.md").write_text(HANDOFF_BODY.format(p=f"v{i}"))
        seed_legacy(repo, "a.md", purpose="THE ONLY COPY")

        got = call_migrate(repo, home)

        assert got["N"] == "0"
        assert got["FAILED"] == "1"
        assert "THE ONLY COPY" in (repo / ".bon" / "handoffs" / "a.md").read_text()
        assert "v100" in (repo / "handoffs" / "a-legacy100.md").read_text()

    def test_collision_uses_the_last_free_slot(self, tmp_path, home):
        """Positive control for the guard above — with slot 100 free it moves
        there rather than refusing, so the refusal is a real boundary and not
        an off-by-one that fires early."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        (repo / "handoffs" / "a.md").write_text(HANDOFF_BODY.format(p="visible"))
        for i in range(2, 100):  # 2..99 taken, 100 free
            (repo / "handoffs" / f"a-legacy{i}.md").write_text(HANDOFF_BODY.format(p=f"v{i}"))
        seed_legacy(repo, "a.md", purpose="LAST SLOT")

        got = call_migrate(repo, home)

        assert got["N"] == "1"
        assert got["FAILED"] == "0"
        assert "LAST SLOT" in (repo / "handoffs" / "a-legacy100.md").read_text()

    # --- physical identity: the branch that once deleted the only copy ------
    #
    # Found by an adversarial verifier, 2026-08-30. The dedup branch treats
    # "target exists and compares identical" as "already migrated, drop the
    # duplicate". When both names reach ONE directory, every file is identical
    # to itself, so the rm unlinked the single inode: every handoff in the repo
    # destroyed, silently, N=0 and exit 0. Permanent on a gitignored pile.
    # The suite green-lit it because every collision test used a real COPY.

    def test_forward_symlink_shim_destroys_nothing(self, tmp_path, home):
        """`ln -s .bon/handoffs handoffs` — the zero-risk shim a consumer makes
        to get the visible convention without rewriting git history."""
        repo = make_repo(tmp_path / "repo")
        seed_legacy(repo, "a.md", purpose="ONLY COPY A")
        seed_legacy(repo, "b.md", purpose="ONLY COPY B")
        (repo / "handoffs").symlink_to(repo / ".bon" / "handoffs")

        got = call_migrate(repo, home)

        assert got["_rc"] == 0, got["_stderr"]
        assert got["FAILED"] == "0"
        assert "ONLY COPY A" in (repo / ".bon" / "handoffs" / "a.md").read_text()
        assert "ONLY COPY B" in (repo / ".bon" / "handoffs" / "b.md").read_text()
        assert sorted(p.name for p in (repo / "handoffs").iterdir()) == ["a.md", "b.md"]

    def test_reverse_symlink_shim_destroys_nothing(self, tmp_path, home):
        """`.bon/handoffs -> ../handoffs`, the compat shim left after someone
        hand-migrated. Destroying this pile also empties the visible dir."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        (repo / "handoffs" / "a.md").write_text(HANDOFF_BODY.format(p="ONLY COPY"))
        (repo / ".bon" / "handoffs").symlink_to(repo / "handoffs")

        got = call_migrate(repo, home)

        assert got["_rc"] == 0, got["_stderr"]
        assert got["FAILED"] == "0"
        assert "ONLY COPY" in (repo / "handoffs" / "a.md").read_text()

    def test_hardlinked_duplicate_is_skipped_not_unlinked(self, tmp_path, home):
        """Same inode by a different route — the per-file -ef guard.

        The content survives either way (unlinking one of two links leaves the
        other), so asserting only on the visible copy would be a test that can
        never fail. The discriminating assertion is that the LEGACY path is
        still there: with the guard we skip the file entirely; without it, the
        cmp-identical branch unlinks it.
        """
        repo = make_repo(tmp_path / "repo", visible_handoffs=True)
        seed_legacy(repo, "a.md", purpose="ONLY COPY")
        (repo / "handoffs" / "a.md").hardlink_to(repo / ".bon" / "handoffs" / "a.md")

        call_migrate(repo, home)

        assert "ONLY COPY" in (repo / "handoffs" / "a.md").read_text()
        assert (repo / ".bon" / "handoffs" / "a.md").exists(), "skipped, not unlinked"

    def test_bare_stash_is_not_a_board(self, tmp_path, home):
        """~/.bon has no prefix marker. close-context still WRITES there via
        global-fallback, so migrating it would hoover live history into a
        visible dir most cwds cannot reach — and the stash would re-form."""
        stash = home / ".bon" / "handoffs"
        stash.mkdir(parents=True)
        (stash / "a.md").write_text(HANDOFF_BODY.format(p="global stash"))

        got = call_migrate(home, home)

        assert got["N"] == "0"
        assert got["FAILED"] == "0"
        assert (stash / "a.md").exists()
        assert not (home / "handoffs").exists(), "no uninvited handoffs/ in $HOME"

    def test_non_markdown_is_left_alone(self, tmp_path, home):
        """We only ever claimed *.md. Anything else stays put — and the husk
        survives with it rather than being silently emptied."""
        repo = make_repo(tmp_path / "repo")
        seed_legacy(repo, "a.md")
        (repo / ".bon" / "handoffs" / "notes.txt").write_text("not ours")

        call_migrate(repo, home)

        assert (repo / ".bon" / "handoffs" / "notes.txt").exists()
        assert (repo / "handoffs" / "a.md").exists()


# --- board_root --------------------------------------------------------------

class TestBoardRoot:
    def test_from_root(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo")
        assert call("board_root", repo, home) == str(repo)

    def test_from_room(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo")
        room = repo / "a" / "b"
        room.mkdir(parents=True)
        assert call("board_root", room, home) == str(repo)

    def test_no_board_emits_nothing(self, tmp_path, home):
        bare = tmp_path / "bare"
        bare.mkdir()
        subprocess.run(["git", "init", "-q", str(bare)], check=True)
        assert call("board_root", bare, home) == ""
