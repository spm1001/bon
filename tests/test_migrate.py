"""Tests for arc migrate CLI command."""
import json

import pytest
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
        """Standalone non-epics are excluded with reason and context."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-orphan", "title": "Orphan Bug", "issue_type": "bug", '
            '"description": "This bug causes problems"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft")

        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 1
        assert len(manifest["orphans_excluded"]) == 1
        assert manifest["orphans_excluded"][0]["id"] == "proj-orphan"
        assert manifest["orphans_excluded"][0]["context"] == "This bug causes problems"
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


class TestMigrateOrphanHandling:
    """Tests for orphan handling options."""

    def test_promote_orphans_to_outcomes(self, tmp_path):
        """--promote-orphans converts orphan tasks to outcomes."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-orphan", "title": "Orphan Bug", "issue_type": "bug", '
            '"description": "Bug description"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft", "--promote-orphans")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 2
        assert len(manifest.get("orphans_excluded", [])) == 0

        orphan_outcome = next(o for o in manifest["outcomes"] if o["id"] == "proj-orphan")
        assert orphan_outcome["type"] == "outcome"
        assert orphan_outcome["_promoted_from_orphan"] is True
        assert "PROMOTED" in result.stderr

    def test_orphan_parent_assigns_to_outcome(self, tmp_path):
        """--orphan-parent assigns orphans to specified outcome."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-orphan", "title": "Orphan Bug", "issue_type": "bug"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft",
                        "--orphan-parent", "proj-abc")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 1
        assert len(manifest.get("orphans_excluded", [])) == 0

        children = manifest["outcomes"][0]["children"]
        assert len(children) == 1
        assert children[0]["id"] == "proj-orphan"
        assert children[0]["_adopted_orphan"] is True
        assert "ADOPTED" in result.stderr

    def test_error_both_orphan_flags(self, tmp_path):
        """Errors when both --promote-orphans and --orphan-parent used."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text('{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n')

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft",
                        "--promote-orphans", "--orphan-parent", "proj-abc")

        assert result.returncode == 1
        assert "Cannot use both" in result.stderr

    def test_error_orphan_parent_not_found(self, tmp_path):
        """Errors when --orphan-parent references non-existent epic."""
        beads_file = tmp_path / "beads.jsonl"
        beads_file.write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
            '{"id": "proj-orphan", "title": "Orphan", "issue_type": "bug"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_file), "--draft",
                        "--orphan-parent", "proj-nonexistent")

        assert result.returncode == 1
        assert "not found" in result.stderr.lower()


class TestOrphanFixtureScenarios:
    """Tests using beads_with_orphans fixture for complex scenarios."""

    @pytest.fixture
    def beads_fixture(self, fixtures_dir):
        """Load the beads_with_orphans fixture."""
        return fixtures_dir / "beads_with_orphans.jsonl"

    def test_default_excludes_multiple_orphans(self, beads_fixture):
        """Default mode excludes all orphans."""
        result = run_arc("migrate", "--from-beads", str(beads_fixture), "--draft")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)

        # 2 epics become outcomes
        assert len(manifest["outcomes"]) == 2

        # 3 orphans excluded
        assert len(manifest["orphans_excluded"]) == 3
        orphan_ids = {o["id"] for o in manifest["orphans_excluded"]}
        assert orphan_ids == {"proj-orphan1", "proj-orphan2", "proj-orphan3"}

    def test_promote_multiple_orphans(self, beads_fixture):
        """--promote-orphans converts all orphans to outcomes."""
        result = run_arc("migrate", "--from-beads", str(beads_fixture), "--draft",
                        "--promote-orphans")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)

        # 2 epics + 3 promoted orphans = 5 outcomes
        assert len(manifest["outcomes"]) == 5
        assert len(manifest.get("orphans_excluded", [])) == 0

        # Check promoted orphans have marker
        promoted = [o for o in manifest["outcomes"] if o.get("_promoted_from_orphan")]
        assert len(promoted) == 3

        # Closed orphan preserves status
        closed_orphan = next(o for o in manifest["outcomes"] if o["id"] == "proj-orphan3")
        assert closed_orphan["status"] == "done"

    def test_adopt_multiple_orphans(self, beads_fixture):
        """--orphan-parent assigns all orphans to one outcome."""
        result = run_arc("migrate", "--from-beads", str(beads_fixture), "--draft",
                        "--orphan-parent", "proj-epic2")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)

        # Still 2 outcomes
        assert len(manifest["outcomes"]) == 2
        assert len(manifest.get("orphans_excluded", [])) == 0

        # All 3 orphans adopted under proj-epic2
        epic2 = next(o for o in manifest["outcomes"] if o["id"] == "proj-epic2")
        adopted = [c for c in epic2["children"] if c.get("_adopted_orphan")]
        assert len(adopted) == 3

        # epic1 still has its original 2 children
        epic1 = next(o for o in manifest["outcomes"] if o["id"] == "proj-epic1")
        assert len(epic1["children"]) == 2

    @pytest.mark.parametrize("mode,expected_outcomes,expected_orphans", [
        ("default", 2, 3),
        ("promote", 5, 0),
        ("adopt", 2, 0),
    ])
    def test_orphan_modes_parametrized(self, beads_fixture, mode, expected_outcomes, expected_orphans):
        """Parametrized test for orphan handling modes."""
        args = ["migrate", "--from-beads", str(beads_fixture), "--draft"]
        if mode == "promote":
            args.append("--promote-orphans")
        elif mode == "adopt":
            args.extend(["--orphan-parent", "proj-epic1"])

        result = run_arc(*args)

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == expected_outcomes
        assert len(manifest.get("orphans_excluded", [])) == expected_orphans


class TestMigrateDirectoryShorthand:
    """Tests for .beads/ directory shorthand."""

    def test_accepts_directory_with_issues_jsonl(self, tmp_path):
        """Accepts .beads/ directory and finds issues.jsonl inside."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()
        (beads_dir / "issues.jsonl").write_text(
            '{"id": "proj-abc", "title": "Epic", "issue_type": "epic"}\n'
        )

        result = run_arc("migrate", "--from-beads", str(beads_dir), "--draft")

        assert result.returncode == 0
        manifest = yaml.safe_load(result.stdout)
        assert len(manifest["outcomes"]) == 1

    def test_error_directory_without_issues_jsonl(self, tmp_path):
        """Errors when directory has no issues.jsonl."""
        beads_dir = tmp_path / ".beads"
        beads_dir.mkdir()

        result = run_arc("migrate", "--from-beads", str(beads_dir), "--draft")

        assert result.returncode == 1
        assert "no issues.jsonl" in result.stderr
