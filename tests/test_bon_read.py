"""
Tests for scripts/bon-read.sh edge cases.

Verifies jq queries handle: empty projects, all-done items, malformed JSONL,
missing .bon/, items with/without tactical steps, waiting_for, standalone
outcomes, and mixed states.

These are the mechanical edge cases identified when bon-read.sh was written
against a single project's data. The script must degrade gracefully (empty
output, exit 0) for unexpected input — never produce wrong output silently.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
BON_READ = REPO_ROOT / "scripts" / "bon-read.sh"


def run_bon_read(tmp_path: Path, jsonl_content: str, command: str) -> subprocess.CompletedProcess:
    """Set up temp .bon/ directory and run bon-read.sh with given command."""
    bon_dir = tmp_path / ".bon"
    bon_dir.mkdir(exist_ok=True)
    (bon_dir / "items.jsonl").write_text(jsonl_content)
    return subprocess.run(
        [str(BON_READ), command],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )


def make_jsonl(*items: dict) -> str:
    """Convert dicts to newline-delimited JSON."""
    return "\n".join(json.dumps(item) for item in items) + "\n" if items else ""


# --- Test data ---

OPEN_OUTCOME = {
    "id": "test-abc",
    "type": "outcome",
    "title": "Test outcome",
    "status": "open",
    "order": 1,
}

DONE_OUTCOME = {
    "id": "test-done",
    "type": "outcome",
    "title": "Done outcome",
    "status": "done",
    "order": 1,
}

OPEN_ACTION = {
    "id": "test-act1",
    "type": "action",
    "title": "Open action",
    "status": "open",
    "parent": "test-abc",
    "order": 1,
}

DONE_ACTION = {
    "id": "test-act2",
    "type": "action",
    "title": "Done action",
    "status": "done",
    "parent": "test-abc",
    "order": 2,
}

WAITING_ACTION = {
    "id": "test-wait",
    "type": "action",
    "title": "Waiting action",
    "status": "open",
    "parent": "test-abc",
    "order": 3,
    "waiting_for": "something",
}

TACTICAL_ACTION = {
    "id": "test-tac",
    "type": "action",
    "title": "Tactical action",
    "status": "open",
    "parent": "test-abc",
    "order": 4,
    "tactical": {
        "steps": ["First step", "Second step", "Third step"],
        "current": 1,
    },
}


# --- Tests ---


class TestNoDataDirectory:
    """When neither .bon/ nor .arc/ exists, script exits silently."""

    @pytest.mark.parametrize("command", ["list", "ready", "current"])
    def test_exits_zero_no_output(self, tmp_path, command):
        result = subprocess.run(
            [str(BON_READ), command],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""


class TestEmptyJsonl:
    """Empty items.jsonl — all commands should produce nothing."""

    @pytest.mark.parametrize("command", ["list", "ready", "current"])
    def test_empty_file_no_output(self, tmp_path, command):
        result = run_bon_read(tmp_path, "", command)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestAllDoneItems:
    """When every item is done, nothing should appear."""

    def test_list_empty(self, tmp_path):
        data = make_jsonl(
            DONE_OUTCOME,
            {**DONE_ACTION, "parent": "test-done"},
        )
        result = run_bon_read(tmp_path, data, "list")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_ready_empty(self, tmp_path):
        data = make_jsonl(
            DONE_OUTCOME,
            {**DONE_ACTION, "parent": "test-done"},
        )
        result = run_bon_read(tmp_path, data, "ready")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_current_empty(self, tmp_path):
        data = make_jsonl(
            DONE_OUTCOME,
            {**DONE_ACTION, "parent": "test-done"},
        )
        result = run_bon_read(tmp_path, data, "current")
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestMalformedJsonl:
    """Malformed JSONL lines — script must not crash."""

    def test_malformed_in_slurp_mode(self, tmp_path):
        """One bad line silences all output in slurp mode (list/ready).

        This is a known limitation: jq -s fails on the entire input if any
        line is invalid JSON. The || true catches the error gracefully.
        """
        data = json.dumps(OPEN_OUTCOME) + "\nINVALID JSON\n" + json.dumps(OPEN_ACTION) + "\n"
        result = run_bon_read(tmp_path, data, "list")
        assert result.returncode == 0
        # No assertion on stdout content — behaviour is that output is lost

    def test_malformed_in_current(self, tmp_path):
        """Malformed line in non-slurp mode (current command)."""
        data = json.dumps(OPEN_OUTCOME) + "\nINVALID JSON\n" + json.dumps(TACTICAL_ACTION) + "\n"
        result = run_bon_read(tmp_path, data, "current")
        assert result.returncode == 0
        # jq may produce partial output before failing — either way, no crash


class TestListCommand:
    """The list command shows open outcomes with all their actions."""

    def test_outcome_with_mixed_actions(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION, DONE_ACTION)
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert any("Test outcome" in l for l in lines)
        assert any("Open action" in l for l in lines)
        assert any("Done action" in l for l in lines)

    def test_done_actions_have_checkmark(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, DONE_ACTION)
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        done_line = [l for l in lines if "Done action" in l][0]
        assert "\u2713" in done_line  # ✓

    def test_open_actions_have_circle(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION)
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        open_line = [l for l in lines if "Open action" in l][0]
        assert "\u25cb" in open_line  # ○

    def test_standalone_outcome(self, tmp_path):
        """Outcome with no children shows just the outcome line."""
        data = make_jsonl(OPEN_OUTCOME)
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert len(lines) == 1
        assert "Test outcome" in lines[0]

    def test_preserves_order(self, tmp_path):
        """Actions sorted by order field."""
        data = make_jsonl(
            OPEN_OUTCOME,
            {**OPEN_ACTION, "order": 2, "title": "Second"},
            {**OPEN_ACTION, "id": "test-first", "order": 1, "title": "First"},
        )
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        action_lines = [l for l in lines if l.startswith("  ")]
        first_idx = next(i for i, l in enumerate(action_lines) if "First" in l)
        second_idx = next(i for i, l in enumerate(action_lines) if "Second" in l)
        assert first_idx < second_idx

    def test_uses_order_field_for_numbering(self, tmp_path):
        """List uses item's .order field, not sequential index."""
        data = make_jsonl(
            OPEN_OUTCOME,
            {**OPEN_ACTION, "order": 3, "title": "Third action"},
        )
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        action_line = [l for l in lines if "Third action" in l][0]
        assert "3." in action_line

    def test_includes_ids(self, tmp_path):
        """Output includes item IDs in parentheses."""
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION)
        result = run_bon_read(tmp_path, data, "list")
        assert "(test-abc)" in result.stdout
        assert "(test-act1)" in result.stdout

    def test_multiple_outcomes(self, tmp_path):
        """Multiple open outcomes shown in order."""
        second_outcome = {
            "id": "test-xyz",
            "type": "outcome",
            "title": "Second outcome",
            "status": "open",
            "order": 2,
        }
        data = make_jsonl(second_outcome, OPEN_OUTCOME)  # out of order in file
        result = run_bon_read(tmp_path, data, "list")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        outcome_lines = [l for l in lines if not l.startswith("  ")]
        assert "Test outcome" in outcome_lines[0]  # order 1 first
        assert "Second outcome" in outcome_lines[1]  # order 2 second

    def test_waiting_actions_appear_in_list(self, tmp_path):
        """Waiting actions are shown in list (list doesn't filter by waiting)."""
        data = make_jsonl(OPEN_OUTCOME, WAITING_ACTION)
        result = run_bon_read(tmp_path, data, "list")
        assert "Waiting action" in result.stdout

    def test_no_trailing_blank_line(self, tmp_path):
        """Output must not end with a blank line (match arc CLI)."""
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION)
        result = run_bon_read(tmp_path, data, "list")
        assert result.stdout != ""
        assert not result.stdout.endswith("\n\n")


