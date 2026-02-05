"""Tests for arc status command."""
import pytest
from conftest import run_arc


class TestStatusBasic:
    """Test basic arc status behavior."""

    def test_status_empty(self, arc_dir, monkeypatch):
        """arc status on empty repo."""
        monkeypatch.chdir(arc_dir)

        result = run_arc("status", cwd=arc_dir)

        assert result.returncode == 0
        assert "Arc status (prefix: arc)" in result.stdout
        assert "Outcomes:   0 open, 0 done" in result.stdout
        assert "Actions:    0 open (0 ready, 0 waiting), 0 done" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_status_single_outcome(self, arc_dir_with_fixture, monkeypatch):
        """arc status with one outcome."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("status", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Outcomes:   1 open, 0 done" in result.stdout
        assert "Actions:    0 open" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_status_with_actions(self, arc_dir_with_fixture, monkeypatch):
        """arc status with actions (one done, one open)."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("status", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Outcomes:   1 open, 0 done" in result.stdout
        # 1 open action (arc-ccc), 1 done action (arc-bbb)
        assert "Actions:    1 open (1 ready, 0 waiting), 1 done" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_status_with_waiting(self, arc_dir_with_fixture, monkeypatch):
        """arc status shows waiting count."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("status", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        # arc-bbb is waiting, arc-ccc is ready
        assert "Actions:    2 open (1 ready, 1 waiting), 0 done" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["standalone_actions"], indirect=True)
    def test_status_standalone(self, arc_dir_with_fixture, monkeypatch):
        """arc status shows standalone count."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("status", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Standalone: 2 open" in result.stdout


class TestStatusErrors:
    """Test arc status error cases."""

    def test_status_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("status", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr
