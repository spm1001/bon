"""Tests for arc list command - snapshot tests against fixtures."""
import pytest
from conftest import run_arc

# Expected outputs for snapshot tests
EXPECTED_LIST_DEFAULT = {
    "empty": "No outcomes.\n",

    "single_outcome": "○ User auth (arc-aaa)\n",

    "outcome_with_actions": """\
○ User auth (arc-aaa)
  1. ✓ Add endpoint (arc-bbb)
  2. ○ Add UI (arc-ccc)
""",

    "waiting_dependency": """\
○ Deploy (arc-aaa)
  1. ○ Run tests (arc-bbb) ⏳ arc-ccc
  2. ○ Security review (arc-ccc)
""",

    "multiple_outcomes": """\
○ First outcome (arc-aaa)
  1. ○ Action for first (arc-ccc)

○ Second outcome (arc-bbb)
  1. ○ Action for second (arc-ddd)
""",

    "standalone_actions": """\
Standalone:
  ○ Field Report: OAuth flaky (arc-aaa)
  ○ Quick fix for typo (arc-bbb)
""",

    "all_waiting": """\
○ Ship release (arc-aaa)
  1. ○ Legal review (arc-bbb) ⏳ external counsel
  2. ○ Security audit (arc-ccc) ⏳ arc-bbb
""",
}


EXPECTED_LIST_READY = {
    "outcome_with_actions": """\
○ User auth (arc-aaa)
  1. ✓ Add endpoint (arc-bbb)
  2. ○ Add UI (arc-ccc)
""",

    "waiting_dependency": """\
○ Deploy (arc-aaa)
  2. ○ Security review (arc-ccc)
  (+1 waiting)
""",

    "all_waiting": """\
○ Ship release (arc-aaa)
  (2 waiting)
""",
}


EXPECTED_LIST_WAITING = {
    "waiting_dependency": """\
○ Deploy (arc-aaa)
  1. ○ Run tests (arc-bbb) ⏳ arc-ccc
""",

    "all_waiting": """\
○ Ship release (arc-aaa)
  1. ○ Legal review (arc-bbb) ⏳ external counsel
  2. ○ Security audit (arc-ccc) ⏳ arc-bbb
""",
}


class TestListDefault:
    """Test arc list (default mode)."""

    @pytest.mark.parametrize("arc_dir_with_fixture,expected", [
        ("empty", EXPECTED_LIST_DEFAULT["empty"]),
        ("single_outcome", EXPECTED_LIST_DEFAULT["single_outcome"]),
        ("outcome_with_actions", EXPECTED_LIST_DEFAULT["outcome_with_actions"]),
        ("waiting_dependency", EXPECTED_LIST_DEFAULT["waiting_dependency"]),
        ("multiple_outcomes", EXPECTED_LIST_DEFAULT["multiple_outcomes"]),
        ("standalone_actions", EXPECTED_LIST_DEFAULT["standalone_actions"]),
        ("all_waiting", EXPECTED_LIST_DEFAULT["all_waiting"]),
    ], indirect=["arc_dir_with_fixture"])
    def test_list_default(self, arc_dir_with_fixture, expected, monkeypatch):
        """arc list output matches expected for each fixture."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", cwd=arc_dir_with_fixture)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"


class TestListReady:
    """Test arc list --ready."""

    @pytest.mark.parametrize("arc_dir_with_fixture,expected", [
        ("outcome_with_actions", EXPECTED_LIST_READY["outcome_with_actions"]),
        ("waiting_dependency", EXPECTED_LIST_READY["waiting_dependency"]),
        ("all_waiting", EXPECTED_LIST_READY["all_waiting"]),
    ], indirect=["arc_dir_with_fixture"])
    def test_list_ready(self, arc_dir_with_fixture, expected, monkeypatch):
        """arc list --ready shows ready and done actions for context."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--ready", cwd=arc_dir_with_fixture)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"


