"""Tests for arc unwait command."""
import json
import re

import pytest
from conftest import run_arc

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestUnwaitBasic:
    """Test basic arc unwait behavior."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_unwait_clears_waiting_for(self, arc_dir_with_fixture, monkeypatch):
        """arc unwait clears waiting_for field."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is waiting for arc-ccc
        result = run_arc("unwait", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "arc-bbb no longer waiting" in result.stdout

        # Verify the item was updated
        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] is None

    @pytest.mark.parametrize("arc_dir_with_fixture", ["all_waiting"], indirect=True)
    def test_unwait_free_text_dependency(self, arc_dir_with_fixture, monkeypatch):
        """arc unwait works on free text dependencies."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is waiting for "external counsel" (free text)
        result = run_arc("unwait", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert bbb["waiting_for"] is None

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_not_waiting(self, arc_dir_with_fixture, monkeypatch):
        """arc unwait on item not waiting is a no-op (sets None to None)."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("unwait", "arc-aaa", cwd=arc_dir_with_fixture)

        # Should succeed silently
        assert result.returncode == 0
        assert "no longer waiting" in result.stdout


class TestUnwaitErrors:
    """Test arc unwait error cases."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unwait_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("unwait", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    def test_unwait_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("unwait", "arc-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestUnwaitUpdatedAt:
    """Verify unwait sets updated_at timestamp."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_unwait_sets_updated_at(self, arc_dir_with_fixture, monkeypatch):
        """arc unwait sets updated_at on the item."""
        monkeypatch.chdir(arc_dir_with_fixture)

        run_arc("unwait", "arc-bbb", cwd=arc_dir_with_fixture)

        lines = (arc_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        bbb = json.loads(lines[1])
        assert "updated_at" in bbb
        assert ISO_RE.match(bbb["updated_at"])
