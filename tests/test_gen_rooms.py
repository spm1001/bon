"""Tests for the rooms.md generator (scripts/gen-rooms.py).

A "room" is any directory containing a CLAUDE.md. The generator walks a repo's
**/CLAUDE.md, extracts each sub-room's path + a one-line description (the first
prose sentence under the H1), and writes a flat, sorted, drift-proof rooms.md
at the repo root. It is generic across any multi-room repo (bon-walile, under
bon-gopewu).

These invoke the real script via subprocess so the tests assert the actual
entry point rather than reproduced logic.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "gen-rooms.py"


def run_gen(repo, *args):
    """Run gen-rooms.py against repo; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, str(repo)],
        capture_output=True,
        text=True,
    )


def room(repo, relpath, body):
    """Create repo/<relpath>/CLAUDE.md with the given body."""
    d = repo / relpath if relpath else repo
    d.mkdir(parents=True, exist_ok=True)
    (d / "CLAUDE.md").write_text(body, encoding="utf-8")


def test_lists_subrooms_sorted_with_oneliners(tmp_path):
    room(tmp_path, "", "# root\n\nThe orientation doc.\n")
    room(tmp_path, "work", "# work/\n\nITV-context work knowledge.\n")
    room(tmp_path, "personal/Car", "# personal/Car/\n\nVehicle records.\n")

    result = run_gen(tmp_path)
    assert result.returncode == 0
    rooms = (tmp_path / "rooms.md").read_text()

    # Both sub-rooms present, with their one-liners
    assert "[`personal/Car/`](personal/Car/CLAUDE.md) — Vehicle records." in rooms
    assert "[`work/`](work/CLAUDE.md) — ITV-context work knowledge." in rooms
    # Alphabetical order: personal/ before work/
    assert rooms.index("personal/Car/") < rooms.index("work/")


def test_repo_root_claude_md_is_skipped(tmp_path):
    """The root CLAUDE.md hosts the index — it is not itself a listed room."""
    room(tmp_path, "", "# root\n\nOrientation for the whole repo.\n")
    room(tmp_path, "sub", "# sub/\n\nA real sub-room.\n")

    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()

    assert "sub/" in rooms
    # The root entry would be "(./CLAUDE.md)" or a "[`/`]" line — neither appears
    assert "](CLAUDE.md)" not in rooms
    assert "Orientation for the whole repo" not in rooms


def test_oneliner_trims_to_first_sentence(tmp_path):
    room(tmp_path, "x", "# x/\n\nSameer's wife. Sensitive — medical only.\n")
    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "Sameer's wife." in rooms
    assert "Sensitive" not in rooms


def test_skips_blockquote_and_banner_to_reach_prose(tmp_path):
    """A status banner (>) or HTML comment before the prose must be skipped."""
    body = "# work/\n\n> **Status:** folded in 2026-05-31\n\nThe real description.\n"
    room(tmp_path, "work", body)
    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "The real description." in rooms
    assert "Status" not in rooms


def test_no_subrooms_message(tmp_path):
    room(tmp_path, "", "# root\n\nOnly a root here.\n")
    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "_No sub-rooms found._" in rooms


def test_skips_git_and_bon_internal_claude_md(tmp_path):
    """CLAUDE.md inside .git/ or .bon/ is internal noise, not a room."""
    room(tmp_path, "real", "# real/\n\nA genuine room.\n")
    room(tmp_path, ".git/hooks", "# hooks\n\nNot a room.\n")
    room(tmp_path, ".bon", "# bon\n\nNot a room either.\n")
    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "real/" in rooms
    assert ".git" not in rooms
    assert "Not a room" not in rooms


def test_check_mode_detects_stale_then_clean(tmp_path):
    room(tmp_path, "sub", "# sub/\n\nA room.\n")

    # Missing rooms.md → stale → exit 1, writes nothing
    stale = run_gen(tmp_path, "--check")
    assert stale.returncode == 1
    assert not (tmp_path / "rooms.md").exists()

    # Generate, then --check is clean (idempotent)
    assert run_gen(tmp_path).returncode == 0
    clean = run_gen(tmp_path, "--check")
    assert clean.returncode == 0


def test_idempotent_write_leaves_content_identical(tmp_path):
    room(tmp_path, "sub", "# sub/\n\nA room.\n")
    run_gen(tmp_path)
    first = (tmp_path / "rooms.md").read_text()
    run_gen(tmp_path)
    second = (tmp_path / "rooms.md").read_text()
    assert first == second


def test_adding_a_room_updates_the_index(tmp_path):
    """The drift-proof property: a new room appears on the next run."""
    room(tmp_path, "one", "# one/\n\nFirst room.\n")
    run_gen(tmp_path)
    assert "two/" not in (tmp_path / "rooms.md").read_text()

    room(tmp_path, "two", "# two/\n\nSecond room.\n")
    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "one/" in rooms and "two/" in rooms


def test_heading_fallback_when_no_prose(tmp_path):
    """A CLAUDE.md with only a heading falls back to the heading text."""
    room(tmp_path, "bare", "# bare-room/\n")
    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "bare-room/" in rooms
