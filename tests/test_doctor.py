"""Tests for bon doctor command."""
import json

import pytest

from conftest import run_bon


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_clean"], indirect=True)
def test_doctor_clean(bon_dir_with_fixture):
    """Clean file reports all clear."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "All clear." in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_malformed_json"], indirect=True)
def test_doctor_malformed_json(bon_dir_with_fixture):
    """Malformed JSON lines are flagged with line numbers."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "line 2: malformed JSON" in result.stdout
    assert "1 issue(s) found." in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_conflict_markers"], indirect=True)
def test_doctor_conflict_markers(bon_dir_with_fixture):
    """Git conflict markers are flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "git conflict marker" in result.stdout
    # Three markers: <<<<<<<, =======, >>>>>>>
    assert result.stdout.count("git conflict marker") == 3


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_duplicate_ids"], indirect=True)
def test_doctor_duplicate_ids(bon_dir_with_fixture):
    """Duplicate IDs are flagged with line numbers."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "duplicate ID 'bon-bbb'" in result.stdout
    assert "lines 2, 3" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_orphaned_parent"], indirect=True)
def test_doctor_orphaned_parent(bon_dir_with_fixture):
    """Orphaned parent references are flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "parent 'bon-deleted' does not exist" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_invalid_verb"], indirect=True)
def test_doctor_invalid_verb(bon_dir_with_fixture):
    """Unknown updated_by verbs are flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "unknown updated_by verb 'yolo'" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_missing_brief"], indirect=True)
def test_doctor_missing_brief(bon_dir_with_fixture):
    """Missing brief and partial brief are flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "missing brief" in result.stdout
    assert "missing brief.what" in result.stdout
    assert "missing brief.done" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_bad_tactical"], indirect=True)
def test_doctor_bad_tactical(bon_dir_with_fixture):
    """Invalid tactical structure is flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "bad tactical" in result.stdout
    assert "steps cannot be empty" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_outcome_with_tactical"], indirect=True)
def test_doctor_outcome_with_tactical(bon_dir_with_fixture):
    """Outcome with tactical field is flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "outcome has tactical" in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_broken_waiting"], indirect=True)
def test_doctor_broken_waiting(bon_dir_with_fixture):
    """Broken waiting_for references are flagged."""
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "waiting_for 'bon-gone' does not exist" in result.stdout


def _seed_waiting(bon_dir, waiting_for):
    import json
    item = {"id": "bon-host", "type": "action", "title": "Waiting item",
            "brief": {"why": "w", "what": "x", "done": "d"}, "status": "open",
            "parent": None, "order": 1, "created_at": "2026-08-01T10:00:00Z",
            "created_by": "t", "waiting_for": waiting_for}
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")


def test_doctor_free_text_rationale_with_hyphen_is_clean(bon_dir):
    """A hyphenated word inside a rationale is not a dangling id (bon-gufale).

    `bon wait` documents its reason as 'ID or text'; doctor was the only
    surface disagreeing — five false positives on a clean 55-item board.
    """
    _seed_waiting(bon_dir, ["Ellie's sign-off on the recharge model"])
    result = run_bon("doctor", cwd=bon_dir)
    assert "does not exist" not in result.stdout
    assert "All clear." in result.stdout


def test_doctor_spaceless_hyphenated_rationale_is_clean(bon_dir):
    """'external-review' is a rationale, not a reference to a board id."""
    _seed_waiting(bon_dir, ["external-review"])
    result = run_bon("doctor", cwd=bon_dir)
    assert "does not exist" not in result.stdout


def test_doctor_foreign_board_id_is_clean(bon_dir):
    """An id from ANOTHER board cannot be verified here — pass, don't guess."""
    _seed_waiting(bon_dir, ["crn-kemize"])
    result = run_bon("doctor", cwd=bon_dir)
    assert "does not exist" not in result.stdout


def test_doctor_waiting_outcome_is_clean(bon_dir):
    """A waiting OUTCOME is legitimate GTD (a delegated outcome is the
    textbook Waiting For) — wait/new/display all allow it; doctor agrees
    since 2026-08-16. Tactical on an outcome stays flagged."""
    import json
    item = {"id": "bon-parked", "type": "outcome", "title": "Delegated outcome",
            "brief": {"why": "w", "what": "x", "done": "d"}, "status": "open",
            "order": 1, "created_at": "2026-08-01T10:00:00Z",
            "created_by": "t", "waiting_for": ["Rupert's sign-off"]}
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
    result = run_bon("doctor", cwd=bon_dir)
    assert "outcome has waiting_for" not in result.stdout
    assert "All clear." in result.stdout


def test_doctor_own_prefix_dangling_id_still_fires(bon_dir):
    """The negative control: a doctor that passes everything is the same
    uselessness the other way round."""
    _seed_waiting(bon_dir, ["bon-zzzzzz"])
    result = run_bon("doctor", cwd=bon_dir)
    assert "waiting_for 'bon-zzzzzz' does not exist" in result.stdout


