"""Tests for arc done command."""
import json

import pytest
from conftest import run_arc


class TestDoneBasic:
    """Test basic arc done behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_marks_item(self, arc_dir_with_fixture, monkeypatch):
        """arc done marks item as done with timestamp."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("done", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: arc-aaa" in result.stdout

        # Verify the item was updated
        item = json.loads((arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip())
        assert item["status"] == "done"
        assert "done_at" in item
        assert item["done_at"].endswith("Z")

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_action(self, arc_dir_with_fixture, monkeypatch):
        """Can mark an action as done."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-ccc is the open action
        result = run_arc("done", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: arc-ccc" in result.stdout


class TestDoneAlready:
    """Test arc done on already-done items."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_already_done(self, arc_dir_with_fixture, monkeypatch):
        """arc done on already-done item is a no-op."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is already done
        result = run_arc("done", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Already done: arc-bbb" in result.stdout


class TestDoneUnblock:
    """Test the critical unblock behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_done_unblocks_waiters(self, arc_dir_with_fixture, monkeypatch):
        """Completing an item clears waiting_for on waiters."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb (Run tests) is waiting for arc-ccc (Security review)
        # Complete arc-ccc
        result = run_arc("done", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: arc-ccc" in result.stdout
        assert "Unblocked: arc-bbb" in result.stdout

        # Verify arc-bbb is now unblocked
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        bbb = next(i for i in items if i["id"] == "arc-bbb")
        assert bbb["waiting_for"] is None

    @pytest.mark.parametrize("arc_dir_with_fixture", ["all_waiting"], indirect=True)
    def test_done_unblocks_chain(self, arc_dir_with_fixture, monkeypatch):
        """Unblocking happens one level at a time."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb waits for "external counsel" (free text)
        # arc-ccc waits for arc-bbb
        # Complete arc-bbb
        result = run_arc("done", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Unblocked: arc-ccc" in result.stdout

        # arc-ccc is now unblocked
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        ccc = next(i for i in items if i["id"] == "arc-ccc")
        assert ccc["waiting_for"] is None


class TestDoneErrors:
    """Test arc done error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("done", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    def test_done_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("done", "arc-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestDonePrefixTolerant:
    """Test prefix-tolerant ID matching."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_by_suffix(self, arc_dir_with_fixture, monkeypatch):
        """Can mark done by suffix only."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("done", "aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: arc-aaa" in result.stdout
