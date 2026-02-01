"""Tests for arc convert command."""
import json

import pytest

from conftest import run_arc


class TestConvertActionToOutcome:
    """Test converting action → outcome."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_to_outcome(self, arc_dir_with_fixture, monkeypatch):
        """Basic action → outcome conversion."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-ccc is an action under arc-aaa
        result = run_arc("convert", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted arc-ccc to outcome" in result.stdout

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-ccc"]["type"] == "outcome"
        assert items["arc-ccc"].get("parent") is None
        assert "waiting_for" not in items["arc-ccc"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_assigns_order(self, arc_dir_with_fixture, monkeypatch):
        """Converted action gets appended to outcomes."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-aaa is outcome at order 1, arc-ccc should be at order 2
        assert items["arc-ccc"]["order"] == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_convert_waiting_action_clears_waiting_for(self, arc_dir_with_fixture, monkeypatch):
        """Converting waiting action clears waiting_for."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-bbb"]["type"] == "outcome"
        assert "waiting_for" not in items["arc-bbb"]

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_closes_gap(self, arc_dir_with_fixture, monkeypatch):
        """Converting action closes gap in old parent's ordering."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # First add a third action
        run_arc("new", "Third action", "--for", "arc-aaa",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=arc_dir_with_fixture)

        # Now convert arc-bbb (order 1, done) to outcome
        result = run_arc("convert", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-ccc was order 2, should now be order 1
        assert items["arc-ccc"]["order"] == 1


class TestConvertOutcomeToAction:
    """Test converting outcome → action."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["two_outcomes_no_children"], indirect=True)
    def test_convert_outcome_to_action(self, arc_dir_with_fixture, monkeypatch):
        """Basic outcome → action conversion."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Convert arc-bbb (outcome with no children) to action under arc-aaa
        result = run_arc("convert", "arc-bbb", "--parent", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted arc-bbb to action" in result.stdout

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-bbb"]["type"] == "action"
        assert items["arc-bbb"]["parent"] == "arc-aaa"
        assert items["arc-bbb"]["waiting_for"] is None

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_appends_to_parent(self, arc_dir_with_fixture, monkeypatch):
        """Converted outcome appended to end of parent's actions."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb has arc-ddd as child, use --force to convert
        # arc-aaa already has arc-ccc as action at order 1
        result = run_arc("convert", "arc-bbb", "--parent", "arc-aaa", "--force", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-bbb should be at order 2 (after arc-ccc at order 1)
        assert items["arc-bbb"]["order"] == 2


class TestConvertValidation:
    """Test convert command validation."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_requires_parent(self, arc_dir_with_fixture, monkeypatch):
        """Converting outcome without --parent is an error."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "requires --parent" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_rejects_parent(self, arc_dir_with_fixture, monkeypatch):
        """Converting action with --parent is an error."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-ccc", "--parent", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "don't specify --parent" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_parent_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when parent doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-bbb", "--parent", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent 'arc-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_parent_must_be_outcome(self, arc_dir_with_fixture, monkeypatch):
        """Error when parent is an action."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-ccc is an action
        result = run_arc("convert", "arc-bbb", "--parent", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_convert_item_not_found(self, arc_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-nonexistent", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'arc-nonexistent' not found" in result.stderr

    def test_convert_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_arc("convert", "arc-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestConvertWithChildren:
    """Test converting outcome with children."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_children"], indirect=True)
    def test_convert_outcome_with_children_blocked(self, arc_dir_with_fixture, monkeypatch):
        """Outcome with children requires --force."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-aaa", "--parent", "arc-ddd", cwd=arc_dir_with_fixture)

        assert result.returncode == 1
        assert "has 2 children" in result.stderr
        assert "--force" in result.stderr

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_children"], indirect=True)
    def test_convert_outcome_with_force_orphans_children(self, arc_dir_with_fixture, monkeypatch):
        """Converting outcome with --force makes children standalone."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-aaa", "--parent", "arc-ddd", "--force",
                         cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # arc-aaa should be an action under arc-ddd
        assert items["arc-aaa"]["type"] == "action"
        assert items["arc-aaa"]["parent"] == "arc-ddd"

        # arc-bbb and arc-ccc should now be standalone
        assert items["arc-bbb"]["parent"] is None
        assert items["arc-ccc"]["parent"] is None


class TestConvertStandalone:
    """Test converting standalone actions."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["standalone_actions"], indirect=True)
    def test_convert_standalone_action_to_outcome(self, arc_dir_with_fixture, monkeypatch):
        """Standalone action converts to outcome."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted arc-aaa to outcome" in result.stdout

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-aaa"]["type"] == "outcome"
        assert items["arc-aaa"].get("parent") is None


class TestConvertPrefixTolerance:
    """Test prefix-tolerant ID matching."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_with_prefix_tolerant_id(self, arc_dir_with_fixture, monkeypatch):
        """Convert works with ID without prefix."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Use "ccc" instead of "arc-ccc"
        result = run_arc("convert", "ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted arc-ccc to outcome" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["two_outcomes_no_children"], indirect=True)
    def test_convert_with_prefix_tolerant_parent(self, arc_dir_with_fixture, monkeypatch):
        """Convert works with parent ID without prefix."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Use "aaa" instead of "arc-aaa" for parent
        result = run_arc("convert", "arc-bbb", "--parent", "aaa", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        # Parent should be resolved to full ID
        assert items["arc-bbb"]["parent"] == "arc-aaa"


class TestConvertPreservesMetadata:
    """Test that convert preserves metadata."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_preserves_brief(self, arc_dir_with_fixture, monkeypatch):
        """Convert preserves brief."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # Get original brief
        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        original = next(json.loads(l) for l in lines if json.loads(l)["id"] == "arc-ccc")
        original_brief = original["brief"]

        result = run_arc("convert", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-ccc"]["brief"] == original_brief

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_preserves_id(self, arc_dir_with_fixture, monkeypatch):
        """Convert preserves original ID."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("convert", "arc-ccc", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        ids = [json.loads(l)["id"] for l in lines]

        assert "arc-ccc" in ids

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_preserves_status(self, arc_dir_with_fixture, monkeypatch):
        """Convert preserves status (including done)."""
        monkeypatch.chdir(arc_dir_with_fixture)

        # arc-bbb is done
        result = run_arc("convert", "arc-bbb", cwd=arc_dir_with_fixture)

        assert result.returncode == 0

        lines = (arc_dir_with_fixture / ".arc" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(l)["id"]: json.loads(l) for l in lines}

        assert items["arc-bbb"]["status"] == "done"
