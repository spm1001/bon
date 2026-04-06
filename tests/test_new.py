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
        items = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert items["type"] == "outcome"
        assert items["title"] == "Test outcome"
        assert items["brief"]["why"] == "Testing the feature"
        assert items["status"] == "open"

    def test_outcome_gets_order_1(self, arc_dir, monkeypatch):
        """First outcome gets order 1."""
        monkeypatch.chdir(arc_dir)

        run_arc("new", "First", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)

        items = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
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
        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "This is a multi-line title with spaces"


class TestNewAction:
    def test_create_action_under_outcome(self, arc_dir, monkeypatch):
        """arc new --for creates action under outcome."""
        monkeypatch.chdir(arc_dir)

        # Create outcome first
        run_arc("new", "Parent outcome", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        items = (arc_dir / ".bon" / "items.jsonl").read_text().strip()
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
        lines = (arc_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id
        assert action["waiting_for"] is None

    def test_parent_alias_creates_action(self, arc_dir, monkeypatch):
        """--parent works as alias for --outcome in bon new."""
        monkeypatch.chdir(arc_dir)

        run_arc("new", "Parent outcome", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        items = (arc_dir / ".bon" / "items.jsonl").read_text().strip()
        outcome_id = json.loads(items)["id"]

        result = run_arc(
            "new", "Child via --parent",
            "--parent", outcome_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0

        lines = (arc_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id

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
        outcome_id = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        run_arc("new", "Action", "--outcome", outcome_id, "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        lines = (arc_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action_id = next(i for i in items if i["type"] == "action")["id"]

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
        outcome_id = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

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

        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "Add rate limiting"
        assert item["type"] == "outcome"


class TestNewJsonStdin:
    """JSON stdin input for bon new --json."""

    def test_json_creates_outcome(self, arc_dir, monkeypatch):
        """bon new --json creates outcome from stdin JSON."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "JSON outcome",
            "brief": {"why": "testing", "what": "a thing", "done": "it works"}
        })
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 0
        assert "Created:" in result.stdout

        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["type"] == "outcome"
        assert item["title"] == "JSON outcome"
        assert item["brief"]["why"] == "testing"

    def test_json_creates_action_with_parent(self, arc_dir, monkeypatch):
        """bon new --json with parent creates action."""
        monkeypatch.chdir(arc_dir)

        # Create outcome first
        run_arc("new", "Parent", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        outcome_id = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        data = json.dumps({
            "title": "JSON action",
            "parent": outcome_id,
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 0
        lines = (arc_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id

    def test_json_missing_brief_fields_errors(self, arc_dir, monkeypatch):
        """Missing required brief fields produce error."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({"title": "Incomplete", "brief": {"why": "only why"}})
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 1
        assert "Brief required. Missing:" in result.stderr
        assert "--what" in result.stderr
        assert "--done" in result.stderr

    def test_json_missing_title_errors(self, arc_dir, monkeypatch):
        """Missing title in JSON produces error."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({"brief": {"why": "w", "what": "x", "done": "d"}})
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 1
        assert "JSON must include 'title'" in result.stderr

    def test_json_bad_parent_errors(self, arc_dir, monkeypatch):
        """Non-existent parent in JSON produces error."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "Orphan",
            "parent": "arc-nonexistent",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_json_outcome_language_warning(self, arc_dir, monkeypatch):
        """Activity-verb outcome title warns even via JSON."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "Implement OAuth",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 0
        assert "activity, not achievement" in result.stderr

    def test_json_with_quiet(self, arc_dir, monkeypatch):
        """--json with -q outputs just the ID."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "Quiet JSON",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", "--json", "-q", cwd=arc_dir, input=data)

        assert result.returncode == 0
        assert result.stdout.strip().startswith("arc-")
        assert "Created:" not in result.stdout

    def test_json_with_how(self, arc_dir, monkeypatch):
        """Optional how field preserved via JSON."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "With approach",
            "brief": {"why": "w", "how": "the approach", "what": "x", "done": "d"}
        })
        result = run_arc("new", "--json", cwd=arc_dir, input=data)

        assert result.returncode == 0
        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["how"] == "the approach"

    def test_json_invalid_json_errors(self, arc_dir, monkeypatch):
        """Invalid JSON on stdin produces error."""
        monkeypatch.chdir(arc_dir)

        result = run_arc("new", "--json", cwd=arc_dir, input="not json at all")

        assert result.returncode == 1
        assert "Invalid JSON on stdin" in result.stderr

    def test_no_title_without_json_flag_errors(self, arc_dir, monkeypatch):
        """Omitting title without piped stdin produces helpful error."""
        monkeypatch.chdir(arc_dir)

        result = run_arc("new", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)

        assert result.returncode == 1
        assert "stdin" in result.stderr

    def test_implicit_json_from_piped_stdin(self, arc_dir, monkeypatch):
        """Piping JSON without --json flag auto-detects JSON input."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "Implicit JSON",
            "brief": {"why": "testing", "what": "a thing", "done": "it works"}
        })
        # No --json flag — just pipe stdin
        result = run_arc("new", cwd=arc_dir, input=data)

        assert result.returncode == 0
        assert "Created:" in result.stdout

        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "Implicit JSON"
        assert item["brief"]["why"] == "testing"

    def test_implicit_json_with_parent(self, arc_dir, monkeypatch):
        """Piped JSON with parent field creates action without --json flag."""
        monkeypatch.chdir(arc_dir)

        run_arc("new", "Parent", "--why", "w", "--what", "x", "--done", "d", cwd=arc_dir)
        outcome_id = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        data = json.dumps({
            "title": "Implicit child",
            "parent": outcome_id,
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", cwd=arc_dir, input=data)

        assert result.returncode == 0
        lines = (arc_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id

    def test_implicit_json_with_quiet(self, arc_dir, monkeypatch):
        """Piped JSON with -q outputs just the ID."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "Quiet implicit",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", "-q", cwd=arc_dir, input=data)

        assert result.returncode == 0
        assert result.stdout.strip().startswith("arc-")
        assert "Created:" not in result.stdout


class TestStandaloneAction:
    """Standalone actions via explicit type field in JSON stdin."""

    def test_json_type_action_creates_standalone_action(self, arc_dir, monkeypatch):
        """Explicit type=action with no parent creates a standalone action."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "type": "action",
            "title": "Fix a typo in docs",
            "brief": {"why": "typo spotted", "what": "fix it", "done": "no typo"}
        })
        result = run_arc("new", cwd=arc_dir, input=data)

        assert result.returncode == 0
        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["type"] == "action"
        assert item["parent"] is None
        assert item["waiting_for"] is None

    def test_json_no_type_no_parent_creates_outcome(self, arc_dir, monkeypatch):
        """No explicit type and no parent still creates an outcome (default)."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "title": "Docs are accurate",
            "brief": {"why": "accuracy", "what": "review", "done": "reviewed"}
        })
        result = run_arc("new", cwd=arc_dir, input=data)

        assert result.returncode == 0
        item = json.loads((arc_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["type"] == "outcome"

    def test_standalone_action_no_outcome_language_warning(self, arc_dir, monkeypatch):
        """Standalone actions skip outcome language lint."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "type": "action",
            "title": "Implement the fix",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_arc("new", cwd=arc_dir, input=data)

        assert result.returncode == 0
        assert result.stderr == ""  # No activity-language warning

    def test_standalone_action_appears_in_standalone_section(self, arc_dir, monkeypatch):
        """Standalone actions show in the Standalone section of bon list."""
        monkeypatch.chdir(arc_dir)

        data = json.dumps({
            "type": "action",
            "title": "Field report: something odd",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        run_arc("new", cwd=arc_dir, input=data)

        result = run_arc("list", cwd=arc_dir)
        assert "Standalone:" in result.stdout
        assert "Field report: something odd" in result.stdout


class TestNewNotInitialized:
    def test_error_when_not_initialized(self, tmp_path, monkeypatch):
        """Error when .arc/ doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("new", "Test", "--why", "w", "--what", "x", "--done", "d", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr
