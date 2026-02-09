"""Tests for arc new command."""
import json

from conftest import run_arc


class TestNewOutcome:
    def test_create_outcome(self, arc_dir, monkeypatch):
        """arc new creates an outcome with brief."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Test outcome",
            "--why", "Testing the feature",
            "--what", "A working test",
            "--done", "Tests pass",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert "Created:" in result.stdout

        # Verify the item was saved
        items = json.loads((arc_dir / ".arc" / "items.jsonl").read_text().strip())
        assert items["type"] == "outcome"
        assert items["title"] == "Test outcome"
        assert items["brief"]["why"] == "Testing the feature"
        assert items["status"] == "open"

    def test_outcome_gets_order_1(self, arc_dir, monkeypatch):
        """First outcome gets order 1."""
        monkeypatch.chdir(arc_dir)

        run_arc("new", "First", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)

        items = json.loads((arc_dir / ".arc" / "items.jsonl").read_text().strip())
        assert items["order"] == 1

    def test_empty_title_rejected(self, arc_dir, monkeypatch):
        """Empty title is rejected."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "   ",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 1
        assert "Title cannot be empty" in result.stderr

    def test_multiline_title_normalized(self, arc_dir, monkeypatch):
        """Multi-line titles are normalized to single line."""
        monkeypatch.chdir(arc_dir)

        # Title with newlines and extra spaces
        result = run_arc(
            "new", "This is\na multi-line\n\ntitle  with   spaces",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0

        # Verify title was normalized
        item = json.loads((arc_dir / ".arc" / "items.jsonl").read_text().strip())
        assert item["title"] == "This is a multi-line title with spaces"


class TestNewAction:
    def test_create_action_under_outcome(self, arc_dir, monkeypatch):
        """arc new --for creates action under outcome."""
        monkeypatch.chdir(arc_dir)

        # Create outcome first
        run_arc("new", "Parent outcome", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        items = (arc_dir / ".arc" / "items.jsonl").read_text().strip()
        outcome_id = json.loads(items)["id"]

        # Create action under it (--outcome is primary flag)
        result = run_arc(
            "new", "Child action",
            "--outcome", outcome_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0

        # Verify action
        lines = (arc_dir / ".arc" / "items.jsonl").read_text().strip().split("\n")
        action = json.loads(lines[1])
        assert action["type"] == "action"
        assert action["parent"] == outcome_id
        assert action["waiting_for"] is None

    def test_action_parent_not_found(self, arc_dir, monkeypatch):
        """Error when parent doesn't exist."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Orphan",
            "--outcome", "arc-nonexistent",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 1
        assert "Parent 'arc-nonexistent' not found" in result.stderr

    def test_action_parent_must_be_outcome(self, arc_dir, monkeypatch):
        """Error when parent is an action, not outcome."""
        monkeypatch.chdir(arc_dir)

        # Create outcome and action
        run_arc("new", "Outcome", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        outcome_id = json.loads((arc_dir / ".arc" / "items.jsonl").read_text().strip())["id"]

        run_arc("new", "Action", "--outcome", outcome_id, "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        lines = (arc_dir / ".arc" / "items.jsonl").read_text().strip().split("\n")
        action_id = json.loads(lines[1])["id"]

        # Try to create action under action
        result = run_arc(
            "new", "Nested",
            "--outcome", action_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr


class TestNewBriefRequired:
    def test_missing_brief_flags_error(self, arc_dir, monkeypatch):
        """Error when brief flags missing in non-interactive mode."""
        monkeypatch.chdir(arc_dir)

        result = run_arc("new", "Test", "--why", "only why", cwd=arc_dir)

        assert result.returncode == 1
        assert "Brief required. Missing:" in result.stderr
        assert "--what" in result.stderr
        assert "--done" in result.stderr


class TestOutcomeLanguageLint:
    """Activity-language warnings for outcome titles."""

    def test_activity_verb_warns(self, arc_dir, monkeypatch):
        """Outcome starting with activity verb produces warning."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Implement OAuth",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert "Created:" in result.stdout
        assert "activity, not achievement" in result.stderr

    def test_achievement_language_no_warning(self, arc_dir, monkeypatch):
        """Outcome with achievement language produces no warning."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Users can authenticate with GitHub",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_action_no_warning(self, arc_dir, monkeypatch):
        """Actions don't trigger activity-language warning."""
        monkeypatch.chdir(arc_dir)

        # Create outcome first
        run_arc("new", "Auth works", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        outcome_id = json.loads((arc_dir / ".arc" / "items.jsonl").read_text().strip())["id"]

        result = run_arc(
            "new", "Implement the callback endpoint",
            "--outcome", outcome_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_case_insensitive(self, arc_dir, monkeypatch):
        """Warning works regardless of title case."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "BUILD the new pipeline",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert "activity, not achievement" in result.stderr

    def test_verb_must_be_at_start(self, arc_dir, monkeypatch):
        """Verb in middle of title doesn't trigger warning."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Team can build dashboards independently",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_item_still_created_despite_warning(self, arc_dir, monkeypatch):
        """Warning doesn't prevent item creation."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Add rate limiting",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        assert "Created:" in result.stdout

        item = json.loads((arc_dir / ".arc" / "items.jsonl").read_text().strip())
        assert item["title"] == "Add rate limiting"
        assert item["type"] == "outcome"


class TestNewNotInitialized:
    def test_error_when_not_initialized(self, tmp_path, monkeypatch):
        """Error when .arc/ doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("new", "Test", "--why", "w", "--what", "x", "--done", "d", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr
