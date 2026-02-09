"""Tests for arc show command."""
import pytest
from conftest import run_arc


class TestShowOutcome:
    """Test arc show for outcomes."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_show_outcome_with_actions(self, arc_dir_with_fixture, monkeypatch):
        """arc show displays outcome with all its actions."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        # Check header
        assert "○ User auth (arc-aaa)" in result.stdout
        assert "Type: outcome" in result.stdout
        assert "Status: open" in result.stdout
        assert "Created:" in result.stdout

        # Check brief
        assert "--why: New devs struggling with auth setup" in result.stdout
        assert "--what: Simplified OAuth flow" in result.stdout
        assert "--done: Setup takes < 10 minutes" in result.stdout

        # Check actions
        assert "Actions:" in result.stdout
        assert "1. ✓ Add endpoint (arc-bbb)" in result.stdout
        assert "2. ○ Add UI (arc-ccc)" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_outcome_no_actions(self, arc_dir_with_fixture, monkeypatch):
        """arc show displays outcome without actions section when empty."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "○ User auth (arc-aaa)" in result.stdout
        assert "Actions:" not in result.stdout  # No actions section


class TestShowAction:
    """Test arc show for actions."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_show_action(self, arc_dir_with_fixture, monkeypatch):
        """arc show displays action details."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "✓ Add endpoint (arc-bbb)" in result.stdout
        assert "Type: action" in result.stdout
        assert "Status: done" in result.stdout
        assert "Actions:" not in result.stdout  # Actions don't show nested actions

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_show_waiting_action(self, arc_dir_with_fixture, monkeypatch):
        """arc show displays waiting status."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Waiting for: arc-ccc" in result.stdout


class TestShowErrors:
    """Test arc show error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    def test_show_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("show", "arc-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestShowCurrent:
    """Test arc show --current with active tactical steps."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_show_current_with_active_tactical(self, arc_dir_with_fixture, monkeypatch):
        """arc show --current outputs working line and tactical steps."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "--current", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Working: Test action with steps (arc-child)" in result.stdout
        # Step 1 (index 0) completed, step 2 (index 1) current, step 3 pending
        assert "✓ 1. Step one" in result.stdout
        assert "→ 2. Step two [current]" in result.stdout
        assert "3. Step three" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_show_current_no_active_tactical(self, arc_dir_with_fixture, monkeypatch):
        """arc show --current silently exits when no tactical steps active."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "--current", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert result.stdout == ""


class TestShowPrefixTolerant:
    """Test prefix-tolerant ID matching."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_by_suffix(self, arc_dir_with_fixture, monkeypatch):
        """Can show item by suffix only."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "User auth" in result.stdout
