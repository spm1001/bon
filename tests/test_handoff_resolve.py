"""
Tests for the shared handoff / understanding.md resolver (scripts/lib-handoff.sh).

The resolver is the single source of truth that open-context.sh (READ) and
close-context.sh (WRITE) both source, so they cannot drift. It implements the
"visible substrate" convention: prose (handoffs/, understanding.md) lives
VISIBLE at the room where work happens, with .bon/ as the legacy fallback; the
board (.bon/items.jsonl) stays hidden + repo-global.

These source the lib in a bash subprocess and call its functions directly, so
the tests assert the actual contract rather than reproduced logic. HOME is
isolated to a throwaway dir so the machine's real ~/.bon/handoffs never leaks
into results.

Regression anchor: the 2026-06-17 stale-handoff bug — a newer handoff in a
visible root handoffs/ was invisible to /open because it only checked
.bon/handoffs/ (bon-zopopu).
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
    def test_visible_handoffs_preferred_over_bon(self, tmp_path, home):
        """The 06-17 convention: a visible handoffs/ wins over .bon/handoffs/."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True, bon_handoffs=True)
        assert call("handoff_write_dir", repo, home) == str(repo / "handoffs")

    def test_bon_only_repo_unchanged(self, tmp_path, home):
        """Backward compat: a .bon-only repo still writes to .bon/handoffs."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        assert call("handoff_write_dir", repo, home) == str(repo / ".bon" / "handoffs")

    def test_fresh_repo_defaults_to_bon(self, tmp_path, home):
        """No handoffs dir yet → legacy .bon/handoffs (the default, not visible)."""
        repo = make_repo(tmp_path / "repo")
        assert call("handoff_write_dir", repo, home) == str(repo / ".bon" / "handoffs")

    def test_room_with_handoffs_writes_to_room(self, tmp_path, home):
        """Launched in a room that hosts its own handoffs/ → nearest-room wins."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        room = repo / "work" / "room"
        (room / "handoffs").mkdir(parents=True)
        assert call("handoff_write_dir", room, home) == str(room / "handoffs")

    def test_room_without_handoffs_falls_to_board_root(self, tmp_path, home):
        """A bare room (no handoffs/) falls back to the board root's .bon."""
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        room = repo / "work" / "bare"
        room.mkdir(parents=True)
        assert call("handoff_write_dir", room, home) == str(repo / ".bon" / "handoffs")


# --- handoff_read_dirs -------------------------------------------------------

class TestHandoffReadDirs:
    def test_visible_listed_before_bon(self, tmp_path, home):
        """READ sees both, visible first, so a migration-in-progress repo ranks
        the genuinely-newest across locations (the 06-17 fix)."""
        repo = make_repo(tmp_path / "repo", visible_handoffs=True, bon_handoffs=True)
        got = lines("handoff_read_dirs", repo, home)
        assert got[0] == str(repo / "handoffs")
        assert str(repo / ".bon" / "handoffs") in got

    def test_bon_only_repo_lists_bon_then_global(self, tmp_path, home):
        repo = make_repo(tmp_path / "repo", bon_handoffs=True)
        got = lines("handoff_read_dirs", repo, home)
        assert got[0] == str(repo / ".bon" / "handoffs")
        assert got[-1] == str(home / ".bon" / "handoffs")  # global fallback last


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
