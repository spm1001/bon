"""Tests for bon log command."""
import json

import pytest

from conftest import run_bon


# --- Basic ---


def test_log_empty(bon_dir):
    """Log with no items shows no activity."""
    result = run_bon("log", cwd=bon_dir)
    assert result.returncode == 0
    assert "No activity" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
def test_log_shows_creation(bon_dir_with_fixture):
    """Log shows item creation events."""
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "created" in result.stdout
    assert "bon-aaa" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_shows_completion(bon_dir_with_fixture):
    """Log shows done events for completed items."""
    run_bon("done", "bon-aaa", cwd=bon_dir_with_fixture)
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "completed" in result.stdout
    assert "bon-aaa" in result.stdout


# --- Limit ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
def test_log_limit(bon_dir_with_fixture):
    """--limit restricts number of events."""
    result = run_bon("log", "-n", "2", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
    assert len(lines) == 2


# --- Archive events ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["done_outcome_with_actions"], indirect=True)
def test_log_shows_archived(bon_dir_with_fixture):
    """Log includes archived events from archive.jsonl."""
    run_bon("archive", "--all", cwd=bon_dir_with_fixture)
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "archived" in result.stdout


# --- Ordering ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_newest_first(bon_dir_with_fixture):
    """Events are sorted newest first."""
    result = run_bon("log", "--json", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    events = json.loads(result.stdout)
    times = [e["time"] for e in events]
    assert times == sorted(times, reverse=True)


# --- JSON output ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_json(bon_dir_with_fixture):
    """--json returns structured output."""
    result = run_bon("log", "--json", cwd=bon_dir_with_fixture)
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


# --- Mutation verbs ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_shows_edited_verb(bon_dir_with_fixture):
    """Editing an item shows 'edited' verb in log."""
    run_bon("edit", "bon-aaa", "--title", "New title", cwd=bon_dir_with_fixture)
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "edited" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_shows_waited_verb(bon_dir_with_fixture):
    """Waiting on an item shows 'waited' verb in log."""
    run_bon("wait", "bon-bbb", "needs review", cwd=bon_dir_with_fixture)
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "waited" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_shows_unwaited_verb(bon_dir_with_fixture):
    """Unwaiting shows 'unwaited' verb in log."""
    run_bon("wait", "bon-bbb", "needs review", cwd=bon_dir_with_fixture)
    run_bon("unwait", "bon-bbb", cwd=bon_dir_with_fixture)
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "unwaited" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
def test_log_shows_stepped_verb(bon_dir_with_fixture, monkeypatch):
    """Stepping shows 'stepped' verb in log."""
    monkeypatch.chdir(bon_dir_with_fixture)
    run_bon("step", cwd=bon_dir_with_fixture)
    result = run_bon("log", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "stepped" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_log_json_has_distinct_verb(bon_dir_with_fixture):
    """JSON log output includes the specific mutation verb."""
    run_bon("edit", "bon-aaa", "--title", "Changed", cwd=bon_dir_with_fixture)
    result = run_bon("log", "--json", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    events = json.loads(result.stdout)
    verbs = [e["verb"] for e in events]
    assert "edited" in verbs


# --- Show updated_by ---


@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_show_displays_updated_by(bon_dir_with_fixture):
    """bon show displays the mutation type alongside updated_at."""
    run_bon("edit", "bon-aaa", "--title", "Changed", cwd=bon_dir_with_fixture)
    result = run_bon("show", "bon-aaa", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "(edited)" in result.stdout


# --- Not initialized ---


def test_log_not_initialized(tmp_path):
    """Log errors when not initialized."""
    result = run_bon("log", cwd=tmp_path)
    assert result.returncode == 1
    assert "Not initialized" in result.stderr
