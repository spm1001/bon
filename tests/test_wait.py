"""Tests for arc wait command."""
import json

import pytest
from conftest import run_arc


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
        assert item["waiting_for"] == "some-blocker"

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
        assert ccc["waiting_for"] == "arc-bbb"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_wait_overwrites_previous(self, arc_dir_with_fixture, monkeypatch):
        """arc wait overwrites previous waiting_for."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is already waiting for arc-ccc
        result = run_arc("wait", "arc-bbb", "new-reason", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] == "new-reason"

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
