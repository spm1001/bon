"""Tests for arc work command."""
import json

import pytest

from conftest import run_arc


class TestWorkParseWhat:
    """Test parsing steps from --what field."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_parses_what(self, arc_dir_with_fixture, monkeypatch):
        """arc work parses numbered steps from --what."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # First, update arc-ccc to have numbered steps in --what
        result = run_arc(
            "edit", "arc-ccc",
            "--what", "1. Add login button 2. Add redirect flow 3. Test integration",
            cwd=arc_dir_with_fixture
        )
        assert result.returncode == 0

        # Now work on it
        result = run_arc("work", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "→ 1. Add login button [current]" in result.stdout
        assert "2. Add redirect flow" in result.stdout
        assert "3. Test integration" in result.stdout


class TestWorkExplicitSteps:
    """Test providing explicit steps."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_explicit_steps(self, arc_dir_with_fixture, monkeypatch):
        """arc work accepts explicit steps as arguments."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc(
            "work", "arc-ccc",
            "Step A", "Step B", "Step C",
            cwd=arc_dir_with_fixture
        )

        assert result.returncode == 0
        assert "→ 1. Step A [current]" in result.stdout
        assert "2. Step B" in result.stdout
        assert "3. Step C" in result.stdout


class TestWorkProseErrors:
    """Test error when --what has no numbered steps."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_prose_what_errors(self, arc_dir_with_fixture, monkeypatch):
        """arc work errors when --what has prose without numbers."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-ccc has "Login button in header, redirect flow" - no numbers
        result = run_arc("work", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "No numbered steps" in result.stderr


class TestWorkOutcomeErrors:
    """Test error when trying to add steps to outcome."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_outcome_errors(self, arc_dir_with_fixture, monkeypatch):
        """arc work errors on outcomes."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("work", "arc-aaa", "Step 1", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Tactical steps only for actions" in result.stderr


class TestWorkSerialEnforcement:
    """Test serial execution constraint."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_another_active_errors(self, arc_dir_with_fixture, monkeypatch):
        """arc work errors when another action has active steps."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-child already has tactical steps in progress
        # Try to create a new action and work on it
        result = run_arc(
            "new", "Another action",
            "--for", "arc-parent",
            "--why", "Test", "--what", "Test", "--done", "Test",
            cwd=arc_dir_with_fixture
        )
        assert result.returncode == 0

        # Get the new action ID
        new_id = result.stdout.strip().replace("Created: ", "")

        # Now try to work on the new action
        result = run_arc("work", new_id, "Step 1", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "arc-child has active steps" in result.stderr


class TestWorkProgressProtection:
    """Test protection of in-progress steps."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_progress_requires_force(self, arc_dir_with_fixture, monkeypatch):
        """arc work errors when steps in progress, unless --force."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-child has tactical at current=1
        result = run_arc("work", "arc-child", "New steps", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Steps in progress" in result.stderr
        assert "--force" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_force_restarts(self, arc_dir_with_fixture, monkeypatch):
        """arc work --force restarts steps."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc(
            "work", "arc-child", "--force",
            "New step A", "New step B",
            cwd=arc_dir_with_fixture
        )

        assert result.returncode == 0
        assert "→ 1. New step A [current]" in result.stdout


class TestWorkStatus:
    """Test arc work --status."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_status_shows_current(self, arc_dir_with_fixture, monkeypatch):
        """arc work --status shows current tactical state."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("work", "--status", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Working on: Test action with steps" in result.stdout
        assert "✓ 1. Step one" in result.stdout
        assert "→ 2. Step two [current]" in result.stdout
        assert "3. Step three" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_status_no_tactical(self, arc_dir_with_fixture, monkeypatch):
        """arc work --status when no tactical active."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("work", "--status", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "No active tactical steps" in result.stdout


class TestWorkClear:
    """Test arc work --clear."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_clear(self, arc_dir_with_fixture, monkeypatch):
        """arc work --clear removes tactical steps."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("work", "--clear", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Cleared tactical steps from arc-child" in result.stdout

        # Verify tactical removed
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert "tactical" not in child

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_clear_no_tactical(self, arc_dir_with_fixture, monkeypatch):
        """arc work --clear is silent when no tactical active."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("work", "--clear", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert result.stdout == ""


class TestWorkDoneAction:
    """Test errors on done actions."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_done_action_errors(self, arc_dir_with_fixture, monkeypatch):
        """arc work errors on already-done actions."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is done
        result = run_arc("work", "arc-bbb", "Step 1", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "already complete" in result.stderr


class TestWorkErrors:
    """Test various error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_not_found(self, arc_dir_with_fixture, monkeypatch):
        """arc work errors when item not found."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("work", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_work_not_initialized(self, tmp_path, monkeypatch):
        """arc work errors when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("work", "arc-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr

    def test_work_no_args(self, arc_dir, monkeypatch):
        """arc work with no args errors."""
        monkeypatch.chdir(arc_dir)

        result = run_arc("work", cwd=arc_dir)

        assert result.returncode == 1
        assert "Usage:" in result.stderr
