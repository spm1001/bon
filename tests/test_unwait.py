"""Tests for bon unwait command."""
import json
import re

import pytest
from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestUnwaitBasic:
    """Test basic bon unwait behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_unwait_clears_waiting_for(self, bon_dir_with_fixture, monkeypatch):
        """bon unwait clears waiting_for field."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is waiting for bon-ccc
        result = run_bon("unwait", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "bon-bbb no longer waiting" in result.stdout

        # Verify the item was updated
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["all_waiting"], indirect=True)
    def test_unwait_free_text_dependency(self, bon_dir_with_fixture, monkeypatch):
        """bon unwait works on free text dependencies."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is waiting for "external counsel" (free text)
        result = run_bon("unwait", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_not_waiting(self, bon_dir_with_fixture, monkeypatch):
        """bon unwait on item not waiting is a no-op (sets None to None)."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("unwait", "bon-aaa", cwd=bon_dir_with_fixture)

        # Should succeed silently
        assert result.returncode == 0
        assert "no longer waiting" in result.stdout


class TestUnwaitErrors:
    """Test bon unwait error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("unwait", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    def test_unwait_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("unwait", "bon-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestUnwaitUpdatedAt:
    """Verify unwait sets updated_at timestamp."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_unwait_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """bon unwait sets updated_at on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("unwait", "bon-bbb", cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert "updated_at" in bbb
        assert ISO_RE.match(bbb["updated_at"])


class TestReleasedNote:
    """bon-wevapu: releasing a Waiting For records WHY, not just that it happened.

    The blocker resolves — met, abandoned, or decided against — and before
    this field the rationale evaporated at exactly that moment.
    """

    def _stored(self, bon_dir, item_id):
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        return next(json.loads(l) for l in lines if json.loads(l)["id"] == item_id)

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_unwait_note_stored(self, bon_dir_with_fixture, monkeypatch):
        """The rationale is retrievable afterwards without the transcript."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("unwait", "bon-bbb", "--note",
                         "Sameer decided: capture-path stays as shipped",
                         cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "release note recorded" in result.stdout
        stored = self._stored(bon_dir_with_fixture, "bon-bbb")
        assert stored["released_note"] == "Sameer decided: capture-path stays as shipped"
        assert stored["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_unwait_without_note_stores_nothing(self, bon_dir_with_fixture, monkeypatch):
        """Negative control: no --note, no released_note."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("unwait", "bon-bbb", cwd=bon_dir_with_fixture)

        assert "released_note" not in self._stored(bon_dir_with_fixture, "bon-bbb")

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_show_renders_released_note(self, bon_dir_with_fixture, monkeypatch):
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("unwait", "bon-bbb", "--note", "blocker met", cwd=bon_dir_with_fixture)
        result = run_bon("show", "bon-bbb", cwd=bon_dir_with_fixture)

        assert "Released: blocker met" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_fresh_wait_clears_released_note(self, bon_dir_with_fixture, monkeypatch):
        """A new waiting cycle makes the old release story stale — clear it
        at the moment it would mislead (same rule as done_note on re-close)."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("unwait", "bon-bbb", "--note", "first block met", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-bbb", "a new blocker", cwd=bon_dir_with_fixture)

        stored = self._stored(bon_dir_with_fixture, "bon-bbb")
        assert "released_note" not in stored

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_partial_unwait_with_note(self, bon_dir_with_fixture, monkeypatch):
        """Releasing one blocker of several still records the rationale."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("wait", "bon-bbb", "second-blocker", cwd=bon_dir_with_fixture)
        result = run_bon("unwait", "bon-bbb", "second-blocker", "--note",
                         "decided against", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        stored = self._stored(bon_dir_with_fixture, "bon-bbb")
        assert stored["released_note"] == "decided against"
        assert stored["waiting_for"]  # still waiting on the original

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_wait_note_still_behaves(self, bon_dir_with_fixture, monkeypatch):
        """--done's compatibility clause: bon wait --note is untouched."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("unwait", "bon-bbb", cwd=bon_dir_with_fixture)
        run_bon("wait", "bon-bbb", "blocker-x", "--note", "context here",
                cwd=bon_dir_with_fixture)

        stored = self._stored(bon_dir_with_fixture, "bon-bbb")
        assert stored["wait_note"] == "context here"
