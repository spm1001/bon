"""Tests for --json, --jsonl, --quiet output flags."""
import json

import pytest
from conftest import run_bon


class TestJsonOutput:
    """Test --json flag."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_list_json(self, bon_dir_with_fixture, monkeypatch):
        """bon list --json outputs nested JSON."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--json", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "outcomes" in data
        assert "standalone" in data
        assert len(data["outcomes"]) == 1
        assert data["outcomes"][0]["id"] == "bon-aaa"
        assert "actions" in data["outcomes"][0]
        assert len(data["outcomes"][0]["actions"]) == 2

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_json(self, bon_dir_with_fixture, monkeypatch):
        """bon show --json outputs item as JSON."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "bon-aaa", "--json", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["id"] == "bon-aaa"
        assert data["type"] == "outcome"
        assert "actions" in data  # Outcomes include actions array


class TestJsonlOutput:
    """Test --jsonl flag."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_list_jsonl(self, bon_dir_with_fixture, monkeypatch):
        """bon list --jsonl outputs flat JSONL."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--jsonl", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 3  # 1 outcome + 2 actions

        # Each line should be valid JSON
        for line in lines:
            item = json.loads(line)
            assert "id" in item


class TestQuietOutput:
    """Test --quiet flag."""

    def test_new_quiet(self, bon_dir, monkeypatch):
        """bon new --quiet outputs only the ID."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Test", "-q",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        # Output should be just the ID, no "Created:" prefix
        output = result.stdout.strip()
        assert output.startswith("bon-")
        assert "Created:" not in result.stdout

    def test_new_quiet_long_flag(self, bon_dir, monkeypatch):
        """bon new --quiet works with long flag."""
        monkeypatch.chdir(bon_dir)

        result = run_bon(
            "new", "Test", "--quiet",
            "--why", "w", "--what", "x", "--done", "d",
            cwd=bon_dir
        )

        assert result.returncode == 0
        output = result.stdout.strip()
        assert output.startswith("bon-")
        assert "Created:" not in result.stdout


class TestJsonlWithFilters:
    """Test --jsonl respects filters."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_list_jsonl_ready(self, bon_dir_with_fixture, monkeypatch):
        """bon list --jsonl --ready shows only ready items."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--jsonl", "--ready", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        items = [json.loads(line) for line in lines]

        # Should have outcome and ready action only (bon-ccc), not waiting action (bon-bbb)
        ids = {item["id"] for item in items}
        assert "bon-aaa" in ids  # outcome
        assert "bon-ccc" in ids  # ready action
        assert "bon-bbb" not in ids  # waiting action should be filtered out

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_list_jsonl_waiting(self, bon_dir_with_fixture, monkeypatch):
        """bon list --jsonl --waiting shows only waiting items."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--jsonl", "--waiting", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        items = [json.loads(line) for line in lines]

        # Should have outcome and waiting action only
        ids = {item["id"] for item in items}
        assert "bon-aaa" in ids  # outcome (open outcomes included)
        assert "bon-bbb" in ids  # waiting action
        assert "bon-ccc" not in ids  # ready action should be filtered out


class TestJsonWithFilters:
    """Test --json respects filters."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_list_json_ready(self, bon_dir_with_fixture, monkeypatch):
        """bon list --json --ready shows only ready items."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("list", "--json", "--ready", cwd=bon_dir_with_fixture)

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

        assert "bon-aaa" in ids  # outcome
        assert "bon-ccc" in ids  # ready action
        assert "bon-bbb" not in ids  # waiting action should be filtered out
