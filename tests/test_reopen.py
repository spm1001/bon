"""Tests for arc reopen command."""
import json

import pytest

from conftest import run_arc


# --- Basic ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_reopen_done_item(arc_dir_with_fixture):
    """Reopen a completed item."""
    run_arc("done", "arc-aaa", cwd=arc_dir_with_fixture)
    result = run_arc("reopen", "arc-aaa", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "Reopened: arc-aaa" in result.stdout

    # Item is open again
    show = run_arc("show", "arc-aaa", "--json", cwd=arc_dir_with_fixture)
    item = json.loads(show.stdout)
    assert item["status"] == "open"
    assert "done_at" not in item


@pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
def test_reopen_already_open_errors(arc_dir_with_fixture):
    """Cannot reopen an already-open item."""
    result = run_arc("reopen", "arc-aaa", cwd=arc_dir_with_fixture)
    assert result.returncode == 1
    assert "already open" in result.stderr


def test_reopen_not_found(arc_dir):
    """Reopen unknown ID errors."""
    result = run_arc("reopen", "arc-nonexistent", cwd=arc_dir)
    assert result.returncode == 1
    assert "not found" in result.stderr


# --- Clears done_at ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_reopen_clears_done_at(arc_dir_with_fixture):
    """Reopen removes done_at timestamp."""
    # arc-ccc is open in this fixture, so done will add done_at
    run_arc("done", "arc-ccc", cwd=arc_dir_with_fixture)

    # Confirm done_at exists
    show = run_arc("show", "arc-ccc", "--json", cwd=arc_dir_with_fixture)
    assert "done_at" in json.loads(show.stdout)

    run_arc("reopen", "arc-ccc", cwd=arc_dir_with_fixture)
    show = run_arc("show", "arc-ccc", "--json", cwd=arc_dir_with_fixture)
    item = json.loads(show.stdout)
    assert "done_at" not in item
    assert item["status"] == "open"


# --- Preserves tactical ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["action_tactical_complete"], indirect=True)
def test_reopen_preserves_tactical(arc_dir_with_fixture):
    """Tactical steps are preserved when reopening."""
    # action_tactical_complete has a done action with completed tactical
    items_path = arc_dir_with_fixture / ".bon" / "items.jsonl"
    items = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
    # Find the action with tactical
    action = next(i for i in items if i.get("tactical"))
    action_id = action["id"]

    result = run_arc("reopen", action_id, cwd=arc_dir_with_fixture)
    assert result.returncode == 0

    show = run_arc("show", action_id, "--json", cwd=arc_dir_with_fixture)
    reopened = json.loads(show.stdout)
    assert reopened["status"] == "open"
    assert "tactical" in reopened


# --- Reopen from archive ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["done_outcome_with_actions"], indirect=True)
def test_reopen_from_archive(arc_dir_with_fixture):
    """Reopen an archived item restores it to items.jsonl."""
    # Archive first
    run_arc("archive", "--all", cwd=arc_dir_with_fixture)

    # Confirm items.jsonl is empty
    items_path = arc_dir_with_fixture / ".bon" / "items.jsonl"
    assert items_path.read_text().strip() == ""

    # Reopen one item
    result = run_arc("reopen", "arc-bbb", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "restored from archive" in result.stdout

    # Item is back in items.jsonl
    items = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
    ids = {i["id"] for i in items}
    assert "arc-bbb" in ids

    # Item is open, no done_at or archived_at
    restored = next(i for i in items if i["id"] == "arc-bbb")
    assert restored["status"] == "open"
    assert "done_at" not in restored
    assert "archived_at" not in restored

    # Archive file has the other two still
    archive_path = arc_dir_with_fixture / ".bon" / "archive.jsonl"
    archived = [json.loads(l) for l in archive_path.read_text().splitlines() if l.strip()]
    archived_ids = {a["id"] for a in archived}
    assert "arc-bbb" not in archived_ids
    assert "arc-aaa" in archived_ids
    assert "arc-ccc" in archived_ids


# --- Prefix tolerance ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_reopen_prefix_tolerant(arc_dir_with_fixture):
    """Reopen works with or without prefix."""
    run_arc("done", "arc-aaa", cwd=arc_dir_with_fixture)
    result = run_arc("reopen", "aaa", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "Reopened: arc-aaa" in result.stdout


# --- Not initialized ---


def test_reopen_not_initialized(tmp_path):
    """Reopen errors when not initialized."""
    result = run_arc("reopen", "arc-xyz", cwd=tmp_path)
    assert result.returncode == 1
    assert "Not initialized" in result.stderr
