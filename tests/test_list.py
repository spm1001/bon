"""Tests for arc list command - snapshot tests against fixtures."""
import pytest
from conftest import run_arc

# Expected outputs from SPEC.md
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
    "waiting_dependency": """\
○ Deploy (arc-aaa)
  1. ○ Security review (arc-ccc)
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
        ("waiting_dependency", EXPECTED_LIST_READY["waiting_dependency"]),
        ("all_waiting", EXPECTED_LIST_READY["all_waiting"]),
    ], indirect=["arc_dir_with_fixture"])
    def test_list_ready(self, arc_dir_with_fixture, expected, monkeypatch):
        """arc list --ready shows only ready actions."""
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
