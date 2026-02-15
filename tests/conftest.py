"""Pytest configuration and fixtures."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def arc_dir(tmp_path):
    """Create temp dir with initialized .bon/."""
    arc_path = tmp_path / ".bon"
    arc_path.mkdir()
    (arc_path / "items.jsonl").touch()
    (arc_path / "prefix").write_text("arc")
    return tmp_path


@pytest.fixture
def arc_dir_with_fixture(request, tmp_path, fixtures_dir):
    """Load a specific fixture into .bon/.

    Usage:
        @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
        def test_something(arc_dir_with_fixture):
            ...
    """
    fixture_name = request.param
    arc_path = tmp_path / ".bon"
    arc_path.mkdir()

    fixture_file = fixtures_dir / f"{fixture_name}.jsonl"
    if fixture_file.exists():
        content = fixture_file.read_text()
    else:
        content = ""

    (arc_path / "items.jsonl").write_text(content)
    (arc_path / "prefix").write_text("arc")
    return tmp_path


def run_arc(*args, cwd=None, env=None, input=None):
    """Run arc CLI and return result."""
    result = subprocess.run(
        [sys.executable, "-m", "bon.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        input=input,
    )
    return result
