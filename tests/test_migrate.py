"""Tests for migration script."""
import json
import sys
from io import StringIO
from pathlib import Path

import pytest

# Add scripts directory to path for migrate module
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

    def test_multiline_brief_preserved(self):
        """Multi-line fields are preserved in full."""
        item = {
            "id": "x",
            "title": "Test",
            "description": "First line\nSecond line\nThird line"
        }
        result = migrate_item(item)
        assert result["brief"]["why"] == "First line\nSecond line\nThird line"

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


# CLI command tests
import yaml
from conftest import run_arc


class TestMigrateDraft:
    """Tests for arc migrate --from-beads --draft."""

    def test_generates_manifest_yaml(self, tmp_path):
        """Generates valid YAML manifest from beads export."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Test Epic", "issue_type": "epic", '
            '"description": "Why", "design": "What", "notes": "Session notes"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 1
        assert manifest["outcomes"][0]["id"] == "proj-abc"
        assert manifest["outcomes"][0]["type"] == "outcome"

    def test_preserves_beads_context(self, tmp_path):
        """Preserves raw beads fields in _beads."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Test", "issue_type": "epic", '
            '"description": "The description", "design": "The design", '
            '"acceptance_criteria": "The criteria", "notes": "The notes"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        manifest = yaml.safe_load(result.stdout)
        beads_ctx = manifest["outcomes"][0]["_beads"]
        assert beads_ctx["description"] == "The description"
        assert beads_ctx["design"] == "The design"
        assert beads_ctx["acceptance_criteria"] == "The criteria"
        assert beads_ctx["notes"] == "The notes"

    def test_creates_empty_brief_placeholders(self, tmp_path):
        """Creates empty brief fields for Claude to fill."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Test", "issue_type": "epic"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        manifest = yaml.safe_load(result.stdout)
        brief = manifest["outcomes"][0]["brief"]
        assert brief["why"] == ""
        assert brief["what"] == ""
        assert brief["done"] == ""

    def test_nests_children_under_parent(self, tmp_path):
        """Children are nested under their parent outcome."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-abc.1", "title": "Task", "issue_type": "task", '
            '"dependencies": [{"type": "parent-child", "depends_on_id": "proj-abc"}]}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 1
        assert len(manifest["outcomes"][0]["children"]) == 1
        assert manifest["outcomes"][0]["children"][0]["id"] == "proj-abc.1"

    def test_excludes_orphan_actions(self, tmp_path):
        """Standalone non-epics are excluded with reason."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-orphan", "title": "Orphan Bug", "issue_type": "bug"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 1
        assert len(manifest["orphans_excluded"]) == 1
        assert manifest["orphans_excluded"][0]["id"] == "proj-orphan"
        assert "standalone" in manifest["orphans_excluded"][0]["reason"]

    def test_maps_closed_to_done(self, tmp_path):
        """Closed status maps to done."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Done Epic", "issue_type": "epic", "status": "closed"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        manifest = yaml.safe_load(result.stdout)
        assert manifest["outcomes"][0]["status"] == "done"

    def test_reports_summary_to_stderr(self, tmp_path):
        """Reports migration summary to stderr."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-abc.1", "title": "Task", "issue_type": "task", '
            '"dependencies": [{"type": "parent-child", "depends_on_id": "proj-abc"}]}\n'
            '{"id": "proj-orphan", "title": "Orphan", "issue_type": "bug"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        assert "1 outcomes" in result.stderr
        assert "1 actions" in result.stderr
        assert "1 orphans EXCLUDED" in result.stderr

    def test_error_file_not_found(self, tmp_path):
        """Errors when beads file doesn't exist."""
        result = run_arc("migrate", "--from-beads", "/nonexistent.jsonl", "--draft")

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_error_without_draft_flag(self, tmp_path):
        """Errors when --from-beads used without --draft."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text('{"id": "x", "title": "Test", "issue_type": "epic"}\n')

        result = run_arc("migrate", "--from-beads", str(beads_file))

        assert result.returncode == 1
        assert "--draft" in result.stderr


class TestMigrateFromDraft:
    """Tests for arc migrate --from-draft."""

    def test_imports_complete_manifest(self, tmp_path):
        """Imports manifest with complete briefs."""
        manifest_file = tmp_path / "manifest.yaml"
        manifest_file.write_text("""