def test_doctor_legacy_prefix_carried_by_live_items_is_checked(bon_dir):
    """A prefix any live item carries counts as the board's own (re-prefix
    migrations leave legacy ids behind)."""
    import json
    item = {"id": "old-abcdef", "type": "action", "title": "Legacy id",
            "brief": {"why": "w", "what": "x", "done": "d"}, "status": "open",
            "parent": None, "order": 1, "created_at": "2026-08-01T10:00:00Z",
            "created_by": "t", "waiting_for": ["old-gonexx"]}
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
    result = run_bon("doctor", cwd=bon_dir)
    assert "waiting_for 'old-gonexx' does not exist" in result.stdout


def test_doctor_no_items(bon_dir):
    """Empty items.jsonl reports nothing to check."""
    result = run_bon("doctor", cwd=bon_dir)
    assert result.returncode == 0
    # Empty file — should be all clear or nothing to check
    assert "All clear." in result.stdout or "No items" in result.stdout


def test_doctor_not_initialized(tmp_path):
    """Doctor errors when not initialized."""
    result = run_bon("doctor", cwd=tmp_path)
    assert result.returncode != 0
    assert "Not initialized" in result.stderr


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_clean"], indirect=True)
def test_doctor_stale_bottle(bon_dir_with_fixture):
    """A README.md that differs from current bottle wording is flagged."""
    (bon_dir_with_fixture / ".bon" / "README.md").write_text("old bottle\n")
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "differs from current wording" in result.stdout
    assert "1 issue(s) found." in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_clean"], indirect=True)
def test_doctor_missing_bottle(bon_dir_with_fixture):
    """A board with no README.md at all is flagged."""
    (bon_dir_with_fixture / ".bon" / "README.md").unlink()
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "is missing" in result.stdout
    assert "1 issue(s) found." in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_clean"], indirect=True)
def test_doctor_fix_refreshes_bottle(bon_dir_with_fixture):
    """--fix rewrites the bottle and the board comes back clean."""
    from bon.storage import BOARD_README
    readme = bon_dir_with_fixture / ".bon" / "README.md"
    readme.write_text("old bottle\n")
    result = run_bon("doctor", "--fix", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Refreshed .bon/README.md" in result.stdout
    assert "All clear." in result.stdout
    assert readme.read_text() == BOARD_README
    result = run_bon("doctor", cwd=bon_dir_with_fixture)
    assert "All clear." in result.stdout


@pytest.mark.parametrize("bon_dir_with_fixture", ["doctor_clean"], indirect=True)
def test_doctor_fix_noop_when_current(bon_dir_with_fixture):
    """--fix on a current bottle refreshes nothing."""
    result = run_bon("doctor", "--fix", cwd=bon_dir_with_fixture)
    assert result.returncode == 0
    assert "Refreshed" not in result.stdout
    assert "All clear." in result.stdout


def test_doctor_reports_stale_claim(bon_dir):
    """An active tactical untouched for 7+ days surfaces as an advisory, not an issue."""
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    item = {
        "id": "bon-stale1", "type": "action", "title": "Stale claim",
        "brief": {"why": "w", "what": "x", "done": "d"},
        "status": "open", "order": 1,
        "created_at": old, "created_by": "test",
        "updated_at": old, "updated_by": "stepped",
        "tactical": {"steps": ["a", "b"], "current": 1, "session": "/dead/path"},
    }
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
    result = run_bon("doctor", cwd=bon_dir)
    assert result.returncode == 0
    assert "Stale claims (advisory" in result.stdout
    assert "bon-stale1 held by /dead/path" in result.stdout
    assert "untouched 10d" in result.stdout
    assert "All clear." in result.stdout  # advisory does not dirty the health verdict


def test_doctor_fresh_claim_not_stale(bon_dir):
    """A recently-touched claim stays out of the advisory."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    item = {
        "id": "bon-fresh1", "type": "action", "title": "Fresh claim",
        "brief": {"why": "w", "what": "x", "done": "d"},
        "status": "open", "order": 1,
        "created_at": now, "created_by": "test",
        "updated_at": now, "updated_by": "worked",
        "tactical": {"steps": ["a"], "current": 0, "session": "/live/path"},
    }
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
    result = run_bon("doctor", cwd=bon_dir)
    assert result.returncode == 0
    assert "Stale claims" not in result.stdout


def test_doctor_released_claim_not_stale(bon_dir):
    """A released tactical is not an active claim — never advisory material."""
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    item = {
        "id": "bon-parked", "type": "action", "title": "Released claim",
        "brief": {"why": "w", "what": "x", "done": "d"},
        "status": "open", "order": 1,
        "created_at": old, "created_by": "test",
        "updated_at": old, "updated_by": "released",
        "tactical": {"steps": ["a", "b"], "current": 1, "session": "/x", "released": True},
    }
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
    result = run_bon("doctor", cwd=bon_dir)
    assert result.returncode == 0
    assert "Stale claims" not in result.stdout