class TestListWaiting:
    """Test arc list --waiting."""

    @pytest.mark.parametrize("arc_dir_with_fixture,expected", [
        ("waiting_dependency", EXPECTED_LIST_WAITING["waiting_dependency"]),
        ("all_waiting", EXPECTED_LIST_WAITING["all_waiting"]),
    ], indirect=["arc_dir_with_fixture"])
    def test_list_waiting(self, arc_dir_with_fixture, expected, monkeypatch):
        """arc list --waiting shows only waiting actions."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--waiting", cwd=arc_dir_with_fixture)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"


class TestListNotInitialized:
    """Test arc list when not initialized."""

    def test_error_when_not_initialized(self, tmp_path, monkeypatch):
        """Error when .arc/ doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("list", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestListLimit:
    """Test arc list --limit N truncates to first N top-level items."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_limit_truncates_outcomes(self, arc_dir_with_fixture, monkeypatch):
        """--limit 1 keeps only the first outcome (with its children)."""
        monkeypatch.chdir(arc_dir_with_fixture)
        expected = """\
○ First outcome (arc-aaa)
  1. ○ Action for first (arc-ccc)
"""
        result = run_arc("list", "--limit", "1", cwd=arc_dir_with_fixture)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_limit_larger_than_available(self, arc_dir_with_fixture, monkeypatch):
        """--limit N where N > available returns everything."""
        monkeypatch.chdir(arc_dir_with_fixture)
        result_unlimited = run_arc("list", cwd=arc_dir_with_fixture)
        result_limited = run_arc("list", "--limit", "100", cwd=arc_dir_with_fixture)
        assert result_limited.returncode == 0
        assert result_limited.stdout == result_unlimited.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_spans_outcomes_and_standalones(self, arc_dir_with_fixture, monkeypatch):
        """--limit consumes outcomes first, then spends remaining budget on standalones."""
        monkeypatch.chdir(arc_dir_with_fixture)
        expected = """\
○ First outcome (arc-aaa)
  1. ○ Action for first (arc-ccc)

○ Second outcome (arc-bbb)

Standalone:
  ○ Standalone one (arc-ddd)
"""
        result = run_arc("list", "--limit", "3", cwd=arc_dir_with_fixture)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout == expected, f"\nGot:\n{repr(result.stdout)}\n\nExpected:\n{repr(expected)}"

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_under_outcome_count_drops_standalones(self, arc_dir_with_fixture, monkeypatch):
        """--limit smaller than outcome count drops all standalones."""
        monkeypatch.chdir(arc_dir_with_fixture)
        result = run_arc("list", "--limit", "1", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        assert "Standalone:" not in result.stdout
        assert "arc-aaa" in result.stdout
        assert "arc-bbb" not in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_zero_treated_as_no_limit(self, arc_dir_with_fixture, monkeypatch):
        """--limit 0 is permissive, not exclusive — returns everything."""
        monkeypatch.chdir(arc_dir_with_fixture)
        result_zero = run_arc("list", "--limit", "0", cwd=arc_dir_with_fixture)
        result_unlimited = run_arc("list", cwd=arc_dir_with_fixture)
        assert result_zero.returncode == 0
        assert result_zero.stdout == result_unlimited.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_with_json(self, arc_dir_with_fixture, monkeypatch):
        """--limit affects --json output: outcomes truncated, standalones share budget."""
        import json
        monkeypatch.chdir(arc_dir_with_fixture)
        result = run_arc("list", "--limit", "1", "--json", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["outcomes"]) == 1
        assert data["outcomes"][0]["id"] == "arc-aaa"
        assert len(data["outcomes"][0]["actions"]) == 1
        assert data["standalone"] == []

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcomes_and_standalones"], indirect=True)
    def test_limit_with_jsonl(self, arc_dir_with_fixture, monkeypatch):
        """--limit affects --jsonl output: only kept top-level items + their children."""
        import json
        monkeypatch.chdir(arc_dir_with_fixture)
        result = run_arc("list", "--limit", "1", "--jsonl", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        ids = {json.loads(line)["id"] for line in result.stdout.strip().split("\n")}
        # First outcome (arc-aaa) and its child (arc-ccc); no other outcomes or standalones
        assert ids == {"arc-aaa", "arc-ccc"}