outcomes:
- id: proj-abc
  title: Test Outcome
  type: outcome
  status: open
  brief:
    why: The reason
    what: The deliverable
    done: The criteria
  children: []
""")
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        result = run_arc("migrate", "--from-draft", str(manifest_file), cwd=work_dir)

        assert result.returncode == 0
        assert "Migrated 1 items" in result.stdout
        assert (work_dir / ".arc" / "items.jsonl").exists()
        assert (work_dir / ".arc" / "prefix").read_text() == "proj"

    def test_strips_beads_context(self, tmp_path):
        """Strips _beads context from imported items."""
        manifest_file = tmp_path / "manifest.yaml"
        manifest_file.write_text("""
outcomes:
- id: proj-abc
  title: Test
  type: outcome
  status: open
  _beads:
    description: Old description
    notes: Old notes
  brief:
    why: Why
    what: What
    done: Done
  children: []
""")
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        run_arc("migrate", "--from-draft", str(manifest_file), cwd=work_dir)

        items_content = (work_dir / ".arc" / "items.jsonl").read_text()
        item = json.loads(items_content.strip())
        assert "_beads" not in item

    def test_rejects_incomplete_brief(self, tmp_path):
        """Rejects items with incomplete briefs."""
        manifest_file = tmp_path / "manifest.yaml"
        manifest_file.write_text("""
outcomes:
- id: proj-abc
  title: Test
  type: outcome
  status: open
  brief:
    why: Has why
    what: ""
    done: ""
  children: []
""")
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        result = run_arc("migrate", "--from-draft", str(manifest_file), cwd=work_dir)

        assert result.returncode == 1
        assert "incomplete brief" in result.stderr
        assert not (work_dir / ".arc").exists()

    def test_rejects_when_arc_exists(self, tmp_path):
        """Rejects migration when .arc/ already exists."""
        manifest_file = tmp_path / "manifest.yaml"
        manifest_file.write_text("""
outcomes:
- id: proj-abc
  title: Test
  type: outcome
  status: open
  brief:
    why: Why
    what: What
    done: Done
  children: []
""")
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        (work_dir / ".arc").mkdir()

        result = run_arc("migrate", "--from-draft", str(manifest_file), cwd=work_dir)

        assert result.returncode == 1
        assert ".arc/ already exists" in result.stderr

    def test_imports_children_as_actions(self, tmp_path):
        """Imports children as actions with parent reference."""
        manifest_file = tmp_path / "manifest.yaml"
        manifest_file.write_text("""
outcomes:
- id: proj-abc
  title: Parent Outcome
  type: outcome
  status: open
  brief:
    why: Why
    what: What
    done: Done
  children:
  - id: proj-abc.1
    title: Child Action
    type: action
    status: open
    brief:
      why: Child why
      what: Child what
      done: Child done
""")
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        run_arc("migrate", "--from-draft", str(manifest_file), cwd=work_dir)

        items_content = (work_dir / ".arc" / "items.jsonl").read_text()
        lines = items_content.strip().split("\n")
        assert len(lines) == 2

        action = json.loads(lines[1])
        assert action["type"] == "action"
        assert action["parent"] == "proj-abc"

    def test_preserves_done_status(self, tmp_path):
        """Preserves done status and adds done_at."""
        manifest_file = tmp_path / "manifest.yaml"
        manifest_file.write_text("""
outcomes:
- id: proj-abc
  title: Done Outcome
  type: outcome
  status: done
  brief:
    why: Why
    what: What
    done: Done
  children: []
""")
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        run_arc("migrate", "--from-draft", str(manifest_file), cwd=work_dir)

        items_content = (work_dir / ".arc" / "items.jsonl").read_text()
        item = json.loads(items_content.strip())
        assert item["status"] == "done"
        assert "done_at" in item

    def test_error_file_not_found(self, tmp_path):
        """Errors when manifest file doesn't exist."""
        result = run_arc("migrate", "--from-draft", "/nonexistent.yaml", cwd=tmp_path)

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()
