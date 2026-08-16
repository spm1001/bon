"""Tests for bon new command."""
import json

from conftest import run_bon


class TestNewOutcome:
    def test_create_outcome(self, bon_dir, monkeypatch):
        """bon new creates an outcome with brief."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Test outcome",
            "--why", "Testing the feature",
            "--what", "A working test",
            "--done", "Tests pass",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert "Created" in result.stdout

        # Verify the item was saved
        items = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert items["type"] == "outcome"
        assert items["title"] == "Test outcome"
        assert items["brief"]["why"] == "Testing the feature"
        assert items["status"] == "open"

    def test_outcome_gets_order_1(self, bon_dir, monkeypatch):
        """First outcome gets order 1."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "First", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)

        items = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert items["order"] == 1

    def test_empty_title_rejected(self, bon_dir, monkeypatch):
        """Empty title is rejected."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "   ",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 1
        assert "Title cannot be empty" in result.stderr

    def test_multiline_title_normalized(self, bon_dir, monkeypatch):
        """Multi-line titles are normalized to single line."""
        monkeypatch.chdir(bon_dir)

        # Title with newlines and extra spaces
        result = run_bon(
            "new", "This is\na multi-line\n\ntitle  with   spaces",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0

        # Verify title was normalized
        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "This is a multi-line title with spaces"


class TestNewAction:
    def test_create_action_under_outcome(self, bon_dir, monkeypatch):
        """bon new --for creates action under outcome."""
        monkeypatch.chdir(bon_dir)

        # Create outcome first
        run_bon("new", "Parent outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        items = (bon_dir / ".bon" / "items.jsonl").read_text().strip()
        outcome_id = json.loads(items)["id"]

        # Create action under it (--outcome is primary flag)
        result = run_bon(
            "new", "Child action",
            "--outcome", outcome_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0

        # Verify action
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id
        assert action["waiting_for"] is None

    def test_parent_alias_creates_action(self, bon_dir, monkeypatch):
        """--parent works as alias for --outcome in bon new."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "Parent outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        items = (bon_dir / ".bon" / "items.jsonl").read_text().strip()
        outcome_id = json.loads(items)["id"]

        result = run_bon(
            "new", "Child via --parent",
            "--parent", outcome_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0

        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id

    def test_action_parent_not_found(self, bon_dir, monkeypatch):
        """Error when parent doesn't exist."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Orphan",
            "--outcome", "bon-nonexistent",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 1
        assert "Parent 'bon-nonexistent' not found" in result.stderr

    def test_action_parent_must_be_outcome(self, bon_dir, monkeypatch):
        """Error when parent is an action, not outcome."""
        monkeypatch.chdir(bon_dir)

        # Create outcome and action
        run_bon("new", "Outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        outcome_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        run_bon("new", "Action", "--outcome", outcome_id, "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action_id = next(i for i in items if i["type"] == "action")["id"]

        # Try to create action under action
        result = run_bon(
            "new", "Nested",
            "--outcome", action_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr


class TestNewBriefRequired:
    def test_missing_brief_flags_error(self, bon_dir, monkeypatch):
        """Error when brief flags missing in non-interactive mode."""
        monkeypatch.chdir(bon_dir)

        result = run_bon("new", "Test", "--why", "only why", cwd=bon_dir)

        assert result.returncode == 1
        assert "Brief required. Missing:" in result.stderr
        assert "--what" in result.stderr
        assert "--done" in result.stderr


class TestOutcomeLanguageLint:
    """Activity-language warnings for outcome titles."""

    def test_activity_verb_warns(self, bon_dir, monkeypatch):
        """Outcome starting with activity verb produces warning."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Implement OAuth",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert "Created" in result.stdout
        assert "activity, not achievement" in result.stderr

    def test_achievement_language_no_warning(self, bon_dir, monkeypatch):
        """Outcome with achievement language produces no warning."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Users can authenticate with GitHub",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_action_no_warning(self, bon_dir, monkeypatch):
        """Actions don't trigger activity-language warning."""
        monkeypatch.chdir(bon_dir)

        # Create outcome first
        run_bon("new", "Auth works", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        outcome_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        result = run_bon(
            "new", "Implement the callback endpoint",
            "--outcome", outcome_id,
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_case_insensitive(self, bon_dir, monkeypatch):
        """Warning works regardless of title case."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "BUILD the new pipeline",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert "activity, not achievement" in result.stderr

    def test_verb_must_be_at_start(self, bon_dir, monkeypatch):
        """Verb in middle of title doesn't trigger warning."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Team can build dashboards independently",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert result.stderr == ""

    def test_item_still_created_despite_warning(self, bon_dir, monkeypatch):
        """Warning doesn't prevent item creation."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Add rate limiting",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        assert "Created" in result.stdout

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "Add rate limiting"
        assert item["type"] == "outcome"


class TestNewJsonStdin:
    """JSON stdin input for bon new --json."""

    def test_json_creates_outcome(self, bon_dir, monkeypatch):
        """bon new --json creates outcome from stdin JSON."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "JSON outcome",
            "brief": {"why": "testing", "what": "a thing", "done": "it works"}
        })
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert "Created" in result.stdout

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["type"] == "outcome"
        assert item["title"] == "JSON outcome"
        assert item["brief"]["why"] == "testing"

    def test_json_creates_action_with_parent(self, bon_dir, monkeypatch):
        """bon new --json with parent creates action."""
        monkeypatch.chdir(bon_dir)

        # Create outcome first
        run_bon("new", "Parent", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        outcome_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        data = json.dumps({
            "title": "JSON action",
            "parent": outcome_id,
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 0
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id

    def test_json_missing_brief_fields_errors(self, bon_dir, monkeypatch):
        """Missing required brief fields produce error."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({"title": "Incomplete", "brief": {"why": "only why"}})
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "Brief required. Missing:" in result.stderr
        assert "--what" in result.stderr
        assert "--done" in result.stderr

    def test_json_missing_title_errors(self, bon_dir, monkeypatch):
        """Missing title in JSON produces error."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({"brief": {"why": "w", "what": "x", "done": "d"}})
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "JSON must include 'title'" in result.stderr

    def test_json_bad_parent_errors(self, bon_dir, monkeypatch):
        """Non-existent parent in JSON produces error."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Orphan",
            "parent": "bon-nonexistent",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_json_outcome_language_warning(self, bon_dir, monkeypatch):
        """Activity-verb outcome title warns even via JSON."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Implement OAuth",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert "activity, not achievement" in result.stderr

    def test_json_with_quiet(self, bon_dir, monkeypatch):
        """--json with -q outputs just the ID."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Quiet JSON",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", "--json", "-q", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert result.stdout.strip().startswith("bon-")
        assert "Created" not in result.stdout

    def test_json_with_how(self, bon_dir, monkeypatch):
        """Optional how field preserved via JSON."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "With approach",
            "brief": {"why": "w", "how": "the approach", "what": "x", "done": "d"}
        })
        result = run_bon("new", "--json", cwd=bon_dir, input=data)

        assert result.returncode == 0
        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["how"] == "the approach"

    def test_json_invalid_json_errors(self, bon_dir, monkeypatch):
        """Invalid JSON on stdin produces error."""
        monkeypatch.chdir(bon_dir)

        result = run_bon("new", "--json", cwd=bon_dir, input="not json at all")

        assert result.returncode == 1
        assert "Invalid JSON on stdin" in result.stderr

    def test_no_title_without_json_flag_errors(self, bon_dir, monkeypatch):
        """Omitting title without piped stdin produces helpful error."""
        monkeypatch.chdir(bon_dir)

        result = run_bon("new", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)

        assert result.returncode == 1
        assert "stdin" in result.stderr

    def test_implicit_json_from_piped_stdin(self, bon_dir, monkeypatch):
        """Piping JSON without --json flag auto-detects JSON input."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Implicit JSON",
            "brief": {"why": "testing", "what": "a thing", "done": "it works"}
        })
        # No --json flag — just pipe stdin
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert "Created" in result.stdout

        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "Implicit JSON"
        assert item["brief"]["why"] == "testing"

    def test_implicit_json_with_parent(self, bon_dir, monkeypatch):
        """Piped JSON with parent field creates action without --json flag."""
        monkeypatch.chdir(bon_dir)

        run_bon("new", "Parent", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
        outcome_id = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]

        data = json.dumps({
            "title": "Implicit child",
            "parent": outcome_id,
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        action = next(i for i in items if i["type"] == "action")
        assert action["parent"] == outcome_id

    def test_implicit_json_with_quiet(self, bon_dir, monkeypatch):
        """Piped JSON with -q outputs just the ID."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Quiet implicit",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", "-q", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert result.stdout.strip().startswith("bon-")
        assert "Created" not in result.stdout


class TestStandaloneAction:
    """Standalone actions via explicit type field in JSON stdin."""

    def test_json_type_action_creates_standalone_action(self, bon_dir, monkeypatch):
        """Explicit type=action with no parent creates a standalone action."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Fix a typo in docs",
            "brief": {"why": "typo spotted", "what": "fix it", "done": "no typo"}
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["type"] == "action"
        assert item["parent"] is None
        assert item["waiting_for"] is None

    def test_json_no_type_no_parent_creates_outcome(self, bon_dir, monkeypatch):
        """No explicit type and no parent still creates an outcome (default)."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Docs are accurate",
            "brief": {"why": "accuracy", "what": "review", "done": "reviewed"}
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        item = json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())
        assert item["type"] == "outcome"

    def test_standalone_action_no_outcome_language_warning(self, bon_dir, monkeypatch):
        """Standalone actions skip outcome language lint."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Implement the fix",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert result.stderr == ""  # No activity-language warning

    def test_standalone_action_appears_in_standalone_section(self, bon_dir, monkeypatch):
        """Standalone actions show in the Standalone section of bon list."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Field report: something odd",
            "brief": {"why": "w", "what": "x", "done": "d"}
        })
        run_bon("new", cwd=bon_dir, input=data)

        result = run_bon("list", cwd=bon_dir)
        assert "Standalone:" in result.stdout
        assert "Field report: something odd" in result.stdout


class TestNewNotInitialized:
    def test_error_when_not_initialized(self, tmp_path, monkeypatch):
        """Error when .bon/ doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("new", "Test", "--why", "w", "--what", "x", "--done", "d", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


def _read_items(bon_dir):
    lines = (bon_dir / ".bon" / "items.jsonl").read_text().strip().split("\n")
    return [json.loads(line) for line in lines]


def _mk_outcome(bon_dir):
    run_bon("new", "Host outcome", "--why", "w", "--what", "x", "--done", "d", cwd=bon_dir)
    return _read_items(bon_dir)[0]["id"]


class TestNewJsonWaitingFor:
    """JSON stdin honours waiting_for at creation (bon-gezela)."""

    def test_waiting_for_list_stored_and_reported(self, bon_dir, monkeypatch):
        """An action can be born blocked; the confirmation names the blockers."""
        monkeypatch.chdir(bon_dir)
        outcome_id = _mk_outcome(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Born blocked",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": [outcome_id, "external review"],
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert f"waiting for: {outcome_id}, external review" in result.stdout
        created = next(i for i in _read_items(bon_dir) if i["title"] == "Born blocked")
        assert created["waiting_for"] == [outcome_id, "external review"]

    def test_waiting_for_string_normalised_to_list(self, bon_dir, monkeypatch):
        """A bare string blocker lands as a one-element list."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Blocked by one",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": "external review",
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        created = next(i for i in _read_items(bon_dir) if i["title"] == "Blocked by one")
        assert created["waiting_for"] == ["external review"]

    def test_waiting_for_empty_list_is_none(self, bon_dir, monkeypatch):
        """An empty waiting_for list normalises to None, matching unwait."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Not actually blocked",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": [],
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        created = next(i for i in _read_items(bon_dir) if i["title"] == "Not actually blocked")
        assert created["waiting_for"] is None

    def test_waiting_for_invalid_shape_errors(self, bon_dir, monkeypatch):
        """Non-string blockers are refused loudly."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Bad blockers",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": [42],
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "'waiting_for' must be a string or a list" in result.stderr

    def test_waiting_for_warns_on_unresolvable_id(self, bon_dir, monkeypatch):
        """An id-shaped blocker that doesn't exist gets cmd_wait's warning."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Waiting on a ghost",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": ["bon-nonexistent"],
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        assert "not found in active items" in result.stderr

    def test_born_blocked_excluded_from_ready(self, bon_dir, monkeypatch):
        """A born-blocked action is genuinely blocked, not just decorated."""
        monkeypatch.chdir(bon_dir)
        outcome_id = _mk_outcome(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Born blocked",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": [outcome_id],
        })
        run_bon("new", cwd=bon_dir, input=data)

        result = run_bon("list", "--ready", cwd=bon_dir)
        assert "Born blocked" not in result.stdout

    def test_unblock_on_done_clears_birth_blocker(self, bon_dir, monkeypatch):
        """The unblock-on-done cascade treats a birth blocker like any other."""
        monkeypatch.chdir(bon_dir)
        outcome_id = _mk_outcome(bon_dir)

        data = json.dumps({
            "type": "action",
            "title": "Born blocked",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "waiting_for": [outcome_id],
        })
        run_bon("new", cwd=bon_dir, input=data)
        run_bon("done", outcome_id, cwd=bon_dir)

        created = next(i for i in _read_items(bon_dir) if i["title"] == "Born blocked")
        assert created["waiting_for"] is None


class TestNewJsonKeyContract:
    """Unknown keys are hard errors; flat brief fields are accepted (cefisu parity)."""

    def test_unknown_top_level_key_errors(self, bon_dir, monkeypatch):
        """The key that used to vanish silently now refuses loudly."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "With stowaway",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "priority": 1,
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "Unknown field(s): priority" in result.stderr

    def test_unknown_brief_key_errors(self, bon_dir, monkeypatch):
        """Unknown keys inside brief are refused too."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "With stowaway",
            "brief": {"why": "w", "what": "x", "done": "d", "urgency": "high"},
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "Unknown field(s): urgency" in result.stderr

    def test_flat_brief_fields_accepted(self, bon_dir, monkeypatch):
        """Brief fields given flat land nested in the stored brief."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Flat brief",
            "why": "w", "what": "x", "done": "d", "how": "h",
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        created = next(i for i in _read_items(bon_dir) if i["title"] == "Flat brief")
        assert created["brief"] == {"why": "w", "what": "x", "done": "d", "how": "h"}

    def test_flat_and_nested_conflict_errors(self, bon_dir, monkeypatch):
        """The same brief field flat and nested is ambiguous — refuse."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Conflicted",
            "why": "flat why",
            "brief": {"why": "nested why", "what": "x", "done": "d"},
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "given both flat and inside 'brief'" in result.stderr

    def test_non_string_brief_value_errors(self, bon_dir, monkeypatch):
        """A non-string brief value is refused, not stored as-is."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "title": "Typed wrong",
            "brief": {"why": 3, "what": "x", "done": "d"},
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "'why' must be a string" in result.stderr

    def test_bad_type_value_errors(self, bon_dir, monkeypatch):
        """A typo'd type no longer silently creates an outcome."""
        monkeypatch.chdir(bon_dir)

        data = json.dumps({
            "type": "actoin",
            "title": "Mistyped",
            "brief": {"why": "w", "what": "x", "done": "d"},
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 1
        assert "'type' must be 'action' or 'outcome'" in result.stderr

    def test_outcome_key_aliases_parent(self, bon_dir, monkeypatch):
        """'outcome' works as an alias for 'parent', matching bon edit."""
        monkeypatch.chdir(bon_dir)
        outcome_id = _mk_outcome(bon_dir)

        data = json.dumps({
            "title": "Child via alias",
            "outcome": outcome_id,
            "brief": {"why": "w", "what": "x", "done": "d"},
        })
        result = run_bon("new", cwd=bon_dir, input=data)

        assert result.returncode == 0
        created = next(i for i in _read_items(bon_dir) if i["title"] == "Child via alias")
        assert created["type"] == "action"
        assert created["parent"] == outcome_id


class TestSpeciesAnnouncement:
    """A bare `bon new TITLE` mints an OUTCOME with no error — the species in
    the confirmation is the only signal (bon-siciri verdict c)."""

    def test_outcome_named(self, bon_dir):
        r = run_bon("new", "Things improve", "--why", "w", "--what", "x",
                    "--done", "d", cwd=bon_dir)
        assert "Created outcome:" in r.stdout

    def test_action_named(self, bon_dir):
        r = run_bon("new", cwd=bon_dir,
                    input='{"type":"action","title":"Loud action","brief":{"why":"w","what":"x","done":"d"}}')
        assert "Created action:" in r.stdout

    def test_quiet_still_id_only(self, bon_dir):
        r = run_bon("new", "Quiet outcome", "--why", "w", "--what", "x",
                    "--done", "d", "-q", cwd=bon_dir)
        assert r.stdout.strip().startswith("bon-")
        assert "Created" not in r.stdout
