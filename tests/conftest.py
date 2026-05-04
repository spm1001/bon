"""Pytest configuration and fixtures."""
import subprocess
import sys
from pathlib import Path

import pytest

from bon.storage import _reset_backend, _reset_data_dir


@pytest.fixture(autouse=True)
def _reset_storage_cache():
    """Reset cached data dir and backend between tests so monkeypatch.chdir works."""
    _reset_data_dir()
    _reset_backend()
    yield
    _reset_data_dir()
    _reset_backend()


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bon_dir(tmp_path):
    """Create temp dir with initialized .bon/."""
    bon_path = tmp_path / ".bon"
    bon_path.mkdir()
    (bon_path / "items.jsonl").touch()
    (bon_path / "prefix").write_text("bon")
    return tmp_path


@pytest.fixture
def bon_dir_with_fixture(request, tmp_path, fixtures_dir):
    """Load a specific fixture into .bon/.

    Usage:
        @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
        def test_something(bon_dir_with_fixture):
            ...
    """
    fixture_name = request.param
    bon_path = tmp_path / ".bon"
    bon_path.mkdir()

    fixture_file = fixtures_dir / f"{fixture_name}.jsonl"
    if fixture_file.exists():
        content = fixture_file.read_text()
    else:
        content = ""

    (bon_path / "items.jsonl").write_text(content)
    (bon_path / "prefix").write_text("bon")
    return tmp_path


def run_bon(*args, cwd=None, env=None, input=None):
    """Run bon CLI and return result."""
    result = subprocess.run(
        [sys.executable, "-m", "bon.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        input=input,
    )
    return result
