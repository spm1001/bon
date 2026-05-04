"""Tests for bon edit command (flag-based, non-interactive)."""
import json
import re

import pytest
from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestEditBasic:
    """Test basic bon edit behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_title(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --title changes title."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--title", "New Title", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Updated: bon-aaa" in result.stdout

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_why(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --why changes brief.why."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--why", "New reason", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["why"] == "New reason"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_what(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --what changes brief.what."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--what", "New deliverable", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["what"] == "New deliverable"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_done(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --done changes brief.done."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--done", "New criteria", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["done"] == "New criteria"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_multiple_fields(self, bon_dir_with_fixture, monkeypatch):
        """bon edit can change multiple fields at once."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa",
                        "--title", "New Title",
                        "--why", "New reason",
                        "--what", "New deliverable",
                        cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"
        assert item["brief"]["why"] == "New reason"
        assert item["brief"]["what"] == "New deliverable"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_requires_flag(self, bon_dir_with_fixture, monkeypatch):
        """Edit with no flags is an error."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "At least one edit flag required" in result.stderr


class TestEditValidation:
    """Test bon edit validation."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Cannot set parent to non-existent ID."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-ccc", "--parent", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent 'bon-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_must_be_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Cannot set parent to an action."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-ccc is an action, try to set its parent to bon-bbb (also an action)

        result = run_bon("edit", "bon-ccc", "--parent", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr


class TestEditReorder:
    """Test bon edit reordering."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_outcomes(self, bon_dir_with_fixture, monkeypatch):
        """Changing order shifts siblings."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-aaa has order 1, bon-bbb has order 2
        # Move bon-bbb to order 1

        result = run_bon("edit", "bon-bbb", "--order", "1", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-bbb should now be order 1
        assert items["bon-bbb"]["order"] == 1
        # bon-aaa should have shifted to order 2
        assert items["bon-aaa"]["order"] == 2

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_move_down(self, bon_dir_with_fixture, monkeypatch):
        """Moving order down shifts siblings up."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-aaa has order 1, bon-bbb has order 2
        # Move bon-aaa to order 2 (moving DOWN)

        result = run_bon("edit", "bon-aaa", "--order", "2", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-aaa should now be order 2
        assert items["bon-aaa"]["order"] == 2
        # bon-bbb should have shifted to order 1
        assert items["bon-bbb"]["order"] == 1


class TestEditReparent:
    """Test bon edit reparenting."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_action_to_different_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting action moves it to new outcome at end."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-ccc is under bon-aaa, move it to bon-bbb

        result = run_bon("edit", "bon-ccc", "--parent", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-ccc should now be under bon-bbb
        assert items["bon-ccc"]["parent"] == "bon-bbb"
        # bon-ccc should be at order 2 (after bon-ddd which is at order 1)
        assert items["bon-ccc"]["order"] == 2

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_resolves_short_id(self, bon_dir_with_fixture, monkeypatch):
        """--parent accepts a short ID and stores the canonical full ID."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bbb (without bon- prefix) should resolve to bon-bbb on storage

        result = run_bon("edit", "bon-ccc", "--parent", "bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # Stored parent must be the canonical "bon-bbb", not the short "bbb"
        assert items["bon-ccc"]["parent"] == "bon-bbb"

        # And the hierarchy should render the reparented item correctly
        list_result = run_bon("list", cwd=bon_dir_with_fixture)
        assert list_result.returncode == 0
        # bon-ccc should appear under bon-bbb in the rendered hierarchy
        # (format_hierarchical does exact-match against parent ID, so a short-form
        # storage would orphan it)
        bbb_idx = list_result.stdout.find("bon-bbb")
        ccc_idx = list_result.stdout.find("bon-ccc")
        assert bbb_idx >= 0 and ccc_idx > bbb_idx, \
            f"bon-ccc should appear under bon-bbb in hierarchy:\n{list_result.stdout}"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_closes_gap_in_old_parent(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting closes the gap left in old parent's ordering."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # First, create a second outcome to reparent to
        run_bon("new", "Second outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        # Get the new outcome's ID
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        new_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Second outcome":
                new_outcome_id = item["id"]
                break

        # Now create another action under bon-aaa to have order 3
        run_bon("new", "Third action",
                "--for", "bon-aaa",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        # Verify setup: bon-bbb (order 1), bon-ccc (order 2), new action (order 3)
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        actions_under_aaa = [json.loads(line) for line in lines
                           if json.loads(line).get("parent") == "bon-aaa"]
        assert len(actions_under_aaa) == 3

        # Now reparent bon-ccc (order 2) to the new outcome
        result = run_bon("edit", "bon-ccc", "--parent", new_outcome_id, cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        # Check that the third action (was order 3) is now order 2
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        third_action = [i for i in items.values()
                       if i.get("parent") == "bon-aaa" and i["title"] == "Third action"][0]
        assert third_action["order"] == 2  # Gap closed

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_to_outcome_with_no_actions(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting to outcome with no actions sets order to 1."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Create a third outcome with no actions
        run_bon("new", "Empty outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        empty_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Empty outcome":
                empty_outcome_id = item["id"]
                break

        # Reparent bon-ccc to the empty outcome
        result = run_bon("edit", "bon-ccc", "--parent", empty_outcome_id, cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-ccc"]["parent"] == empty_outcome_id
        assert items["bon-ccc"]["order"] == 1

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_to_none_makes_standalone(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting to 'none' makes action standalone."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-ccc is under bon-aaa

        result = run_bon("edit", "bon-ccc", "--parent", "none", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-ccc should now be standalone (no parent)
        assert items["bon-ccc"].get("parent") is None


class TestEditErrors:
    """Test bon edit error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-nonexistent", "--title", "X", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_outcome_cannot_have_parent(self, bon_dir_with_fixture, monkeypatch):
        """Error when trying to set parent on outcome."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--parent", "something", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Cannot set --outcome on an outcome" in result.stderr

    def test_edit_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("edit", "bon-aaa", "--title", "X", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestEditUpdatedAt:
    """Verify edit sets updated_at timestamp."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """bon edit sets updated_at on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--title", "New Title", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "updated_at" in item
        assert ISO_RE.match(item["updated_at"])
