"""Tests for bon archive command."""
import json
import re

import pytest

from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


# --- Fixtures ---


@pytest.fixture
def done_action(bon_dir):
    """Create a single done action."""
    result = run_bon(
        "new", "Done thing",
        "--why", "test", "--what", "test", "--done", "test",
        cwd=bon_dir,
    )
    item_id = result.stdout.strip().split(": ")[1]
    run_bon("done", item_id, cwd=bon_dir)
    return bon_dir, item_id


# --- Basic archive ---


def test_archive_single_done_action(done_action):
    """Archive a single done action by ID."""
    bon_dir, item_id = done_action
    result = run_bon("archive", item_id, cwd=bon_dir)
    assert result.returncode == 0
    assert "Archived 1 item(s)" in result.stdout
    assert item_id in result.stdout

    # Item removed from items.jsonl
    items = json.loads(run_bon("list", "--json", cwd=bon_dir).stdout)
    all_ids = [o["id"] for o in items.get("outcomes", [])] + [o["id"] for o in items.get("standalone", [])]
    assert item_id not in all_ids

    # Item present in archive.jsonl
    archive_path = bon_dir / ".bon" / "archive.jsonl"
    assert archive_path.exists()
    archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
    assert len(archived) == 1
    assert archived[0]["id"] == item_id
    assert "archived_at" in archived[0]


def test_archive_open_item_errors(bon_dir):
    """Cannot archive an open item."""
    result = run_bon(
        "new", "Open thing",
        "--why", "test", "--what", "test", "--done", "test",
        cwd=bon_dir,
    )
    item_id = result.stdout.strip().split(": ")[1]
    result = run_bon("archive", item_id, cwd=bon_dir)
    assert result.returncode == 1
    assert "not done" in result.stderr


def test_archive_not_found_errors(bon_dir):
    """Archive unknown ID errors."""
    result = run_bon("archive", "bon-nonexistent", cwd=bon_dir)
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_archive_no_args_errors(bon_dir):
    """Archive with no IDs and no --all errors."""
    result = run_bon("archive", cwd=bon_dir)
    assert result.returncode == 1
    assert "Specify item IDs or --all" in result.stderr


# --- --all ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
def test_archive_all(bon_dir_with_fixture):
    """--all archives all done items."""
    result = run_bon("archive", "--all", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Archived" in result.stdout

    # Only open items remain
    items_path = bon_dir_with_fixture / ".bon" / "items.jsonl"
    remaining = [json.loads(line) for line in items_path.read_text().splitlines() if line.strip()]
    for item in remaining:
        assert item["status"] == "open"

    # Archived items are in archive.jsonl
    archive_path = bon_dir_with_fixture / ".bon" / "archive.jsonl"
    archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
    for item in archived:
        assert item["status"] == "done"
        assert "archived_at" in item


@pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
def test_archive_all_nothing_done(bon_dir_with_fixture):
    """--all with no done items prints message."""
    result = run_bon("archive", "--all", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Nothing to archive" in result.stdout


# --- Outcome cascade ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["done_outcome_with_actions"], indirect=True)
def test_archive_outcome_cascades_actions(bon_dir_with_fixture):
    """Archiving a done outcome cascades to its done actions."""
    result = run_bon("archive", "bon-aaa", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Archived 3 item(s)" in result.stdout

    # All three items archived
    archive_path = bon_dir_with_fixture / ".bon" / "archive.jsonl"
    archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
    archived_ids = {a["id"] for a in archived}
    assert archived_ids == {"bon-aaa", "bon-bbb", "bon-ccc"}

    # items.jsonl is empty
    items_path = bon_dir_with_fixture / ".bon" / "items.jsonl"
    remaining = [line for line in items_path.read_text().splitlines() if line.strip()]
    assert len(remaining) == 0


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_archive_done_outcome_with_open_actions_errors(bon_dir_with_fixture):
    """Cannot archive outcome that has open actions."""
    # Mark outcome as done first
    run_bon("done", "bon-aaa", cwd=bon_dir_with_fixture)
    result = run_bon("archive", "bon-aaa", cwd=bon_dir_with_fixture)
    assert result.returncode == 1
    assert "open actions" in result.stderr


# --- Multiple IDs ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
def test_archive_multiple_ids(bon_dir_with_fixture):
    """Archive multiple items by ID."""
    result = run_bon("archive", "bon-bbb", "bon-ddd", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Archived 2 item(s)" in result.stdout


# --- Append behavior ---


def test_archive_appends(done_action):
    """Multiple archive calls append to the same file."""
    bon_dir, first_id = done_action

    # Create and archive a second item
    result = run_bon(
        "new", "Another done thing",
        "--why", "test", "--what", "test", "--done", "test",
        cwd=bon_dir,
    )
    second_id = result.stdout.strip().split(": ")[1]
    run_bon("done", second_id, cwd=bon_dir)

    # Archive first
    run_bon("archive", first_id, cwd=bon_dir)

    # Archive second
    run_bon("archive", second_id, cwd=bon_dir)

    # Both in archive
    archive_path = bon_dir / ".bon" / "archive.jsonl"
    archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
    assert len(archived) == 2
    archived_ids = {a["id"] for a in archived}
    assert first_id in archived_ids
    assert second_id in archived_ids


# --- Prefix tolerance ---


def test_archive_prefix_tolerant(done_action):
    """Archive works with or without prefix."""
    bon_dir, item_id = done_action
    suffix = item_id.split("-", 1)[1]  # e.g. "gabdur" from "bon-gabdur"
    result = run_bon("archive", suffix, cwd=bon_dir)
    assert result.returncode == 0
    assert "Archived 1 item(s)" in result.stdout


# --- updated_at ---


class TestBonhiveUpdatedAt:
    """Verify archive sets updated_at on archived items."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["done_outcome_with_actions"], indirect=True)
    def test_archive_all_sets_updated_at(self, bon_dir_with_fixture):
        """Archived items have updated_at set in ISO format."""
        result = run_bon("archive", "--all", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        archive_path = bon_dir_with_fixture / ".bon" / "archive.jsonl"
        archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
        assert len(archived) > 0
        for item in archived:
            assert "updated_at" in item
            assert ISO_RE.match(item["updated_at"])
