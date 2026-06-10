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
    def test_empty_file(self, bon_dir, monkeypatch):
        """Empty items.jsonl returns empty list."""
        monkeypatch.chdir(bon_dir)

        items = load_items()

        assert items == []

    def test_load_single_item(self, bon_dir, monkeypatch):
        """Load a single valid item."""
        monkeypatch.chdir(bon_dir)
        item = {"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open"}
        (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")

        items = load_items()

        assert len(items) == 1
        assert items[0]["id"] == "bon-aaa"

    def test_skip_malformed_json(self, bon_dir, monkeypatch, capsys):
        """Malformed JSON lines are skipped with warning."""
        monkeypatch.chdir(bon_dir)
        content = '{"id": "bon-aaa", "type": "outcome", "title": "Good", "status": "open"}\n'
        content += 'not valid json\n'
        content += '{"id": "bon-bbb", "type": "action", "title": "Also good", "status": "open"}\n'
        (bon_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 2
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "line 2" in captured.err


class TestValidateItem:
    def test_valid_outcome(self):
        """Valid outcome passes validation."""
        item = {"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open"}
        validate_item(item)  # Should not raise

    def test_valid_action(self):
        """Valid action passes validation."""
        item = {"id": "bon-aaa", "type": "action", "title": "Test", "status": "done"}
        validate_item(item)  # Should not raise

    def test_missing_required_field(self):
        """Missing required field raises ValidationError."""
        item = {"id": "bon-aaa", "type": "outcome", "title": "Test"}  # Missing status
        with pytest.raises(ValidationError, match="Missing required field: status"):
            validate_item(item)

    def test_invalid_type(self):
        """Invalid type raises ValidationError."""
        item = {"id": "bon-aaa", "type": "task", "title": "Test", "status": "open"}
        with pytest.raises(ValidationError, match="Invalid type: task"):
            validate_item(item)

    def test_invalid_status(self):
        """Invalid status raises ValidationError."""
        item = {"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "closed"}
        with pytest.raises(ValidationError, match="Invalid status: closed"):
            validate_item(item)

    def test_strict_requires_brief(self):
        """Strict mode requires brief field."""
        item = {"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open"}
        with pytest.raises(ValidationError, match="Missing required field: brief"):
            validate_item(item, strict=True)

    def test_strict_requires_brief_subfields(self):
        """Strict mode requires all brief subfields."""
        item = {
            "id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open",
            "brief": {"why": "reason", "what": "thing"}  # Missing 'done'
        }
        with pytest.raises(ValidationError, match="Missing brief.done"):
            validate_item(item, strict=True)


class TestLoadItemsDedup:
    def test_duplicate_id_warns(self, bon_dir, monkeypatch, capsys):
        """Duplicate IDs produce a warning."""
        monkeypatch.chdir(bon_dir)
        item = {"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open"}
        content = json.dumps(item) + "\n" + json.dumps(item) + "\n"
        (bon_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 1
        captured = capsys.readouterr()
        assert "Duplicate IDs found" in captured.err
        assert "bon-aaa" in captured.err

    def test_duplicate_prefers_most_recent(self, bon_dir, monkeypatch, capsys):
        """Dedup keeps the version with the most recent timestamp."""
        monkeypatch.chdir(bon_dir)
        old = {"id": "bon-aaa", "type": "outcome", "title": "Old", "status": "open",
               "created_at": "2026-01-01T00:00:00Z"}
        new = {"id": "bon-aaa", "type": "outcome", "title": "New", "status": "done",
               "created_at": "2026-01-01T00:00:00Z", "done_at": "2026-02-01T00:00:00Z"}
        # Old appears after new — but new should still win because done_at is more recent
        content = json.dumps(new) + "\n" + json.dumps(old) + "\n"
        (bon_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 1
        assert items[0]["title"] == "New"
        assert items[0]["status"] == "done"

    def test_duplicate_prefers_updated_at(self, bon_dir, monkeypatch, capsys):
        """Dedup considers updated_at in timestamp comparison."""
        monkeypatch.chdir(bon_dir)
        old = {"id": "bon-aaa", "type": "outcome", "title": "Old", "status": "open",
               "created_at": "2026-01-01T00:00:00Z"}
        new = {"id": "bon-aaa", "type": "outcome", "title": "Edited", "status": "open",
               "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z"}
        # Old appears after new — but new should win because updated_at is more recent
        content = json.dumps(new) + "\n" + json.dumps(old) + "\n"
        (bon_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        assert len(items) == 1
        assert items[0]["title"] == "Edited"

    def test_conflict_markers_warn(self, bon_dir, monkeypatch, capsys):
        """Git conflict markers produce a specific diagnostic."""
        monkeypatch.chdir(bon_dir)
        content = (
            '{"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open"}\n'
            '<<<<<<< HEAD\n'
            '{"id": "bon-bbb", "type": "action", "title": "Ours", "status": "open"}\n'
            '=======\n'
            '{"id": "bon-bbb", "type": "action", "title": "Theirs", "status": "done"}\n'
            '>>>>>>> branch\n'
        )
        (bon_dir / ".bon" / "items.jsonl").write_text(content)

        items = load_items()

        captured = capsys.readouterr()
        assert "conflict marker" in captured.err.lower()
        # Should still load the valid items (both versions of bon-bbb)
        assert any(i["id"] == "bon-aaa" for i in items)


class TestSaveItems:
    def test_save_and_reload(self, bon_dir, monkeypatch):
        """Items saved can be reloaded."""
        monkeypatch.chdir(bon_dir)
        items = [
            {"id": "bon-aaa", "type": "outcome", "title": "Test 1", "status": "open"},
            {"id": "bon-bbb", "type": "action", "title": "Test 2", "status": "done"},
        ]

        save_items(items)
        reloaded = load_items()

        assert len(reloaded) == 2
        assert reloaded[0]["id"] == "bon-aaa"
        assert reloaded[1]["id"] == "bon-bbb"


    def test_save_deduplicates(self, bon_dir, monkeypatch, capsys):
        """save_items deduplicates by ID, keeping the most recent version."""
        monkeypatch.chdir(bon_dir)
        items = [
            {"id": "bon-aaa", "type": "outcome", "title": "Old", "status": "open",
             "created_at": "2026-01-01T00:00:00Z"},
            {"id": "bon-bbb", "type": "action", "title": "Other", "status": "open",
             "created_at": "2026-01-01T00:00:00Z"},
            {"id": "bon-aaa", "type": "outcome", "title": "New", "status": "open",
             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z"},
        ]

        save_items(items)

        # Check raw file — not load_items, which also deduplicates
        raw_lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        assert len(raw_lines) == 2
        saved = [json.loads(line) for line in raw_lines]
        aaa = next(i for i in saved if i["id"] == "bon-aaa")
        assert aaa["title"] == "New"
        assert any(i["id"] == "bon-bbb" for i in saved)

        captured = capsys.readouterr()
        assert "Deduplicated" in captured.err
        assert "bon-aaa" in captured.err


class TestDataDirCaching:
    def test_cwd_change_doesnt_break_storage(self, bon_dir, tmp_path, monkeypatch):
        """After resolving data dir, CWD changes don't affect storage operations."""
        monkeypatch.chdir(bon_dir)
        items = [
            {"id": "bon-aaa", "type": "outcome", "title": "Test", "status": "open"},
        ]
        save_items(items)

        # Change CWD to a directory with no .bon/
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)

        # load_items should still find the original .bon/
        reloaded = load_items()
        assert len(reloaded) == 1
        assert reloaded[0]["id"] == "bon-aaa"


class TestFindById:
    def test_exact_match(self):
        """Find by exact ID."""
        items = [
            {"id": "bon-aaa", "type": "outcome"},
            {"id": "bon-bbb", "type": "action"},
        ]

        result = find_by_id(items, "bon-bbb")

        assert result["id"] == "bon-bbb"

    def test_not_found(self):
        """Return None when not found."""
        items = [{"id": "bon-aaa", "type": "outcome"}]

        result = find_by_id(items, "bon-zzz")

        assert result is None

    def test_prefix_tolerant(self):
        """Find by suffix when prefix provided."""
        items = [{"id": "bon-aaa", "type": "outcome"}]

        result = find_by_id(items, "aaa", prefix="bon")

        assert result["id"] == "bon-aaa"


class TestLoadPrefix:
    def test_default_prefix(self, bon_dir, monkeypatch):
        """Default prefix is 'bon' when file is missing."""
        monkeypatch.chdir(bon_dir)
        (bon_dir / ".bon" / "prefix").unlink()  # Remove prefix file

        prefix = load_prefix()

        assert prefix == "bon"

    def test_custom_prefix(self, bon_dir, monkeypatch):
        """Read custom prefix from file."""
        monkeypatch.chdir(bon_dir)
        (bon_dir / ".bon" / "prefix").write_text("myproject")

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


class TestArcUserDeprecation:
    def test_arc_user_still_resolves_but_warns(self, monkeypatch, capsys):
        import bon.storage as storage
        monkeypatch.setattr(storage, "_creator_cache", None)
        monkeypatch.delenv("BON_USER", raising=False)
        monkeypatch.setenv("ARC_USER", "legacy-user")
        name = storage.get_creator()
        assert "legacy-user" in name
        assert "ARC_USER is deprecated" in capsys.readouterr().err

    def test_bon_user_does_not_warn(self, monkeypatch, capsys):
        import bon.storage as storage
        monkeypatch.setattr(storage, "_creator_cache", None)
        monkeypatch.setenv("BON_USER", "current-user")
        monkeypatch.setenv("ARC_USER", "legacy-user")
        name = storage.get_creator()
        assert "current-user" in name
        assert "deprecated" not in capsys.readouterr().err
