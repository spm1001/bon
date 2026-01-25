"""Tests for arc edit command."""
import json
import os
import stat
from pathlib import Path

import pytest

from conftest import run_arc


@pytest.fixture
def mock_editor(tmp_path):
    """Create a mock editor script that applies a transformation."""
    script = tmp_path / "mock_editor.sh"
    return script


def make_editor_script(script_path: Path, transform: str):
    """Create an editor script that transforms the JSON file.

    transform is a Python expression using 'data' dict, e.g.:
    "data['title'] = 'New Title'"
    """
    script_content = f'''#!/usr/bin/env python3
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

{transform}

with open(sys.argv[1], 'w') as f:
    json.dump(data, f, indent=2)
'''
    script_path.write_text(script_content)
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)


class TestEditBasic:
    """Test basic arc edit behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_title(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """arc edit can change title."""
        monkeypatch.chdir(arc_dir_with_fixture)
        make_editor_script(mock_editor, "data['title'] = 'New Title'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Updated: arc-aaa" in result.stdout

        item = json.loads((arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """arc edit can change brief fields."""
        monkeypatch.chdir(arc_dir_with_fixture)
        make_editor_script(mock_editor, "data['brief']['why'] = 'New reason'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip())
        assert item["brief"]["why"] == "New reason"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_no_changes(self, arc_dir_with_fixture, monkeypatch):
        """Edit with no changes is a no-op."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Create a script that reads and writes back unchanged
        script = arc_dir_with_fixture / "noop_editor.py"
        script.write_text('''#!/usr/bin/env python3
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
with open(sys.argv[1], 'w') as f:
    json.dump(data, f, indent=2)
''')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setenv("EDITOR", str(script))

        original = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text()

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Updated: arc-aaa" in result.stdout

        # Content should be equivalent (though formatting may differ)
        original_item = json.loads(original.strip())
        new_item = json.loads((arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip())
        assert original_item == new_item


class TestEditValidation:
    """Test arc edit validation."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_cannot_change_id(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Cannot change item ID."""
        monkeypatch.chdir(arc_dir_with_fixture)
        make_editor_script(mock_editor, "data['id'] = 'arc-zzz'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Cannot change item ID" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_cannot_change_type(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Cannot change item type."""
        monkeypatch.chdir(arc_dir_with_fixture)
        make_editor_script(mock_editor, "data['type'] = 'action'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Cannot change item type" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_cannot_remove_brief_field(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Cannot remove brief subfields."""
        monkeypatch.chdir(arc_dir_with_fixture)
        make_editor_script(mock_editor, "del data['brief']['done']")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Missing brief.done" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_not_found(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Cannot set parent to non-existent ID."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-ccc is an action under arc-aaa
        make_editor_script(mock_editor, "data['parent'] = 'arc-nonexistent'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent 'arc-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_must_be_outcome(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Cannot set parent to an action."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-ccc is an action, try to set its parent to arc-bbb (also an action)
        make_editor_script(mock_editor, "data['parent'] = 'arc-bbb'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_cannot_remove_order(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Cannot remove order field."""
        monkeypatch.chdir(arc_dir_with_fixture)
        make_editor_script(mock_editor, "del data['order']")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Missing required field: order" in result.stderr


class TestEditReorder:
    """Test arc edit reordering."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_outcomes(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Changing order shifts siblings."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-aaa has order 1, arc-bbb has order 2
        # Move arc-bbb to order 1
        make_editor_script(mock_editor, "data['order'] = 1")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-bbb should now be order 1
        assert items["arc-bbb"]["order"] == 1
        # arc-aaa should have shifted to order 2
        assert items["arc-aaa"]["order"] == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_move_down(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Moving order down shifts siblings up."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-aaa has order 1, arc-bbb has order 2
        # Move arc-aaa to order 2 (moving DOWN)
        make_editor_script(mock_editor, "data['order'] = 2")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-aaa should now be order 2
        assert items["arc-aaa"]["order"] == 2
        # arc-bbb should have shifted to order 1
        assert items["arc-bbb"]["order"] == 1


class TestEditReparent:
    """Test arc edit reparenting."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_action_to_different_outcome(self, arc_dir_with_fixture, mock_editor, monkeypatch):
        """Reparenting action moves it to new outcome at end."""
        monkeypatch.chdir(arc_dir_with_fixture)
        # arc-ccc is under arc-aaa, move it to arc-bbb
        make_editor_script(mock_editor, "data['parent'] = 'arc-bbb'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-ccc should now be under arc-bbb
        assert items["arc-ccc"]["parent"] == "arc-bbb"
        # arc-ccc should be at order 2 (after arc-ddd which is at order 1)
        assert items["arc-ccc"]["order"] == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_closes_gap_in_old_parent(self, arc_dir_with_fixture, mock_editor, monkeypatch, tmp_path):
        """Reparenting closes the gap left in old parent's ordering."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # First, create a second outcome to reparent to
        run_arc("new", "Second outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=arc_dir_with_fixture)

        # Get the new outcome's ID
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
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
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        actions_under_aaa = [json.loads(l) for l in lines
                           if json.loads(l).get("parent") == "arc-aaa"]
        assert len(actions_under_aaa) == 3

        # Now reparent arc-ccc (order 2) to the new outcome
        make_editor_script(mock_editor, f"data['parent'] = '{new_outcome_id}'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-ccc", cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        # Check that the third action (was order 3) is now order 2
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        third_action = [i for i in items.values()
                       if i.get("parent") == "arc-aaa" and i["title"] == "Third action"][0]
        assert third_action["order"] == 2  # Gap closed

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_to_outcome_with_no_actions(self, arc_dir_with_fixture, mock_editor, monkeypatch, tmp_path):
        """Reparenting to outcome with no actions sets order to 1."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Create a third outcome with no actions
        run_arc("new", "Empty outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=arc_dir_with_fixture)

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        empty_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Empty outcome":
                empty_outcome_id = item["id"]
                break

        # Reparent arc-ccc to the empty outcome
        make_editor_script(mock_editor, f"data['parent'] = '{empty_outcome_id}'")
        monkeypatch.setenv("EDITOR", str(mock_editor))

        result = run_arc("edit", "arc-ccc", cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-ccc"]["parent"] == empty_outcome_id
        assert items["arc-ccc"]["order"] == 1


class TestEditErrors:
    """Test arc edit error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)
        monkeypatch.setenv("EDITOR", "true")  # No-op editor

        result = run_arc("edit", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    def test_edit_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("edit", "arc-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_invalid_json(self, arc_dir_with_fixture, tmp_path, monkeypatch):
        """Error on invalid JSON."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Create an editor that writes invalid JSON
        script = tmp_path / "bad_editor.sh"
        script.write_text('#!/bin/bash\necho "not json" > "$1"')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        monkeypatch.setenv("EDITOR", str(script))

        result = run_arc("edit", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Invalid JSON" in result.stderr
