"""Tests for arc step command."""
import json
import re

import pytest
from conftest import run_arc

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestStepAdvances:
    """Test basic step advancement."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_step_advances(self, arc_dir_with_fixture, monkeypatch):
        """arc step increments current."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # action_with_tactical has current=1, meaning step 1 is done, on step 2
        result = run_arc("step", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "✓ 1. Step one" in result.stdout
        assert "✓ 2. Step two" in result.stdout
        assert "→ 3. Step three [current]" in result.stdout
        assert "Next: Step three" in result.stdout

        # Verify storage updated
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert child["tactical"]["current"] == 2


class TestStepShowsNext:
    """Test output shows next step."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_step_shows_next(self, arc_dir_with_fixture, monkeypatch):
        """arc step shows next step to work on."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("step", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Next: Step three" in result.stdout


class TestStepFinalCompletes:
    """Test auto-completion on final step."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_step_final_completes(self, arc_dir_with_fixture, monkeypatch):
        """arc step on final step auto-completes action."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Step twice to complete (current=1, need to reach 3)
        run_arc("step", cwd=arc_dir_with_fixture)
        result = run_arc("step", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "✓ 1. Step one" in result.stdout
        assert "✓ 2. Step two" in result.stdout
        assert "✓ 3. Step three" in result.stdout
        assert "Action arc-child complete." in result.stdout

        # Verify action is done
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert child["status"] == "done"
        assert "done_at" in child


class TestStepUnblocksWaiters:
    """Test unblocking on completion."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_step_unblocks_waiters(self, arc_dir_with_fixture, monkeypatch):
        """Completing via arc step unblocks waiters."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Create another action waiting on arc-child
        result = run_arc(
            "new", "Waiting action",
            "--for", "arc-parent",
            "--why", "Test", "--what", "Test", "--done", "Test",
            cwd=arc_dir_with_fixture
        )
        assert result.returncode == 0
        waiter_id = result.stdout.strip().replace("Created: ", "")

        # Mark it as waiting for arc-child
        result = run_arc("wait", waiter_id, "arc-child", cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        # Complete arc-child via steps
        run_arc("step", cwd=arc_dir_with_fixture)
        run_arc("step", cwd=arc_dir_with_fixture)

        # Verify waiter is unblocked
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        waiter = next(i for i in items if i["id"] == waiter_id)
        assert waiter["waiting_for"] is None


class TestStepNoTacticalErrors:
    """Test error when no tactical active."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_step_no_tactical_errors(self, arc_dir_with_fixture, monkeypatch):
        """arc step errors when no tactical in progress."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("step", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "No steps in progress" in result.stderr
        assert "bon work <id>" in result.stderr


class TestStepErrors:
    """Test various error cases."""

    def test_step_not_initialized(self, tmp_path, monkeypatch):
        """arc step errors when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("step", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestStepUpdatedAt:
    """Verify step sets updated_at timestamp."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_step_sets_updated_at(self, arc_dir_with_fixture, monkeypatch):
        """arc step sets updated_at on the item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("step", cwd=arc_dir_with_fixture)

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert "updated_at" in child
        assert ISO_RE.match(child["updated_at"])


class TestStepSkip:
    """Test --skip flag."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_skip_advances_with_reason(self, arc_dir_with_fixture, monkeypatch):
        """bon step --skip records reason and advances."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Fixture has current=1 (on step 2). Skip it.
        result = run_arc("step", "--skip", "needs manual test", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "⊘ 2. Step two [skipped: needs manual test]" in result.stdout
        assert "→ 3. Step three [current]" in result.stdout

        # Verify storage
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert child["tactical"]["skipped"] == {"1": "needs manual test"}
        assert child["tactical"]["current"] == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_skip_final_step_still_completes(self, arc_dir_with_fixture, monkeypatch):
        """Skipping the final step still auto-completes by default."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Advance to step 3 (final), then skip it
        run_arc("step", cwd=arc_dir_with_fixture)
        result = run_arc("step", "--skip", "can't test yet", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Action arc-child complete." in result.stdout
        assert "⊘ 3. Step three [skipped: can't test yet]" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_skip_combined_with_no_complete(self, arc_dir_with_fixture, monkeypatch):
        """--skip and --no-complete together: skip final step, don't complete action."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Advance to step 3 (final), then skip with --no-complete
        run_arc("step", cwd=arc_dir_with_fixture)
        result = run_arc("step", "--skip", "needs phone test", "--no-complete", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "⊘ 3. Step three [skipped: needs phone test]" in result.stdout
        assert "--no-complete" in result.stdout

        # Action should still be open
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert child["status"] == "open"


class TestStepNoComplete:
    """Test --no-complete flag."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_no_complete_prevents_auto_complete(self, arc_dir_with_fixture, monkeypatch):
        """--no-complete on final step leaves action open."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Advance to final step, then complete with --no-complete
        run_arc("step", cwd=arc_dir_with_fixture)
        result = run_arc("step", "--no-complete", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "✓ 3. Step three" in result.stdout
        assert "left open (--no-complete)" in result.stdout

        # Action should still be open
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "arc-child")
        assert child["status"] == "open"
        assert "done_at" not in child

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_no_complete_does_not_unblock_waiters(self, arc_dir_with_fixture, monkeypatch):
        """--no-complete doesn't unblock items waiting on this action."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Create a waiter
        result = run_arc(
            "new", "Waiting action",
            "--for", "arc-parent",
            "--why", "Test", "--what", "Test", "--done", "Test",
            cwd=arc_dir_with_fixture
        )
        waiter_id = result.stdout.strip().replace("Created: ", "")
        run_arc("wait", waiter_id, "arc-child", cwd=arc_dir_with_fixture)

        # Complete all steps with --no-complete
        run_arc("step", cwd=arc_dir_with_fixture)
        run_arc("step", "--no-complete", cwd=arc_dir_with_fixture)

        # Waiter should still be blocked
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        waiter = next(i for i in items if i["id"] == waiter_id)
        assert waiter["waiting_for"] == "arc-child"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_no_complete_on_non_final_step_is_ignored(self, arc_dir_with_fixture, monkeypatch):
        """--no-complete on a non-final step has no effect (normal advance)."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("step", "--no-complete", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Next: Step three" in result.stdout
