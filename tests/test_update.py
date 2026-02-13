"""Tests for arc update command."""
import shutil

import pytest

from conftest import run_arc


def test_update_shows_in_help():
    """arc update should appear in help output."""
    result = run_arc("--help")
    assert "update" in result.stdout


def test_update_no_arc_dir_needed(tmp_path):
    """arc update should work without .arc/ directory (it's a meta-command)."""
    result = run_arc("update", cwd=tmp_path)
    # Should not fail with "not initialized" error
    assert "Not an arc project" not in result.stderr


@pytest.mark.skipif(not shutil.which("uv"), reason="uv not available")
def test_update_runs():
    """arc update re-installs from source."""
    result = run_arc("update")
    assert result.returncode == 0
    assert "Current: arc" in result.stdout