class TestReadyCommand:
    """The ready command shows only open, non-waiting items."""

    def test_excludes_done_actions(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION, DONE_ACTION)
        result = run_bon_read(tmp_path, data, "ready")
        assert "Open action" in result.stdout
        assert "Done action" not in result.stdout

    def test_excludes_waiting_actions(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION, WAITING_ACTION)
        result = run_bon_read(tmp_path, data, "ready")
        assert "Open action" in result.stdout
        assert "Waiting action" not in result.stdout

    def test_renumbers_sequentially(self, tmp_path):
        """Ready uses sequential 1,2,3 numbering, not item order fields."""
        data = make_jsonl(
            OPEN_OUTCOME,
            {**OPEN_ACTION, "order": 3, "title": "Was third"},
            {**OPEN_ACTION, "id": "test-act5", "order": 5, "title": "Was fifth"},
        )
        result = run_bon_read(tmp_path, data, "ready")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        action_lines = [l for l in lines if l.startswith("  ")]
        assert action_lines[0].strip().startswith("1.")
        assert action_lines[1].strip().startswith("2.")

    def test_standalone_outcome_appears(self, tmp_path):
        """Open outcome with no children still appears in ready."""
        data = make_jsonl(OPEN_OUTCOME)
        result = run_bon_read(tmp_path, data, "ready")
        assert "Test outcome" in result.stdout

    def test_outcome_hidden_when_all_actions_done(self, tmp_path):
        """Open outcome with only done actions — outcome shown, no actions listed."""
        data = make_jsonl(OPEN_OUTCOME, DONE_ACTION)
        result = run_bon_read(tmp_path, data, "ready")
        lines = [l for l in result.stdout.strip().split("\n") if l]
        assert any("Test outcome" in l for l in lines)
        assert not any("Done action" in l for l in lines)

    def test_no_trailing_blank_line(self, tmp_path):
        """Output must not end with a blank line (match arc CLI)."""
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION)
        result = run_bon_read(tmp_path, data, "ready")
        assert result.stdout != ""
        assert not result.stdout.endswith("\n\n")


