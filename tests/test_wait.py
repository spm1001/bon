"""Tests for arc wait command."""
import json
import re

import pytest
from conftest import run_arc

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestWaitBasic:
    """Test basic arc wait behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_sets_waiting_for(self, arc_dir_with_fixture, monkeypatch):
        """arc wait sets waiting_for field."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-aaa", "some-blocker", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "arc-aaa now waiting for: some-blocker" in result.stdout

        # Verify the item was updated
        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["some-blocker"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_prefix_tolerant(self, arc_dir_with_fixture, monkeypatch):
        """arc wait works with suffix-only ID."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "aaa", "some-blocker", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "arc-aaa now waiting for:" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_with_item_id(self, arc_dir_with_fixture, monkeypatch):
        """arc wait can reference another item ID."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-ccc", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        ccc = json.loads(lines[2])
        assert ccc["waiting_for"] == ["arc-bbb"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_wait_appends_blocker(self, arc_dir_with_fixture, monkeypatch):
        """arc wait appends to existing blockers list."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is already waiting for arc-ccc
        result = run_arc("wait", "arc-bbb", "new-reason", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] == ["arc-ccc", "new-reason"]

    def test_wait_free_text_reason(self, arc_dir, monkeypatch):
        """arc wait accepts free text as reason."""
        monkeypatch.chdir(arc_dir)

        # Create an item first
        run_arc("new", "Test", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        lines = (arc_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        item_id = json.loads(lines[0])["id"]

        result = run_arc("wait", item_id, "security review approval", cwd=arc_dir)

        assert result.returncode == 0
        assert "security review approval" in result.stdout


class TestWaitErrors:
    """Test arc wait error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-nonexistent", "reason", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    def test_wait_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("wait", "arc-aaa", "reason", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestWaitWarnings:
    """Test arc wait warning behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_warns_on_nonexistent_id(self, arc_dir_with_fixture, monkeypatch):
        """Warning when waiting_for looks like an arc ID but doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-ccc", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "not found in active items" in result.stderr
        assert "arc-ccc now waiting for:" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_no_warn_on_valid_id(self, arc_dir_with_fixture, monkeypatch):
        """No warning when waiting_for references a real item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-ccc", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "not found" not in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_no_warn_on_free_text(self, arc_dir_with_fixture, monkeypatch):
        """No warning when waiting_for is free text."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-ccc", "external security review", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "not found" not in result.stderr


class TestWaitNote:
    """Test wait --note feature."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_with_note(self, arc_dir_with_fixture, monkeypatch):
        """arc wait --note stores wait_note on the item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("wait", "arc-aaa", "arc-blocker", "--note", "needs migration script tested", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["wait_note"] == "needs migration script tested"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_without_note(self, arc_dir_with_fixture, monkeypatch):
        """arc wait without --note does not add wait_note."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "wait_note" not in item

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_cleared_on_unwait(self, arc_dir_with_fixture, monkeypatch):
        """arc unwait clears wait_note."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker", "--note", "some reason", cwd=arc_dir_with_fixture)
        run_arc("unwait", "arc-aaa", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] is None
        assert "wait_note" not in item

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_shown_in_show(self, arc_dir_with_fixture, monkeypatch):
        """bon show displays wait_note alongside waiting_for."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "arc-blocker", "--note", "needs testing", cwd=arc_dir_with_fixture)
        result = run_arc("show", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Waiting for: arc-blocker (needs testing)" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_overwritten_on_rewait(self, arc_dir_with_fixture, monkeypatch):
        """Waiting again with a new note replaces the old one."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", "--note", "first reason", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-aaa", "blocker-2", "--note", "second reason", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1", "blocker-2"]
        assert item["wait_note"] == "second reason"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_preserved_when_adding_blocker_without_note(self, arc_dir_with_fixture, monkeypatch):
        """Adding a second blocker without --note preserves existing wait_note."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", "--note", "some reason", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-aaa", "blocker-2", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1", "blocker-2"]
        assert item["wait_note"] == "some reason"


class TestWaitNoteUnblockCascade:
    """Test that unblock-on-done clears wait_note."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_done_clears_wait_note(self, arc_dir_with_fixture, monkeypatch):
        """Completing a blocker clears wait_note on the waiting item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is waiting for arc-ccc in this fixture
        # Add a wait_note manually
        items_file = arc_dir_with_fixture / ".bon" / "items.jsonl"
        lines = items_file.read_text().strip().split("\n")
        items = [json.loads(l) for l in lines]
        for item in items:
            if item["id"] == "arc-bbb":
                item["wait_note"] = "needs ccc done first"
        items_file.write_text("\n".join(json.dumps(i) for i in items) + "\n")

        # Complete the blocker
        result = run_arc("done", "arc-ccc", cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        # Check that wait_note was cleared
        lines = items_file.read_text().strip().split("\n")
        for line in lines:
            item = json.loads(line)
            if item["id"] == "arc-bbb":
                assert item["waiting_for"] is None
                assert "wait_note" not in item


class TestMultiBlocker:
    """Test multiple blockers on a single item."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_multiple_blockers(self, arc_dir_with_fixture, monkeypatch):
        """Calling wait twice appends both blockers."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-aaa", "blocker-2", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1", "blocker-2"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_idempotent(self, arc_dir_with_fixture, monkeypatch):
        """Waiting for the same blocker twice doesn't duplicate it."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_specific_blocker(self, arc_dir_with_fixture, monkeypatch):
        """Unwait with a specific blocker removes only that one."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-aaa", "blocker-2", cwd=arc_dir_with_fixture)
        result = run_arc("unwait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "still waiting for" in result.stdout

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-2"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_last_blocker_sets_none(self, arc_dir_with_fixture, monkeypatch):
        """Removing the last blocker sets waiting_for to None."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)
        run_arc("unwait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] is None

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_partial_unblock(self, arc_dir_with_fixture, monkeypatch):
        """Completing one of multiple blockers removes it but doesn't fully unblock."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is already done in fixture — reopen it first
        run_arc("reopen", "arc-bbb", cwd=arc_dir_with_fixture)

        # Wait arc-ccc for both arc-bbb and a text reason
        run_arc("wait", "arc-ccc", "arc-bbb", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-ccc", "external-review", cwd=arc_dir_with_fixture)

        # Complete arc-bbb — should remove it from arc-ccc's blockers
        run_arc("done", "arc-bbb", cwd=arc_dir_with_fixture)

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        ccc = next(json.loads(l) for l in lines if json.loads(l)["id"] == "arc-ccc")
        assert ccc["waiting_for"] == ["external-review"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_displays_multiple_blockers(self, arc_dir_with_fixture, monkeypatch):
        """bon show displays all blockers."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker-1", cwd=arc_dir_with_fixture)
        run_arc("wait", "arc-aaa", "blocker-2", cwd=arc_dir_with_fixture)
        result = run_arc("show", "arc-aaa", cwd=arc_dir_with_fixture)

        assert "Waiting for: blocker-1, blocker-2" in result.stdout


class TestWaitUpdatedAt:
    """Verify wait sets updated_at timestamp."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_sets_updated_at(self, arc_dir_with_fixture, monkeypatch):
        """arc wait sets updated_at on the item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("wait", "arc-aaa", "blocker", cwd=arc_dir_with_fixture)

        item = json.loads((arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "updated_at" in item
        assert ISO_RE.match(item["updated_at"])
