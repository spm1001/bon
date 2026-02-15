"""Tests for storage operations."""
import json

import pytest

from bon.storage import (
    ValidationError,
    find_by_id,
    load_items,
    load_prefix,
    now_iso,
    save_items,
    validate_item,
)


class TestLoadItems:
    def test_empty_file(self, arc_dir, monkeypatch):
        """Empty items.jsonl returns empty list."""
        monkeypatch.chdir(arc_dir)

        items = load_items()

        assert items == []

    def test_load_single_item(self, arc_dir, monkeypatch):
        """Load a single valid item."""
        monkeypatch.chdir(arc_dir)
        item = {"id": "arc-aaa", "type": "outcome", "title": "Test", "status": "open"}
        (arc_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")

        items = load_items()

        assert len(items) == 1
        assert items[0]["id"] == "arc-aaa"

    def test_skip_malformed_json(self, arc_dir, monkeypatch, capsys):
        """Malformed JSON lines are skipped with warning."""
        monkeypatch.chdir(arc_dir)
        content = '{"id": "arc-aaa", "type": "outcome", "title": "Good", "status": "open"}\n'
        content += 'not valid json\n'
        content += '{"id": "arc-bbb", "type": "action", "title": "Also good", "status": "open"}\n'
        (arc_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 2
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "line 2" in captured.err


class TestValidateItem:
    def test_valid_outcome(self):
        """Valid outcome passes validation."""
        item = {"id": "arc-aaa", "type": "outcome", "title": "Test", "status": "open"}
        validate_item(item)  # Should not raise

    def test_valid_action(self):
        """Valid action passes validation."""
        item = {"id": "arc-aaa", "type": "action", "title": "Test", "status": "done"}
        validate_item(item)  # Should not raise

    def test_missing_required_field(self):
        """Missing required field raises ValidationError."""
        item = {"id": "arc-aaa", "type": "outcome", "title": "Test"}  # Missing status
        with pytest.raises(ValidationError, match="Missing required field: status"):
            validate_item(item)

    def test_invalid_type(self):
        """Invalid type raises ValidationError."""
        item = {"id": "arc-aaa", "type": "task", "title": "Test", "status": "open"}
        with pytest.raises(ValidationError, match="Invalid type: task"):
            validate_item(item)

    def test_invalid_status(self):
        """Invalid status raises ValidationError."""
        item = {"id": "arc-aaa", "type": "outcome", "title": "Test", "status": "closed"}
        with pytest.raises(ValidationError, match="Invalid status: closed"):
            validate_item(item)

    def test_strict_requires_brief(self):
        """Strict mode requires brief field."""
        item = {"id": "arc-aaa", "type": "outcome", "title": "Test", "status": "open"}
        with pytest.raises(ValidationError, match="Missing required field: brief"):
            validate_item(item, strict=True)

    def test_strict_requires_brief_subfields(self):
        """Strict mode requires all brief subfields."""
        item = {
            "id": "arc-aaa", "type": "outcome", "title": "Test", "status": "open",
            "brief": {"why": "reason", "what": "thing"}  # Missing 'done'
        }
        with pytest.raises(ValidationError, match="Missing brief.done"):
            validate_item(item, strict=True)


class TestLoadItemsDedup:
    def test_duplicate_id_warns(self, arc_dir, monkeypatch, capsys):
        """Duplicate IDs produce a warning."""
        monkeypatch.chdir(arc_dir)
        item = {"id": "arc-aaa", "type": "outcome", "title": "Test", "status": "open"}
        content = json.dumps(item) + "\n" + json.dumps(item) + "\n"
        (arc_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 1
        captured = capsys.readouterr()
        assert "Duplicate IDs found" in captured.err
        assert "arc-aaa" in captured.err

    def test_duplicate_prefers_most_recent(self, arc_dir, monkeypatch, capsys):
        """Dedup keeps the version with the most recent timestamp."""
        monkeypatch.chdir(arc_dir)
        old = {"id": "arc-aaa", "type": "outcome", "title": "Old", "status": "open",
               "created_at": "2026-01-01T00:00:00Z"}
        new = {"id": "arc-aaa", "type": "outcome", "title": "New", "status": "done",
               "created_at": "2026-01-01T00:00:00Z", "done_at": "2026-02-01T00:00:00Z"}
        # Old appears after new — but new should still win because done_at is more recent
        content = json.dumps(new) + "\n" + json.dumps(old) + "\n"
        (arc_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 1
        assert items[0]["title"] == "New"
        assert items[0]["status"] == "done"

    def test_conflict_markers_warn(self, arc_dir, monkeypatch, capsys):
        """Git conflict markers produce a specific diagnostic."""
        monkeypatch.chdir(arc_dir)
        content = (
            '{"id": "arc-aaa", "type": "outcome", "title": "Test", "status": "open"}\n'
            '<<<<<<< HEAD\n'
            '{"id": "arc-bbb", "type": "action", "title": "Ours", "status": "open"}\n'
            '=======\n'
            '{"id": "arc-bbb", "type": "action", "title": "Theirs", "status": "done"}\n'
            '>>>>>>> branch\n'
        )
        (arc_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        captured = capsys.readouterr()
        assert "conflict marker" in captured.err.lower()
        # Should still load the valid items (both versions of arc-bbb)
        assert any(i["id"] == "arc-aaa" for i in items)


class TestSaveItems:
    def test_save_and_reload(self, arc_dir, monkeypatch):
        """Items saved can be reloaded."""
        monkeypatch.chdir(arc_dir)
        items = [
            {"id": "arc-aaa", "type": "outcome", "title": "Test 1", "status": "open"},
            {"id": "arc-bbb", "type": "action", "title": "Test 2", "status": "done"},
        ]

        save_items(items)
        reloaded = load_items()

        assert len(reloaded) == 2
        assert reloaded[0]["id"] == "arc-aaa"
        assert reloaded[1]["id"] == "arc-bbb"


class TestFindById:
    def test_exact_match(self):
        """Find by exact ID."""
        items = [
            {"id": "arc-aaa", "type": "outcome"},
            {"id": "arc-bbb", "type": "action"},
        ]

        result = find_by_id(items, "arc-bbb")

        assert result["id"] == "arc-bbb"

    def test_not_found(self):
        """Return None when not found."""
        items = [{"id": "arc-aaa", "type": "outcome"}]

        result = find_by_id(items, "arc-zzz")

        assert result is None

    def test_prefix_tolerant(self):
        """Find by suffix when prefix provided."""
        items = [{"id": "arc-aaa", "type": "outcome"}]

        result = find_by_id(items, "aaa", prefix="arc")

        assert result["id"] == "arc-aaa"


class TestLoadPrefix:
    def test_default_prefix(self, arc_dir, monkeypatch):
        """Default prefix is 'bon' when file is missing."""
        monkeypatch.chdir(arc_dir)
        (arc_dir / ".bon" / "prefix").unlink()  # Remove prefix file

        prefix = load_prefix()

        assert prefix == "bon"

    def test_custom_prefix(self, arc_dir, monkeypatch):
        """Read custom prefix from file."""
        monkeypatch.chdir(arc_dir)
        (arc_dir / ".bon" / "prefix").write_text("myproject")

        prefix = load_prefix()

        assert prefix == "myproject"


class TestNowIso:
    def test_format(self):
        """now_iso returns ISO8601 format with Z suffix."""
        result = now_iso()

        assert result.endswith("Z")
        assert "T" in result
        # Should be parseable
        from datetime import datetime
        datetime.fromisoformat(result.replace("Z", "+00:00"))
