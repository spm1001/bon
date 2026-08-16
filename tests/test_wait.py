"""Tests for bon wait command."""
import json
import re

import pytest
from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestWaitBasic:
    """Test basic bon wait behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_sets_waiting_for(self, bon_dir_with_fixture, monkeypatch):
        """bon wait sets waiting_for field."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-aaa", "some-blocker", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "bon-aaa now waiting for: some-blocker" in result.stdout

        # Verify the item was updated
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["some-blocker"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_prefix_tolerant(self, bon_dir_with_fixture, monkeypatch):
        """bon wait works with suffix-only ID."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "aaa", "some-blocker", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "bon-aaa now waiting for:" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_with_item_id(self, bon_dir_with_fixture, monkeypatch):
        """bon wait can reference another item ID."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-ccc", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        ccc = json.loads(lines[2])
        assert ccc["waiting_for"] == ["bon-bbb"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_wait_appends_blocker(self, bon_dir_with_fixture, monkeypatch):
        """bon wait appends to existing blockers list."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is already waiting for bon-ccc
        result = run_bon("wait", "bon-bbb", "new-reason", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] == ["bon-ccc", "new-reason"]

    def test_wait_free_text_reason(self, bon_dir, monkeypatch):
        """bon wait accepts free text as reason."""
        monkeypatch.chdir(bon_dir)

        # Create an item first
        run_bon("new", "Test", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        item_id = json.loads(lines[0])["id"]

        result = run_bon("wait", item_id, "security review approval", cwd=bon_dir)

        assert result.returncode == 0
        assert "security review approval" in result.stdout


class TestWaitErrors:
    """Test bon wait error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-nonexistent", "reason", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    def test_wait_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("wait", "bon-aaa", "reason", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestWaitWarnings:
    """Test bon wait warning behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_warns_on_nonexistent_id(self, bon_dir_with_fixture, monkeypatch):
        """Warning when waiting_for looks like an bon ID but doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-ccc", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "not found in active items" in result.stderr
        assert "bon-ccc now waiting for:" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_no_warn_on_valid_id(self, bon_dir_with_fixture, monkeypatch):
        """No warning when waiting_for references a real item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-ccc", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "not found" not in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_wait_no_warn_on_free_text(self, bon_dir_with_fixture, monkeypatch):
        """No warning when waiting_for is free text."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-ccc", "external security review", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "not found" not in result.stderr


class TestWaitNote:
    """Test wait --note feature."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_with_note(self, bon_dir_with_fixture, monkeypatch):
        """bon wait --note stores wait_note on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-aaa", "bon-blocker", "--note", "needs migration script tested", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["wait_note"] == "needs migration script tested"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_without_note(self, bon_dir_with_fixture, monkeypatch):
        """bon wait without --note does not add wait_note."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "wait_note" not in item

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_cleared_on_unwait(self, bon_dir_with_fixture, monkeypatch):
        """bon unwait clears wait_note."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker", "--note", "some reason", cwd=bon_dir_with_fixture)
        run_bon("unwait", "bon-aaa", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] is None
        assert "wait_note" not in item

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_shown_in_show(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays wait_note alongside waiting_for."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "bon-blocker", "--note", "needs testing", cwd=bon_dir_with_fixture)
        result = run_bon("show", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Waiting for: bon-blocker (needs testing)" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_overwritten_on_rewait(self, bon_dir_with_fixture, monkeypatch):
        """Waiting again with a new note replaces the old one."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", "--note", "first reason", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-2", "--note", "second reason", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1", "blocker-2"]
        assert item["wait_note"] == "second reason"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_note_preserved_when_adding_blocker_without_note(self, bon_dir_with_fixture, monkeypatch):
        """Adding a second blocker without --note preserves existing wait_note."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", "--note", "some reason", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-2", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1", "blocker-2"]
        assert item["wait_note"] == "some reason"


class TestWaitNoteUnblockCascade:
    """Test that unblock-on-done clears wait_note."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_done_clears_wait_note(self, bon_dir_with_fixture, monkeypatch):
        """Completing a blocker clears wait_note on the waiting item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is waiting for bon-ccc in this fixture
        # Add a wait_note manually
        items_file = bon_dir_with_fixture / ".bon" / "items.jsonl"
        lines = items_file.read_text().strip().split("\n")
        items = [json.loads(l) for l in lines]
        for item in items:
            if item["id"] == "bon-bbb":
                item["wait_note"] = "needs ccc done first"
        items_file.write_text("\n".join(json.dumps(i) for i in items) + "\n")

        # Complete the blocker
        result = run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        # Check that wait_note was cleared
        lines = items_file.read_text().strip().split("\n")
        for line in lines:
            item = json.loads(line)
            if item["id"] == "bon-bbb":
                assert item["waiting_for"] is None
                assert "wait_note" not in item


class TestMultiBlocker:
    """Test multiple blockers on a single item."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_multiple_blockers(self, bon_dir_with_fixture, monkeypatch):
        """Calling wait twice appends both blockers."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-2", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1", "blocker-2"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_idempotent(self, bon_dir_with_fixture, monkeypatch):
        """Waiting for the same blocker twice doesn't duplicate it."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-1"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_specific_blocker(self, bon_dir_with_fixture, monkeypatch):
        """Unwait with a specific blocker removes only that one."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-2", cwd=bon_dir_with_fixture)
        result = run_bon("unwait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "still waiting for" in result.stdout

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["blocker-2"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_last_blocker_sets_none(self, bon_dir_with_fixture, monkeypatch):
        """Removing the last blocker sets waiting_for to None."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)
        run_bon("unwait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_partial_unblock(self, bon_dir_with_fixture, monkeypatch):
        """Completing one of multiple blockers removes it but doesn't fully unblock."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is already done in fixture — reopen it first
        run_bon("reopen", "bon-bbb", cwd=bon_dir_with_fixture)

        # Wait bon-ccc for both bon-bbb and a text reason
        run_bon("wait", "bon-ccc", "bon-bbb", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-ccc", "external-review", cwd=bon_dir_with_fixture)

        # Complete bon-bbb — should remove it from bon-ccc's blockers
        run_bon("done", "bon-bbb", cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        ccc = next(json.loads(l) for l in lines if json.loads(l)["id"] == "bon-ccc")
        assert ccc["waiting_for"] == ["external-review"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_displays_multiple_blockers(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays all blockers."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-2", cwd=bon_dir_with_fixture)
        result = run_bon("show", "bon-aaa", cwd=bon_dir_with_fixture)

        assert "Waiting for: blocker-1, blocker-2" in result.stdout


class TestWaitUpdatedAt:
    """Verify wait sets updated_at timestamp."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_wait_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """bon wait sets updated_at on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-aaa", "blocker", cwd=bon_dir_with_fixture)

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "updated_at" in item
        assert ISO_RE.match(item["updated_at"])


def _set_waiting_for(bon_dir, item_id, value):
    """Write a raw waiting_for value straight into items.jsonl (fixture surgery)."""
    items_file = bon_dir / ".bon" / "items.jsonl"
    items = [json.loads(l) for l in items_file.read_text().strip().split("\n")]
    for item in items:
        if item["id"] == item_id:
            item["waiting_for"] = value
    items_file.write_text("\n".join(json.dumps(i) for i in items) + "\n")


class TestWaitMessageHonesty:
    """The printed line describes the resulting state, not the argument (bon-vapebu)."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_append_message_shows_resulting_list(self, bon_dir_with_fixture, monkeypatch):
        """Appending to a list prints the whole list, and it matches storage."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is already waiting for bon-ccc
        result = run_bon("wait", "bon-bbb", "new-reason", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "bon-bbb now waiting for: bon-ccc, new-reason" in result.stdout
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = next(json.loads(l) for l in lines if json.loads(l)["id"] == "bon-bbb")
        assert bbb["waiting_for"] == ["bon-ccc", "new-reason"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_append_message_on_legacy_scalar(self, bon_dir_with_fixture, monkeypatch):
        """A legacy scalar waiting_for normalises and the message shows both entries."""
        monkeypatch.chdir(bon_dir_with_fixture)
        _set_waiting_for(bon_dir_with_fixture, "bon-aaa", "legacy-blocker")

        result = run_bon("wait", "bon-aaa", "new-reason", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "bon-aaa now waiting for: legacy-blocker, new-reason" in result.stdout
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["legacy-blocker", "new-reason"]


class TestWaitReplace:
    """wait --replace overwrites the blocker set instead of appending."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_replace_overwrites_list(self, bon_dir_with_fixture, monkeypatch):
        """--replace leaves exactly the new reason, and says so."""
        monkeypatch.chdir(bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-1", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-aaa", "blocker-2", cwd=bon_dir_with_fixture)

        result = run_bon("wait", "bon-aaa", "corrected reason", "--replace", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "bon-aaa now waiting for: corrected reason" in result.stdout
        assert "blocker-1" not in result.stdout
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["corrected reason"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_replace_on_legacy_scalar(self, bon_dir_with_fixture, monkeypatch):
        """--replace also cleans up a legacy scalar value."""
        monkeypatch.chdir(bon_dir_with_fixture)
        _set_waiting_for(bon_dir_with_fixture, "bon-aaa", "legacy-blocker")

        result = run_bon("wait", "bon-aaa", "fresh reason", "--replace", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["fresh reason"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_replace_on_unwaiting_item(self, bon_dir_with_fixture, monkeypatch):
        """--replace on an item with no blockers behaves like a plain wait."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("wait", "bon-aaa", "only reason", "--replace", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["waiting_for"] == ["only reason"]
