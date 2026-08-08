"""Tests for skills/review/scripts/orphans.py — the citation cross-check (bon-nenine)."""
import os
import subprocess
import sys
from pathlib import Path

from conftest import run_bon

SCRIPT = Path(__file__).parent.parent / "skills" / "review" / "scripts" / "orphans.py"


def git(*args, cwd):
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@test", *args],
        capture_output=True, text=True, cwd=cwd, check=True,
    )


def run_orphans(repo, *args):
    env = dict(os.environ, BON_CMD=f"{sys.executable} -m bon.cli")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        capture_output=True, text=True, env=env,
    )


def make_repo(tmp_path):
    """Git repo with a board: one open item, one done item."""
    run_bon("init", "--prefix", "tst", cwd=tmp_path)
    open_id = run_bon("new", "Open thing", "--why", "w", "--what", "x",
                      "--done", "d", "-q", cwd=tmp_path).stdout.strip()
    done_id = run_bon("new", "Done thing", "--why", "w", "--what", "x",
                      "--done", "d", "-q", cwd=tmp_path).stdout.strip()
    run_bon("done", done_id, cwd=tmp_path)
    git("init", "-q", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("1")
    git("add", "-A", cwd=tmp_path)
    git("commit", "-q", "-m", f"start work ({open_id})", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("2")
    git("commit", "-q", "-am", f"finish other thing ({done_id})", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("3")
    git("commit", "-q", "-am", "cite a typo (tst-zzzzzz)", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("4")
    git("commit", "-q", "-am", "cross-board ref (oth-abcdef)", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("5")
    git("commit", "-q", "-am", "no citation here", cwd=tmp_path)
    return open_id, done_id


def test_buckets_and_coverage(tmp_path):
    open_id, done_id = make_repo(tmp_path)
    result = run_orphans(tmp_path)
    assert result.returncode == 0, result.stderr
    out = result.stdout

    # Open item cited -> flagged for a verdict, with title and last commit
    assert "CITED-BUT-OPEN" in out
    assert open_id in out
    assert "Open thing" in out

    # Done item cited -> healthy, never listed in the open bucket
    section = out.split("UNKNOWN-ID")[0]
    assert done_id not in section
    assert "1 cited items already closed (healthy)" in out

    # Typo with our prefix -> unknown; other prefix -> cross-board
    assert "tst-zzzzzz" in out.split("UNKNOWN-ID")[1].split("CROSS-BOARD")[0]
    assert "oth-abcdef" in out.split("CROSS-BOARD")[1]

    # 4 of 5 commits cite something
    assert "Coverage: 4/5" in out


def test_board_read_failure_is_loud(tmp_path):
    """No board -> loud exit, never a clean-looking empty report."""
    git("init", "-q", cwd=tmp_path)
    (tmp_path / "f.txt").write_text("1")
    git("add", "-A", cwd=tmp_path)
    git("commit", "-q", "-m", "no board here", cwd=tmp_path)
    result = run_orphans(tmp_path)
    assert result.returncode == 2
    assert "board read failed" in result.stderr


def test_legacy_short_ids_ignored(tmp_path):
    """Legacy 3-char IDs predate the convention; the regex must not match them."""
    open_id, _ = make_repo(tmp_path)
    (tmp_path / "f.txt").write_text("6")
    git("commit", "-q", "-am", "legacy shape (tst-qa6)", cwd=tmp_path)
    result = run_orphans(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "tst-qa6" not in result.stdout