class TestCurrentCommand:
    """The current command shows active tactical steps."""

    def test_no_tactical_no_output(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, OPEN_ACTION)
        result = run_bon_read(tmp_path, data, "current")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_shows_tactical_steps(self, tmp_path):
        data = make_jsonl(OPEN_OUTCOME, TACTICAL_ACTION)
        result = run_bon_read(tmp_path, data, "current")
        lines = result.stdout.strip().split("\n")
        assert "Working:" in lines[0]
        assert "Tactical action" in lines[0]
        assert len(lines) == 4  # header + 3 steps

    def test_step_markers(self, tmp_path):
        """Completed=✓, current=→ [current], pending=space."""
        data = make_jsonl(OPEN_OUTCOME, TACTICAL_ACTION)
        result = run_bon_read(tmp_path, data, "current")
        lines = result.stdout.strip().split("\n")
        # current=1 means step 0 (First) is done, step 1 (Second) is current
        assert "\u2713" in lines[1] and "First step" in lines[1]
        assert "\u2192" in lines[2] and "Second step" in lines[2] and "[current]" in lines[2]
        assert "Third step" in lines[3]
        assert "\u2192" not in lines[3]  # not current

    def test_done_item_with_tactical_ignored(self, tmp_path):
        """Done item with leftover tactical steps not shown."""
        done_with_tactical = {**TACTICAL_ACTION, "status": "done"}
        data = make_jsonl(OPEN_OUTCOME, done_with_tactical)
        result = run_bon_read(tmp_path, data, "current")
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_tactical_at_step_zero(self, tmp_path):
        """current=0 means first step is current, none completed."""
        action = {**TACTICAL_ACTION, "tactical": {"steps": ["Only step"], "current": 0}}
        data = make_jsonl(OPEN_OUTCOME, action)
        result = run_bon_read(tmp_path, data, "current")
        lines = result.stdout.strip().split("\n")
        assert "\u2192" in lines[1] and "[current]" in lines[1]


class TestUsageErrors:
    """Invalid invocations."""

    def test_unknown_command(self, tmp_path):
        result = run_bon_read(tmp_path, make_jsonl(OPEN_OUTCOME), "bogus")
        assert result.returncode == 1
        assert "Usage:" in result.stderr

    def test_no_command(self, tmp_path):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "items.jsonl").write_text(make_jsonl(OPEN_OUTCOME))
        result = subprocess.run(
            [str(BON_READ)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr
