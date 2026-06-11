"""Tests for bon list command - snapshot tests against fixtures."""
import pytest
from conftest import run_bon

# Expected outputs for snapshot tests
EXPECTED_LIST_DEFAULT = {
    "empty": "No outcomes.\n",

    "single_outcome": "○ User auth (bon-aaa)\n",

    "outcome_with_actions": """\
○ User auth (bon-aaa)
  1. ✓ Add endpoint (bon-bbb)
  2. ○ Add UI (bon-ccc)
""",

    "waiting_dependency": """\
○ Deploy (bon-aaa)
  1. ○ Run tests (bon-bbb) ⏳ bon-ccc
  2. ○ Security review (bon-ccc)
""",

    "multiple_outcomes": """\
○ First outcome (bon-aaa)
  1. ○ Action for first (bon-ccc)

○ Second outcome (bon-bbb)
  1. ○ Action for second (bon-ddd)
""",

    "standalone_actions": """\
Standalone:
  ○ Field Report: OAuth flaky (bon-aaa)
  ○ Quick fix for typo (bon-bbb)
""",

    "all_waiting": """\
○ Ship release (bon-aaa)
  1. ○ Legal review (bon-bbb) ⏳ external counsel
  2. ○ Security audit (bon-ccc) ⏳ bon-bbb
""",
}


EXPECTED_LIST_READY = {
    "outcome_with_actions": """\
○ User auth (bon-aaa)
  1. ✓ Add endpoint (bon-bbb)
  2. ○ Add UI (bon-ccc)
""",

    "waiting_dependency": """\
○ Deploy (bon-aaa)
  2. ○ Security review (bon-ccc)
  (+1 waiting)
""",

    "all_waiting": """\
○ Ship release (bon-aaa)
  (2 waiting)
""",
}


EXPECTED_LIST_WAITING = {
    "waiting_dependency": """\
○ Deploy (bon-aaa)
  1. ○ Run tests (bon-bbb) ⏳ bon-ccc
""",

    "all_waiting": """\
○ Ship release (bon-aaa)
  1. ○ Legal review (bon-bbb) ⏳ external counsel
  2. ○ Security audit (bon-ccc) ⏳ bon-bbb
""",
}


class TestListDefault:
    """Test bon list (default mode)."""

    @pytest.mark.parametrize("bon_dir_with_fixture,expected", [
        ("empty", EXPECTED_LIST_DEFAULT["empty"]),
        ("single_outcome", EXPECTED_LIST_DEFAULT["single_outcome"]),
        ("outcome_with_actions", EXPECTED_LIST_DEFAULT["outcome_with_actions"]),
        ("waiting_dependency", EXPECTED_LIST_DEFAULT["waiting_dependency"]),
        ("multiple_outcomes", EXPECTED_LIST_DEFAULT["multiple_outcomes"]),
        ("standalone_actions", EXPECTED_LIST_DEFAULT["standalone_actions"]),
        ("all_waiting", EXPECTED_LIST_DEFAULT["all_waiting"]),
    ], indirect=["bon_dir_with_fixture"])
    def test_list_default(self, bon_dir_with_fixture, expected, monkeypatch):
        """bon list output matches expected for each fixture."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", cwd=bon_dir_with_fixture)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"


class TestListReady:
    """Test bon list --ready."""

    @pytest.mark.parametrize("bon_dir_with_fixture,expected", [
        ("outcome_with_actions", EXPECTED_LIST_READY["outcome_with_actions"]),
        ("waiting_dependency", EXPECTED_LIST_READY["waiting_dependency"]),
        ("all_waiting", EXPECTED_LIST_READY["all_waiting"]),
    ], indirect=["bon_dir_with_fixture"])
    def test_list_ready(self, bon_dir_with_fixture, expected, monkeypatch):
        """bon list --ready shows ready and done actions for context."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--ready", cwd=bon_dir_with_fixture)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"


class TestListWaiting:
    """Test bon list --waiting."""

    @pytest.mark.parametrize("bon_dir_with_fixture,expected", [
        ("waiting_dependency", EXPECTED_LIST_WAITING["waiting_dependency"]),
        ("all_waiting", EXPECTED_LIST_WAITING["all_waiting"]),
    ], indirect=["bon_dir_with_fixture"])
    def test_list_waiting(self, bon_dir_with_fixture, expected, monkeypatch):
        """bon list --waiting shows only waiting actions."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--waiting", cwd=bon_dir_with_fixture)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"


class TestListNotInitialized:
    """Test bon list when not initialized."""

    def test_error_when_not_initialized(self, tmp_path, monkeypatch):
        """Error when .bon/ doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("list", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr

    def test_not_initialized_names_searched_directory(self, tmp_path, monkeypatch):
        """The error names the cwd the walk-up searched from."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("list", cwd=tmp_path)

        assert result.returncode == 1
        assert str(tmp_path.resolve()) in result.stderr


class TestListLimit:
    """Test bon list --limit N truncates to first N top-level items."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_limit_truncates_outcomes(self, bon_dir_with_fixture, monkeypatch):
        """--limit 1 keeps only the first outcome (with its children)."""
        monkeypatch.chdir(bon_dir_with_fixture)
        expected = """\
○ First outcome (bon-aaa)
  1. ○ Action for first (bon-ccc)
"""
        result = run_bon("list", "--limit", "1", cwd=bon_dir_with_fixture)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_limit_larger_than_available(self, bon_dir_with_fixture, monkeypatch):
        """--limit N where N > available returns everything."""
        monkeypatch.chdir(bon_dir_with_fixture)
        result_unlimited = run_bon("list", cwd=bon_dir_with_fixture)
        result_limited = run_bon("list", "--limit", "100", cwd=bon_dir_with_fixture)
        assert result_limited.returncode == 0
        assert result_limited.stdout == result_unlimited.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_spans_outcomes_and_standalones(self, bon_dir_with_fixture, monkeypatch):
        """--limit consumes outcomes first, then spends remaining budget on standalones."""
        monkeypatch.chdir(bon_dir_with_fixture)
        expected = """\
○ First outcome (bon-aaa)
  1. ○ Action for first (bon-ccc)

○ Second outcome (bon-bbb)

Standalone:
  ○ Standalone one (bon-ddd)
"""
        result = run_bon("list", "--limit", "3", cwd=bon_dir_with_fixture)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_under_outcome_count_drops_standalones(self, bon_dir_with_fixture, monkeypatch):
        """--limit smaller than outcome count drops all standalones."""
        monkeypatch.chdir(bon_dir_with_fixture)
        result = run_bon("list", "--limit", "1", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        assert "Standalone:" not in result.stdout
        assert "bon-aaa" in result.stdout
        assert "bon-bbb" not in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_zero_treated_as_no_limit(self, bon_dir_with_fixture, monkeypatch):
        """--limit 0 is permissive, not exclusive — returns everything."""
        monkeypatch.chdir(bon_dir_with_fixture)
        result_zero = run_bon("list", "--limit", "0", cwd=bon_dir_with_fixture)
        result_unlimited = run_bon("list", cwd=bon_dir_with_fixture)
        assert result_zero.returncode == 0
        assert result_zero.stdout == result_unlimited.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_with_json(self, bon_dir_with_fixture, monkeypatch):
        """--limit affects --json output: outcomes truncated, standalones share budget."""
        import json
        monkeypatch.chdir(bon_dir_with_fixture)
        result = run_bon("list", "--limit", "1", "--json", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["outcomes"]) == 1
        assert data["outcomes"][0]["id"] == "bon-aaa"
        assert len(data["outcomes"][0]["actions"]) == 1
        assert data["standalone"] == []

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_with_jsonl(self, bon_dir_with_fixture, monkeypatch):
        """--limit affects --jsonl output: only kept top-level items + their children."""
        import json
        monkeypatch.chdir(bon_dir_with_fixture)
        result = run_bon("list", "--limit", "1", "--jsonl", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        ids = {json.loads(line)["id"] for line in result.stdout.strip().split("\n")}
        # First outcome (bon-aaa) and its child (bon-ccc); no other outcomes or standalones
        assert ids == {"bon-aaa", "bon-ccc"}


class TestDoneOutcomeWithOpenChildren:
    """bon-kegewe: open children of done outcomes must stay board-visible."""

    def _seed(self, bon_dir):
        import json
        items = [
            {"id": "bon-parent", "type": "outcome", "title": "Done parent",
             "brief": {"why": "w", "what": "x", "done": "d"}, "status": "done",
             "order": 1, "created_at": "2026-06-10T20:00:00Z", "created_by": "t",
             "done_at": "2026-06-10T20:30:00Z"},
            {"id": "bon-straggler", "type": "action", "title": "Open straggler",
             "brief": {"why": "w", "what": "x", "done": "d"}, "status": "open",
             "parent": "bon-parent", "order": 1,
             "created_at": "2026-06-10T20:00:00Z", "created_by": "t"},
        ]
        path = bon_dir / ".bon" / "items.jsonl"
        path.write_text("".join(json.dumps(i) + "\n" for i in items))

    def test_list_shows_done_parent_with_open_child(self, bon_dir):
        self._seed(bon_dir)
        result = run_bon("list", cwd=bon_dir)
        assert "Open straggler" in result.stdout
        assert "Done parent" in result.stdout

    def test_list_ready_shows_open_child(self, bon_dir):
        self._seed(bon_dir)
        result = run_bon("list", "--ready", cwd=bon_dir)
        assert "Open straggler" in result.stdout

    def test_list_json_shows_open_child(self, bon_dir):
        import json
        self._seed(bon_dir)
        result = run_bon("list", "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        assert any(o["id"] == "bon-parent" for o in data["outcomes"])
        parent = next(o for o in data["outcomes"] if o["id"] == "bon-parent")
        assert any(a["id"] == "bon-straggler" for a in parent["actions"])

    def test_fully_done_outcome_still_hidden(self, bon_dir):
        self._seed(bon_dir)
        path = bon_dir / ".bon" / "items.jsonl"
        content = path.read_text().replace(
            '"status": "open", "parent": "bon-parent"',
            '"status": "done", "parent": "bon-parent"')
        path.write_text(content)
        result = run_bon("list", cwd=bon_dir)
        assert "Done parent" not in result.stdout

    def test_done_on_outcome_with_open_children_warns(self, bon_dir):
        self._seed(bon_dir)
        path = bon_dir / ".bon" / "items.jsonl"
        content = path.read_text().replace(
            '"status": "done", "order": 1', '"status": "open", "order": 1')
        path.write_text(content)
        result = run_bon("done", "bon-parent", cwd=bon_dir)
        assert result.returncode == 0
        assert "1 open action(s) remain" in result.stderr
        assert "bon-straggler" in result.stderr


class TestWaitingOutcomeDisplay:
    """bon-civelu: outcomes with waiting_for must render the ⏳ suffix."""

    def test_waiting_outcome_shows_hourglass(self, bon_dir):
        import json
        item = {"id": "bon-wout", "type": "outcome", "title": "Waiting outcome",
                "brief": {"why": "w", "what": "x", "done": "d"}, "status": "open",
                "waiting_for": ["bon-blocker"], "order": 1,
                "created_at": "2026-06-10T20:00:00Z", "created_by": "t"}
        (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
        result = run_bon("list", cwd=bon_dir)
        assert "⏳ bon-blocker" in result.stdout
