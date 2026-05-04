"""Tests for bon convert command."""
import json
import re

import pytest
from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestConvertActionToOutcome:
    """Test converting action → outcome."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_to_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Basic action → outcome conversion."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-ccc is an action under bon-aaa
        result = run_bon("convert", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted bon-ccc to outcome" in result.stdout

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-ccc"]["type"] == "outcome"
        assert items["bon-ccc"].get("parent") is None
        assert "waiting_for" not in items["bon-ccc"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_assigns_order(self, bon_dir_with_fixture, monkeypatch):
        """Converted action gets appended to outcomes."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-aaa is outcome at order 1, bon-ccc should be at order 2
        assert items["bon-ccc"]["order"] == 2

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_waiting"], indirect=True)
    def test_convert_waiting_action_clears_waiting_for(self, bon_dir_with_fixture, monkeypatch):
        """Converting waiting action clears waiting_for."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-bbb"]["type"] == "outcome"
        assert "waiting_for" not in items["bon-bbb"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_closes_gap(self, bon_dir_with_fixture, monkeypatch):
        """Converting action closes gap in old parent's ordering."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # First add a third action
        run_bon("new", "Third action", "--for", "bon-aaa",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        # Now convert bon-bbb (order 1, done) to outcome
        result = run_bon("convert", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-ccc was order 2, should now be order 1
        assert items["bon-ccc"]["order"] == 1


class TestConvertOutcomeToAction:
    """Test converting outcome → action."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["two_outcomes_no_children"], indirect=True)
    def test_convert_outcome_to_action(self, bon_dir_with_fixture, monkeypatch):
        """Basic outcome → action conversion."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Convert bon-bbb (outcome with no children) to action under bon-aaa
        result = run_bon("convert", "bon-bbb", "--parent", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted bon-bbb to action" in result.stdout

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-bbb"]["type"] == "action"
        assert items["bon-bbb"]["parent"] == "bon-aaa"
        assert items["bon-bbb"]["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_appends_to_parent(self, bon_dir_with_fixture, monkeypatch):
        """Converted outcome appended to end of parent's actions."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb has bon-ddd as child, use --force to convert
        # bon-aaa already has bon-ccc as action at order 1
        result = run_bon("convert", "bon-bbb", "--parent", "bon-aaa", "--force", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-bbb should be at order 2 (after bon-ccc at order 1)
        assert items["bon-bbb"]["order"] == 2


class TestConvertValidation:
    """Test convert command validation."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["two_outcomes_no_children"], indirect=True)
    def test_convert_outcome_to_standalone_action(self, bon_dir_with_fixture, monkeypatch):
        """Converting outcome without --parent creates standalone action."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted bon-bbb to action" in result.stdout

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-bbb"]["type"] == "action"
        assert items["bon-bbb"]["parent"] is None
        assert items["bon-bbb"]["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_rejects_parent(self, bon_dir_with_fixture, monkeypatch):
        """Converting action with --parent is an error."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-ccc", "--parent", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "don't specify --outcome" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_parent_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when parent doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-bbb", "--parent", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent 'bon-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_convert_outcome_parent_must_be_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Error when parent is an action."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-ccc is an action
        result = run_bon("convert", "bon-bbb", "--parent", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_convert_item_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    def test_convert_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("convert", "bon-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestConvertWithChildren:
    """Test converting outcome with children."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_children"], indirect=True)
    def test_convert_outcome_with_children_blocked(self, bon_dir_with_fixture, monkeypatch):
        """Outcome with children requires --force."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-aaa", "--parent", "bon-ddd", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "has 2 children" in result.stderr
        assert "--force" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_children"], indirect=True)
    def test_convert_outcome_with_force_orphans_children(self, bon_dir_with_fixture, monkeypatch):
        """Converting outcome with --force makes children standalone."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-aaa", "--parent", "bon-ddd", "--force",
                         cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-aaa should be an action under bon-ddd
        assert items["bon-aaa"]["type"] == "action"
        assert items["bon-aaa"]["parent"] == "bon-ddd"

        # bon-bbb and bon-ccc should now be standalone
        assert items["bon-bbb"]["parent"] is None
        assert items["bon-ccc"]["parent"] is None


class TestConvertStandalone:
    """Test converting standalone actions."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["standalone_actions"], indirect=True)
    def test_convert_standalone_action_to_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Standalone action converts to outcome."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted bon-aaa to outcome" in result.stdout

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-aaa"]["type"] == "outcome"
        assert items["bon-aaa"].get("parent") is None


class TestConvertPrefixTolerance:
    """Test prefix-tolerant ID matching."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_with_prefix_tolerant_id(self, bon_dir_with_fixture, monkeypatch):
        """Convert works with ID without prefix."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Use "ccc" instead of "bon-ccc"
        result = run_bon("convert", "ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Converted bon-ccc to outcome" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["two_outcomes_no_children"], indirect=True)
    def test_convert_with_prefix_tolerant_parent(self, bon_dir_with_fixture, monkeypatch):
        """Convert works with parent ID without prefix."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Use "aaa" instead of "bon-aaa" for parent
        result = run_bon("convert", "bon-bbb", "--parent", "aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # Parent should be resolved to full ID
        assert items["bon-bbb"]["parent"] == "bon-aaa"


class TestConvertPreservesMetadata:
    """Test that convert preserves metadata."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_preserves_brief(self, bon_dir_with_fixture, monkeypatch):
        """Convert preserves brief."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Get original brief
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        original = next(json.loads(line) for line in lines if json.loads(line)["id"] == "bon-ccc")
        original_brief = original["brief"]

        result = run_bon("convert", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-ccc"]["brief"] == original_brief

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_preserves_id(self, bon_dir_with_fixture, monkeypatch):
        """Convert preserves original ID."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        ids = [json.loads(line)["id"] for line in lines]

        assert "bon-ccc" in ids

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_preserves_status(self, bon_dir_with_fixture, monkeypatch):
        """Convert preserves status (including done)."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is done
        result = run_bon("convert", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-bbb"]["status"] == "done"


class TestConvertUpdatedAt:
    """Verify convert sets updated_at on the converted item."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_convert_action_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """Converting action to outcome sets updated_at."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("convert", "bon-ccc", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert "updated_at" in items["bon-ccc"]
        assert ISO_RE.match(items["bon-ccc"]["updated_at"])
