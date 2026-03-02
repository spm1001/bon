"""Tests for bon doctor command."""
import pytest

from conftest import run_arc


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_clean"], indirect=True)
def test_doctor_clean(arc_dir_with_fixture):
    """Clean file reports all clear."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "All clear." in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_malformed_json"], indirect=True)
def test_doctor_malformed_json(arc_dir_with_fixture):
    """Malformed JSON lines are flagged with line numbers."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "line 2: malformed JSON" in result.stdout
    assert "1 issue(s) found." in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_conflict_markers"], indirect=True)
def test_doctor_conflict_markers(arc_dir_with_fixture):
    """Git conflict markers are flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "git conflict marker" in result.stdout
    # Three markers: <<<<<<<, =======, >>>>>>>
    assert result.stdout.count("git conflict marker") == 3


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_duplicate_ids"], indirect=True)
def test_doctor_duplicate_ids(arc_dir_with_fixture):
    """Duplicate IDs are flagged with line numbers."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "duplicate ID 'arc-bbb'" in result.stdout
    assert "lines 2, 3" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_orphaned_parent"], indirect=True)
def test_doctor_orphaned_parent(arc_dir_with_fixture):
    """Orphaned parent references are flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "parent 'arc-deleted' does not exist" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_invalid_verb"], indirect=True)
def test_doctor_invalid_verb(arc_dir_with_fixture):
    """Unknown updated_by verbs are flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "unknown updated_by verb 'yolo'" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_missing_brief"], indirect=True)
def test_doctor_missing_brief(arc_dir_with_fixture):
    """Missing brief and partial brief are flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "missing brief" in result.stdout
    assert "missing brief.what" in result.stdout
    assert "missing brief.done" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_bad_tactical"], indirect=True)
def test_doctor_bad_tactical(arc_dir_with_fixture):
    """Invalid tactical structure is flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "bad tactical" in result.stdout
    assert "steps cannot be empty" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_outcome_with_tactical"], indirect=True)
def test_doctor_outcome_with_tactical(arc_dir_with_fixture):
    """Outcome with tactical field is flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "outcome has tactical" in result.stdout


@pytest.mark.parametrize("arc_dir_with_fixture", ["doctor_broken_waiting"], indirect=True)
def test_doctor_broken_waiting(arc_dir_with_fixture):
    """Broken waiting_for references are flagged."""
    result = run_arc("doctor", cwd=arc_dir_with_fixture)
    assert result.returncode == 0
    assert "waiting_for 'arc-gone' does not exist" in result.stdout


def test_doctor_no_items(arc_dir):
    """Empty items.jsonl reports nothing to check."""
    result = run_arc("doctor", cwd=arc_dir)
    assert result.returncode == 0
    # Empty file — should be all clear or nothing to check
    assert "All clear." in result.stdout or "No items" in result.stdout


def test_doctor_not_initialized(tmp_path):
    """Doctor errors when not initialized."""
    result = run_arc("doctor", cwd=tmp_path)
    assert result.returncode != 0
    assert "Not initialized" in result.stderr
