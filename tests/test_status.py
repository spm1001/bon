"""Tests for bon status command."""
import pytest
from conftest import run_bon


class TestStatusBasic:
    """Test basic bon status behavior."""

    def test_status_empty(self, bon_dir, monkeypatch):
        """bon status on empty repo."""
        monkeypatch.chdir(bon_dir)

        result = run_bon("status", cwd=bon_dir)

        assert result.returncode == 0
        assert "Bon status (prefix: bon)" in result.stdout
        assert "Outcomes:   0 open, 0 done" in result.stdout
        assert "Actions:    0 open (0 ready, 0 waiting), 0 done" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_status_single_outcome(self, bon_dir_with_fixture, monkeypatch):
        """bon status with one outcome."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("status", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Outcomes:   1 open, 0 done" in result.stdout
        assert "Actions:    0 open" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_status_with_actions(self, bon_dir_with_fixture, monkeypatch):
        """bon status with actions (one done, one open)."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("status", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Outcomes:   1 open, 0 done" in result.stdout
        # 1 open action (bon-ccc), 1 done action (bon-bbb)
        assert "Actions:    1 open (1 ready, 0 waiting), 1 done" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_status_with_waiting(self, bon_dir_with_fixture, monkeypatch):
        """bon status shows waiting count."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("status", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        # bon-bbb is waiting, bon-ccc is ready
        assert "Actions:    2 open (1 ready, 1 waiting), 0 done" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["standalone_actions"], indirect=True)
    def test_status_standalone(self, bon_dir_with_fixture, monkeypatch):
        """bon status shows standalone count."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("status", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Standalone: 2 open" in result.stdout


class TestStatusErrors:
    """Test bon status error cases."""

    def test_status_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("status", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr
