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


def git(repo, *args):
    """Run git in repo (init/add only — no identity needed, no commits)."""
    subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True
    )


def test_ignored_room_is_flagged_with_culprit_line(tmp_path):
    """A room hidden by a gitignore pattern gets a loud inline annotation.

    The notes-laninu shape: a bare `mise/` pattern matches at any depth and
    silently swallows a real room, which then exists on one machine only
    while rooms.md advertises it everywhere.
    """
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "practices/mise", "# mise\n\nField station.\n")
    room(tmp_path, "work", "# work\n\nHealthy room.\n")
    (tmp_path / ".gitignore").write_text("mise/\n")
    git(tmp_path, "init", "-q")

    result = run_gen(tmp_path)
    assert result.returncode == 0  # write path stays non-fatal
    assert "WARNING" in result.stderr
    rooms = (tmp_path / "rooms.md").read_text()
    mise_line = next(l for l in rooms.splitlines() if "practices/mise/" in l)
    assert "IGNORED" in mise_line
    assert ".gitignore:1 mise/" in mise_line
    work_line = next(l for l in rooms.splitlines() if "work/`" in l)
    assert "IGNORED" not in work_line


def test_untracked_but_not_ignored_room_is_not_flagged(tmp_path):
    """A just-minted room awaiting its first commit is routine, not a defect."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "fresh", "# fresh\n\nNewly minted.\n")
    git(tmp_path, "init", "-q")

    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "fresh/" in rooms
    assert "IGNORED" not in rooms


def test_tracked_room_matching_ignore_pattern_is_not_flagged(tmp_path):
    """A force-added CLAUDE.md is visible to git despite the pattern."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "practices/mise", "# mise\n\nField station.\n")
    (tmp_path / ".gitignore").write_text("mise/\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-f", "practices/mise/CLAUDE.md")

    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "practices/mise/" in rooms
    assert "IGNORED" not in rooms


def test_check_mode_fails_on_ignored_room(tmp_path):
    """--check treats a git-ignored room as an integrity failure for CI."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "practices/mise", "# mise\n\nField station.\n")
    (tmp_path / ".gitignore").write_text("mise/\n")
    git(tmp_path, "init", "-q")

    run_gen(tmp_path)  # rooms.md now current, annotation included
    result = run_gen(tmp_path, "--check")
    assert result.returncode == 1
    assert "ignored" in result.stderr.lower()


def test_non_git_directory_skips_integrity_check(tmp_path):
    """Outside a git work tree the generator behaves exactly as before."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "sub", "# sub\n\nA room.\n")

    result = run_gen(tmp_path)
    assert result.returncode == 0
    rooms = (tmp_path / "rooms.md").read_text()
    assert "sub/" in rooms
    assert "IGNORED" not in rooms


def test_repo_pairing_emitted_beside_description(tmp_path):
    """A room's `**Repo:**` line rides into rooms.md verbatim (bon-jezahi)."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(
        tmp_path,
        "practices/mise",
        "# mise\n\n**Repo:** spm1001/mise-en-space\n\nField station.\n",
    )

    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    line = next(l for l in rooms.splitlines() if "practices/mise/" in l)
    assert "· **repo:** spm1001/mise-en-space" in line
    assert "Field station." in line  # description survives beside it


def test_repo_pairing_cross_cutting_is_verbatim(tmp_path):
    """`cross-cutting — <why>` is a real finding, emitted as written."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(
        tmp_path,
        "practices/briefing",
        "# briefing\n\nThe census.\n\n**Repo:** cross-cutting — many implementations, owned by none\n",
    )

    run_gen(tmp_path)
    rooms = (tmp_path / "rooms.md").read_text()
    assert "· **repo:** cross-cutting — many implementations, owned by none" in rooms


def test_room_without_repo_line_has_no_pairing(tmp_path):
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "plain", "# plain\n\nNo pairing here.\n")

    run_gen(tmp_path)
    # Assert on the room lines, not the whole file — the generated header
    # legitimately mentions `· **repo:**` while documenting the convention.
    room_lines = [
        l for l in (tmp_path / "rooms.md").read_text().splitlines()
        if l.startswith("- ")
    ]
    assert room_lines  # positive control: the index has rooms at all
    assert not any("· **repo:**" in l for l in room_lines)


def test_malformed_repo_line_degrades_to_absent(tmp_path):
    """A bare `**Repo:**` label with no value must not break the index."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "broken", "# broken\n\n**Repo:**\n\nStill a room.\n")
    room(tmp_path, "fine", "# fine\n\nHealthy.\n")

    result = run_gen(tmp_path)
    assert result.returncode == 0
    rooms = (tmp_path / "rooms.md").read_text()
    assert "broken/" in rooms and "fine/" in rooms
    room_lines = [l for l in rooms.splitlines() if l.startswith("- ")]
    assert room_lines
    assert not any("· **repo:**" in l for l in room_lines)


def test_write_refuses_hand_authored_rooms_md_without_adopt(tmp_path):
    """The adoption guard: creating rooms.md by hand can no longer arm the
    regen against its own author (the 2026-08-08 incident)."""
    room(tmp_path, "", "# root\n\nRoot.\n")
    room(tmp_path, "sub", "# sub\n\nA room.\n")
    hand = "# My hand-written index\n\n| room | repo |\n|---|---|\n"
    (tmp_path / "rooms.md").write_text(hand)

    refused = run_gen(tmp_path)
    assert refused.returncode == 2
    assert "hand-authored" in refused.stderr
    assert (tmp_path / "rooms.md").read_text() == hand  # untouched

    adopted = run_gen(tmp_path, "--adopt")
    assert adopted.returncode == 0
    assert "generated by gen-rooms.py" in (tmp_path / "rooms.md").read_text()
