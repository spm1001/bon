"""Tests for --json, --jsonl, --quiet output flags."""
import json

import pytest
from conftest import run_arc


class TestJsonOutput:
    """Test --json flag."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_list_json(self, arc_dir_with_fixture, monkeypatch):
        """arc list --json outputs nested JSON."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--json", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "outcomes" in data
        assert "standalone" in data
        assert len(data["outcomes"]) == 1
        assert data["outcomes"][0]["id"] == "arc-aaa"
        assert "actions" in data["outcomes"][0]
        assert len(data["outcomes"][0]["actions"]) == 2

    @pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_json(self, arc_dir_with_fixture, monkeypatch):
        """arc show --json outputs item as JSON."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("show", "arc-aaa", "--json", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == "arc-aaa"
        assert data["type"] == "outcome"
        assert "actions" in data  # Outcomes include actions array


class TestJsonlOutput:
    """Test --jsonl flag."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_list_jsonl(self, arc_dir_with_fixture, monkeypatch):
        """arc list --jsonl outputs flat JSONL."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--jsonl", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3  # 1 outcome + 2 actions

        # Each line should be valid JSON
        for line in lines:
            item = json.loads(line)
            assert "id" in item


class TestQuietOutput:
    """Test --quiet flag."""

    def test_new_quiet(self, arc_dir, monkeypatch):
        """arc new --quiet outputs only the ID."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Test", "-q",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        # Output should be just the ID, no "Created:" prefix
        output = result.stdout.strip()
        assert output.startswith("arc-")
        assert "Created:" not in result.stdout

    def test_new_quiet_long_flag(self, arc_dir, monkeypatch):
        """arc new --quiet works with long flag."""
        monkeypatch.chdir(arc_dir)

        result = run_arc(
            "new", "Test", "--quiet",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=arc_dir
        )

        assert result.returncode == 0
        output = result.stdout.strip()
        assert output.startswith("arc-")
        assert "Created:" not in result.stdout


class TestJsonlWithFilters:
    """Test --jsonl respects filters."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_list_jsonl_ready(self, arc_dir_with_fixture, monkeypatch):
        """arc list --jsonl --ready shows only ready items."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--jsonl", "--ready", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        items = [json.loads(line) for line in lines]

        # Should have outcome and ready action only (arc-ccc), not waiting action (arc-bbb)
        ids = {item["id"] for item in items}
        assert "arc-aaa" in ids  # outcome
        assert "arc-ccc" in ids  # ready action
        assert "arc-bbb" not in ids  # waiting action should be filtered out

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_list_jsonl_waiting(self, arc_dir_with_fixture, monkeypatch):
        """arc list --jsonl --waiting shows only waiting items."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--jsonl", "--waiting", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        items = [json.loads(line) for line in lines]

        # Should have outcome and waiting action only
        ids = {item["id"] for item in items}
        assert "arc-aaa" in ids  # outcome (open outcomes included)
        assert "arc-bbb" in ids  # waiting action
        assert "arc-ccc" not in ids  # ready action should be filtered out


class TestJsonWithFilters:
    """Test --json respects filters."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_list_json_ready(self, arc_dir_with_fixture, monkeypatch):
        """arc list --json --ready shows only ready items."""
        monkeypatch.chdir(arc_dir_with_fixture)

        result = run_arc("list", "--json", "--ready", cwd=arc_dir_with_fixture)

        assert result.returncode == 0
        data = json.loads(result.stdout)

        # Collect all item IDs from nested structure
        ids = set()
        for outcome in data.get("outcomes", []):
            ids.add(outcome["id"])
            for action in outcome.get("actions", []):
                ids.add(action["id"])
        for action in data.get("standalone", []):
            ids.add(action["id"])

        assert "arc-aaa" in ids  # outcome
        assert "arc-ccc" in ids  # ready action
        assert "arc-bbb" not in ids  # waiting action should be filtered out
