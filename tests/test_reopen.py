"""Tests for bon reopen command."""
import json
import re

import pytest

from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# --- Basic ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_reopen_done_item(bon_dir_with_fixture):
    """Reopen a completed item."""
    run_bon("done", "bon-aaa", cwd=bon_dir_with_fixture)
    result = run_bon("reopen", "bon-aaa", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Reopened: bon-aaa" in result.stdout

    # Item is open again
    show = run_bon("show", "bon-aaa", "--json", cwd=bon_dir_with_fixture)
    item = json.loads(show.stdout)
    assert item["status"] == "open"
    assert "done_at" not in item


@pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
def test_reopen_already_open_errors(bon_dir_with_fixture):
    """Cannot reopen an already-open item."""
    result = run_bon("reopen", "bon-aaa", cwd=bon_dir_with_fixture)
    assert result.returncode == 1
    assert "already open" in result.stderr


def test_reopen_not_found(bon_dir):
    """Reopen unknown ID errors."""
    result = run_bon("reopen", "bon-nonexistent", cwd=bon_dir)
    assert result.returncode == 1
    assert "not found" in result.stderr


# --- Clears done_at ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_reopen_clears_done_at(bon_dir_with_fixture):
    """Reopen removes done_at timestamp."""
    # bon-ccc is open in this fixture, so done will add done_at
    run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)

    # Confirm done_at exists
    show = run_bon("show", "bon-ccc", "--json", cwd=bon_dir_with_fixture)
    assert "done_at" in json.loads(show.stdout)

    run_bon("reopen", "bon-ccc", cwd=bon_dir_with_fixture)
    show = run_bon("show", "bon-ccc", "--json", cwd=bon_dir_with_fixture)
    item = json.loads(show.stdout)
    assert "done_at" not in item
    assert item["status"] == "open"


# --- Preserves tactical ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["action_tactical_complete"], indirect=True)
def test_reopen_preserves_tactical(bon_dir_with_fixture):
    """Tactical steps are preserved when reopening."""
    # action_tactical_complete has a done action with completed tactical
    items_path = bon_dir_with_fixture / ".bon" / "items.jsonl"
    items = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
    # Find the action with tactical
    action = next(i for i in items if i.get("tactical"))
    action_id = action["id"]

    result = run_bon("reopen", action_id, cwd=bon_dir_with_fixture)
    assert result.returncode == 0

    show = run_bon("show", action_id, "--json", cwd=bon_dir_with_fixture)
    reopened = json.loads(show.stdout)
    assert reopened["status"] == "open"
    assert "tactical" in reopened


# --- Reopen from archive ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["done_outcome_with_actions"], indirect=True)
def test_reopen_from_archive(bon_dir_with_fixture):
    """Reopen an archived item restores it to items.jsonl."""
    # Archive first
    run_bon("archive", "--all", cwd=bon_dir_with_fixture)

    # Confirm items.jsonl is empty
    items_path = bon_dir_with_fixture / ".bon" / "items.jsonl"
    assert items_path.read_text().strip() == ""

    # Reopen one item
    result = run_bon("reopen", "bon-bbb", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "restored from archive" in result.stdout

    # Item is back in items.jsonl
    items = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
    ids = {i["id"] for i in items}
    assert "bon-bbb" in ids

    # Item is open, no done_at or archived_at
    restored = next(i for i in items if i["id"] == "bon-bbb")
    assert restored["status"] == "open"
    assert "done_at" not in restored
    assert "archived_at" not in restored

    # Archive file has the other two still
    archive_path = bon_dir_with_fixture / ".bon" / "archive.jsonl"
    archived = [json.loads(l) for l in archive_path.read_text().splitlines() if l.strip()]
    archived_ids = {a["id"] for a in archived}
    assert "bon-bbb" not in archived_ids
    assert "bon-aaa" in archived_ids
    assert "bon-ccc" in archived_ids


# --- Prefix tolerance ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_reopen_prefix_tolerant(bon_dir_with_fixture):
    """Reopen works with or without prefix."""
    run_bon("done", "bon-aaa", cwd=bon_dir_with_fixture)
    result = run_bon("reopen", "aaa", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Reopened: bon-aaa" in result.stdout


# --- Not initialized ---


def test_reopen_not_initialized(tmp_path):
    """Reopen errors when not initialized."""
    result = run_bon("reopen", "bon-xyz", cwd=tmp_path)
    assert result.returncode == 1
    assert "Not initialized" in result.stderr


# --- updated_at ---


class TestReopenUpdatedAt:
    """Verify reopen sets updated_at timestamp."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
    def test_reopen_sets_updated_at(self, bon_dir_with_fixture):
        """Reopening a done item sets updated_at."""
        # bon-bbb is done in mixed_done_open
        result = run_bon("reopen", "bon-bbb", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert "updated_at" in items["bon-bbb"]
        assert ISO_RE.match(items["bon-bbb"]["updated_at"])
