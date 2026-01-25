"""Tests for migration script."""
import json
from io import StringIO

import pytest

# Import from scripts directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from migrate import migrate_item, migrate_stream, extract_parent


class TestExtractParent:
    def test_finds_parent_child_dependency(self):
        """Extracts parent from parent-child dependency."""
        item = {
            "id": "x.1",
            "dependencies": [
                {"issue_id": "x.1", "depends_on_id": "x", "type": "parent-child"}
            ]
        }
        assert extract_parent(item) == "x"

    def test_returns_none_when_no_dependencies(self):
        """Returns None when no dependencies."""
        item = {"id": "x"}
        assert extract_parent(item) is None

    def test_ignores_non_parent_child(self):
        """Ignores dependencies that aren't parent-child."""
        item = {
            "id": "x",
            "dependencies": [
                {"depends_on_id": "y", "type": "blocks"}
            ]
        }
        assert extract_parent(item) is None


class TestMigrateItem:
    def test_epic_becomes_outcome(self):
        """Epic issue_type maps to outcome."""
        item = {"id": "x", "title": "Test", "issue_type": "epic"}
        result = migrate_item(item)
        assert result["type"] == "outcome"

    def test_task_becomes_action(self):
        """Task issue_type maps to action."""
        item = {"id": "x", "title": "Test", "issue_type": "task"}
        result = migrate_item(item)
        assert result["type"] == "action"

    def test_closed_becomes_done(self):
        """Closed status maps to done."""
        item = {"id": "x", "title": "Test", "status": "closed"}
        result = migrate_item(item)
        assert result["status"] == "done"

    def test_closed_at_becomes_done_at(self):
        """closed_at timestamp preserved as done_at."""
        item = {
            "id": "x",
            "title": "Test",
            "status": "closed",
            "closed_at": "2026-01-15T10:00:00Z"
        }
        result = migrate_item(item)
        assert result["done_at"] == "2026-01-15T10:00:00Z"

    def test_open_stays_open(self):
        """Open status stays open."""
        item = {"id": "x", "title": "Test", "status": "open"}
        result = migrate_item(item)
        assert result["status"] == "open"

    def test_brief_from_description_design_acceptance(self):
        """Brief fields extracted from beads fields."""
        item = {
            "id": "x",
            "title": "Test",
            "description": "Why we do this",
            "design": "What we'll make",
            "acceptance_criteria": "How we know it's done"
        }
        result = migrate_item(item)
        assert result["brief"]["why"] == "Why we do this"
        assert result["brief"]["what"] == "What we'll make"
        assert result["brief"]["done"] == "How we know it's done"

    def test_brief_defaults_when_missing(self):
        """Default brief values when fields missing."""
        item = {"id": "x", "title": "Test"}
        result = migrate_item(item)
        assert result["brief"]["why"] == "Migrated from beads"
        assert result["brief"]["what"] == "See title"
        assert result["brief"]["done"] == "When complete"

    def test_multiline_brief_takes_first_line(self):
        """Multi-line fields take first line only."""
        item = {
            "id": "x",
            "title": "Test",
            "description": "First line\nSecond line\nThird line"
        }
        result = migrate_item(item)
        assert result["brief"]["why"] == "First line"

    def test_order_from_id_suffix(self):
        """Order extracted from ID suffix (x.1 → 1)."""
        item = {"id": "prefix-abc.3", "title": "Test"}
        result = migrate_item(item)
        assert result["order"] == 3

    def test_order_defaults_to_1(self):
        """Order defaults to 1 when no suffix."""
        item = {"id": "prefix-abc", "title": "Test"}
        result = migrate_item(item)
        assert result["order"] == 1

    def test_parent_extracted_for_actions(self):
        """Parent relationship preserved for actions."""
        item = {
            "id": "x.1",
            "title": "Test",
            "issue_type": "task",
            "dependencies": [
                {"depends_on_id": "x", "type": "parent-child"}
            ]
        }
        result = migrate_item(item)
        assert result["parent"] == "x"

    def test_waiting_for_is_none(self):
        """Actions get waiting_for=None."""
        item = {"id": "x.1", "title": "Test", "issue_type": "task"}
        result = migrate_item(item)
        assert result["waiting_for"] is None

    def test_timestamps_preserved(self):
        """created_at and created_by preserved."""
        item = {
            "id": "x",
            "title": "Test",
            "created_at": "2026-01-15T10:00:00Z",
            "created_by": "user"
        }
        result = migrate_item(item)
        assert result["created_at"] == "2026-01-15T10:00:00Z"
        assert result["created_by"] == "user"


class TestMigrateStream:
    def test_stream_migration(self):
        """Migrates multiple items from stream."""
        input_data = (
            '{"id": "x", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "x.1", "title": "Task", "issue_type": "task"}\n'
        )
        input_stream = StringIO(input_data)
        output_stream = StringIO()

        outcomes, actions = migrate_stream(input_stream, output_stream)

        assert outcomes == 1
        assert actions == 1

        output_stream.seek(0)
        lines = output_stream.read().strip().split("\n")
        assert len(lines) == 2

    def test_skips_invalid_json(self):
        """Skips invalid JSON lines with warning."""
        input_data = (
            '{"id": "x", "title": "Valid"}\n'
            'not json\n'
            '{"id": "y", "title": "Also Valid"}\n'
        )
        input_stream = StringIO(input_data)
        output_stream = StringIO()

        outcomes, actions = migrate_stream(input_stream, output_stream)

        # Should process 2 valid items
        output_stream.seek(0)
        lines = output_stream.read().strip().split("\n")
        assert len(lines) == 2

    def test_skips_empty_lines(self):
        """Skips empty lines."""
        input_data = (
            '{"id": "x", "title": "One"}\n'
            '\n'
            '{"id": "y", "title": "Two"}\n'
        )
        input_stream = StringIO(input_data)
        output_stream = StringIO()

        migrate_stream(input_stream, output_stream)

        output_stream.seek(0)
        lines = output_stream.read().strip().split("\n")
        assert len(lines) == 2
