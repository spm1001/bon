"""Tests for arc log command."""
import json

import pytest

from conftest import run_arc


# --- Basic ---


def test_log_empty(arc_dir):
    """Log with no items shows no activity."""
    result = run_arc("log", cwd=arc_dir)
    assert result.returncode == 0
    assert "No activity" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["single_outcome"], indirect=True)
def test_log_shows_creation(arc_dir_with_fixture):
    """Log shows item creation events."""
    result = run_arc("log", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "created" in result.stdout
    assert "arc-aaa" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_shows_completion(arc_dir_with_fixture):
    """Log shows done events for completed items."""
    run_arc("done", "arc-aaa", cwd=arc_dir_with_fixture)
    result = run_arc("log", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "completed" in result.stdout
    assert "arc-aaa" in result.stdout


# --- Limit ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["multiple_outcomes"], indirect=True)
def test_log_limit(arc_dir_with_fixture):
    """--limit restricts number of events."""
    result = run_arc("log", "-n", "2", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
    assert len(lines) == 2


# --- Archive events ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["done_outcome_with_actions"], indirect=True)
def test_log_shows_archived(arc_dir_with_fixture):
    """Log includes archived events from archive.jsonl."""
    run_arc("archive", "--all", cwd=arc_dir_with_fixture)
    result = run_arc("log", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "archived" in result.stdout


# --- Ordering ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_newest_first(arc_dir_with_fixture):
    """Events are sorted newest first."""
    result = run_arc("log", "--json", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    events = json.loads(result.stdout)
    times = [e["time"] for e in events]
    assert times == sorted(times, reverse=True)


# --- JSON output ---


@pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_json(arc_dir_with_fixture):
    """--json returns structured output."""
    result = run_arc("log", "--json", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    events = json.loads(result.stdout)
    assert isinstance(events, list)
    assert len(events) > 0
    for e in events:
        assert "time" in e
        assert "verb" in e
        assert "id" in e
        assert "title" in e
        assert "type" in e


# --- Not initialized ---


def test_log_not_initialized(tmp_path):
    """Log errors when not initialized."""
    result = run_arc("log", cwd=tmp_path)
    assert result.returncode == 1
    assert "Not initialized" in result.stderr
