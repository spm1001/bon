"""Tests for arc edit command (flag-based, non-interactive)."""
import json
import re

import pytest
from conftest import run_arc

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestEditBasic:
    """Test basic arc edit behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_title(self, arc_dir_with_fixture, monkeypatch):
        """arc edit --title changes title."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", "--title", "New Title", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Updated: arc-aaa" in result.stdout

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_why(self, arc_dir_with_fixture, monkeypatch):
        """arc edit --why changes brief.why."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", "--why", "New reason", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["why"] == "New reason"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_what(self, arc_dir_with_fixture, monkeypatch):
        """arc edit --what changes brief.what."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", "--what", "New deliverable", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["what"] == "New deliverable"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_done(self, arc_dir_with_fixture, monkeypatch):
        """arc edit --done changes brief.done."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", "--done", "New criteria", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["done"] == "New criteria"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_multiple_fields(self, arc_dir_with_fixture, monkeypatch):
        """arc edit can change multiple fields at once."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa",
                        "--title", "New Title",
                        "--why", "New reason",
                        "--what", "New deliverable",
                        cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"
        assert item["brief"]["why"] == "New reason"
        assert item["brief"]["what"] == "New deliverable"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_requires_flag(self, arc_dir_with_fixture, monkeypatch):
        """Edit with no flags is an error."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "At least one edit flag required" in result.stderr


class TestEditValidation:
    """Test arc edit validation."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Cannot set parent to non-existent ID."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-ccc", "--parent", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent 'arc-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_must_be_outcome(self, arc_dir_with_fixture, monkeypatch):
        """Cannot set parent to an action."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-ccc is an action, try to set its parent to arc-bbb (also an action)

        result = run_arc("edit", "arc-ccc", "--parent", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr


class TestEditReorder:
    """Test arc edit reordering."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_outcomes(self, arc_dir_with_fixture, monkeypatch):
        """Changing order shifts siblings."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-aaa has order 1, arc-bbb has order 2
        # Move arc-bbb to order 1

        result = run_arc("edit", "arc-bbb", "--order", "1", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # arc-bbb should now be order 1
        assert items["arc-bbb"]["order"] == 1
        # arc-aaa should have shifted to order 2
        assert items["arc-aaa"]["order"] == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_move_down(self, arc_dir_with_fixture, monkeypatch):
        """Moving order down shifts siblings up."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-aaa has order 1, arc-bbb has order 2
        # Move arc-aaa to order 2 (moving DOWN)

        result = run_arc("edit", "arc-aaa", "--order", "2", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # arc-aaa should now be order 2
        assert items["arc-aaa"]["order"] == 2
        # arc-bbb should have shifted to order 1
        assert items["arc-bbb"]["order"] == 1


class TestEditReparent:
    """Test arc edit reparenting."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_action_to_different_outcome(self, arc_dir_with_fixture, monkeypatch):
        """Reparenting action moves it to new outcome at end."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-ccc is under arc-aaa, move it to arc-bbb

        result = run_arc("edit", "arc-ccc", "--parent", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # arc-ccc should now be under arc-bbb
        assert items["arc-ccc"]["parent"] == "arc-bbb"
        # arc-ccc should be at order 2 (after arc-ddd which is at order 1)
        assert items["arc-ccc"]["order"] == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_closes_gap_in_old_parent(self, arc_dir_with_fixture, monkeypatch):
        """Reparenting closes the gap left in old parent's ordering."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # First, create a second outcome to reparent to
        run_arc("new", "Second outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=arc_dir_with_fixture)

        # Get the new outcome's ID
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        new_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Second outcome":
                new_outcome_id = item["id"]
                break

        # Now create another action under arc-aaa to have order 3
        run_arc("new", "Third action",
                "--for", "arc-aaa",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=arc_dir_with_fixture)

        # Verify setup: arc-bbb (order 1), arc-ccc (order 2), new action (order 3)
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        actions_under_aaa = [json.loads(line) for line in lines
                           if json.loads(line).get("parent") == "arc-aaa"]
        assert len(actions_under_aaa) == 3

        # Now reparent arc-ccc (order 2) to the new outcome
        result = run_arc("edit", "arc-ccc", "--parent", new_outcome_id, cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        # Check that the third action (was order 3) is now order 2
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        third_action = [i for i in items.values()
                       if i.get("parent") == "arc-aaa" and i["title"] == "Third action"][0]
        assert third_action["order"] == 2  # Gap closed

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_to_outcome_with_no_actions(self, arc_dir_with_fixture, monkeypatch):
        """Reparenting to outcome with no actions sets order to 1."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Create a third outcome with no actions
        run_arc("new", "Empty outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=arc_dir_with_fixture)

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        empty_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Empty outcome":
                empty_outcome_id = item["id"]
                break

        # Reparent arc-ccc to the empty outcome
        result = run_arc("edit", "arc-ccc", "--parent", empty_outcome_id, cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["arc-ccc"]["parent"] == empty_outcome_id
        assert items["arc-ccc"]["order"] == 1

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_to_none_makes_standalone(self, arc_dir_with_fixture, monkeypatch):
        """Reparenting to 'none' makes action standalone."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-ccc is under arc-aaa

        result = run_arc("edit", "arc-ccc", "--parent", "none", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # arc-ccc should now be standalone (no parent)
        assert items["arc-ccc"].get("parent") is None


class TestEditErrors:
    """Test arc edit error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-nonexistent", "--title", "X", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_outcome_cannot_have_parent(self, arc_dir_with_fixture, monkeypatch):
        """Error when trying to set parent on outcome."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", "--parent", "something", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Cannot set --outcome on an outcome" in result.stderr

    def test_edit_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("edit", "arc-aaa", "--title", "X", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestEditUpdatedAt:
    """Verify edit sets updated_at timestamp."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_sets_updated_at(self, arc_dir_with_fixture, monkeypatch):
        """arc edit sets updated_at on the item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("edit", "arc-aaa", "--title", "New Title", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "updated_at" in item
        assert ISO_RE.match(item["updated_at"])
