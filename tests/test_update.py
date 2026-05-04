"""Tests for bon update command."""
import shutil
import subprocess

import pytest

from conftest import run_bon


def _bon_is_uv_tool() -> bool:
    """Return True if bon is installed as a uv tool (not just present in dev venv).

    shutil.which("bon") is insufficient — it finds .venv/bin/bon when the dev venv
    is activated, even though bon isn't a uv tool. `bon update` calls
    `uv tool upgrade bon`, which requires a uv tool install — not just a venv binary.
    """
    try:
        r = subprocess.run(["uv", "tool", "list"], capture_output=True, text=True, timeout=5)
        return "bon" in r.stdout
    except Exception:
        return False


def test_update_shows_in_help():
    """bon update should appear in help output."""
    result = run_bon("--help")
    assert "update" in result.stdout


def test_update_no_bon_dir_needed(tmp_path):
    """bon update should work without .bon/ directory (it's a meta-command)."""
    result = run_bon("update", cwd=tmp_path)
    # Should not fail with "not initialized" error
    assert "Not a bon project" not in result.stderr


@pytest.mark.skipif(not _bon_is_uv_tool(), reason="bon not installed as uv tool")
def test_update_runs():
    """bon update re-installs from source."""
    result = run_bon("update")
    assert result.returncode == 0
    assert "Current: bon" in result.stdout
