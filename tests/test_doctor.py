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


# ---------------------------------------------------------------------------
# Duplicate sibling orders — detection, and repair via --fix (bon-tagoje)
# ---------------------------------------------------------------------------

def _new_standalone(bon_dir, title):
    r = run_bon("new", "-q", cwd=bon_dir,
                input=json.dumps({"type": "action", "title": title,
                                  "brief": {"why": "w", "what": "x", "done": "d"}}))
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _set_fields(bon_dir, item_id, **fields):
    """Hand-edit stored fields — mint the dup the mover can't repair."""
    path = bon_dir / ".bon" / "items.jsonl"
    lines = []
    for line in path.read_text().splitlines():
        item = json.loads(line)
        if item["id"] == item_id:
            item.update(fields)
        lines.append(json.dumps(item, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n")


def _orders(bon_dir):
    path = bon_dir / ".bon" / "items.jsonl"
    return {json.loads(l)["id"]: json.loads(l).get("order")
            for l in path.read_text().splitlines()}


class TestOrderDupRepair:
    def _minted_dup(self, bon_dir):
        """Four standalones at 1,2,3,4; drag C onto 2 → 1,2,2,3 (B,C share 2).

        created_at is hand-spaced: bon stamps second-resolution timestamps, so
        same-second twins would otherwise tie and fall to the id lottery —
        the semantic under test is 'older twin keeps the lower rung'.
        """
        a = _new_standalone(bon_dir, "A")
        b = _new_standalone(bon_dir, "B")
        c = _new_standalone(bon_dir, "C")
        d = _new_standalone(bon_dir, "D")
        for i, item_id in enumerate([a, b, c, d]):
            _set_fields(bon_dir, item_id, created_at=f"2026-08-16T12:00:0{i}Z")
        _set_fields(bon_dir, c, order=2)
        _set_fields(bon_dir, d, order=3)
        return a, b, c, d

    def test_single_move_reminfs_the_dup(self, bon_dir):
        """The mover assumes unique orders: repairing a dup with one move
        re-mints it one rung down (the mit-commons incident, 2026-08-16).
        This test documents WHY the repair lives in doctor, not the mover."""
        a, b, c, d = self._minted_dup(bon_dir)
        r = run_bon("edit", c, "--order", "4", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        orders = _orders(bon_dir)
        # C escaped to 4, but D was pulled onto the vacated rung where B sits
        assert orders[b] == 2 and orders[d] == 2, orders
        vals = sorted(orders.values())
        assert vals.count(2) == 2  # the dup survives, one rung down

    def test_doctor_reports_dup_with_fix_hint(self, bon_dir):
        self._minted_dup(bon_dir)
        r = run_bon("doctor", cwd=bon_dir)
        assert r.returncode == 0
        assert "duplicate order values [2]" in r.stdout
        assert "--fix" in r.stdout  # the issue line names its remedy

    def test_doctor_fix_resequences(self, bon_dir):
        a, b, c, d = self._minted_dup(bon_dir)
        r = run_bon("doctor", "--fix", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "Resequenced" in r.stdout
        orders = _orders(bon_dir)
        assert sorted(orders.values()) == [1, 2, 3, 4]
        # (order, created_at) sort: B keeps 2, C (later-created twin) takes 3
        assert orders[a] == 1 and orders[b] == 2 and orders[c] == 3 and orders[d] == 4
        # clean on re-run
        r = run_bon("doctor", cwd=bon_dir)
        assert "duplicate order" not in r.stdout
        assert "All clear." in r.stdout

    def test_fix_stamps_only_changed_items(self, bon_dir):
        a, b, c, d = self._minted_dup(bon_dir)
        run_bon("doctor", "--fix", cwd=bon_dir)
        path = bon_dir / ".bon" / "items.jsonl"
        by_id = {json.loads(l)["id"]: json.loads(l) for l in path.read_text().splitlines()}
        assert by_id[c]["updated_by"] == "repaired"
        assert by_id[d]["updated_by"] == "repaired"
        assert by_id[a].get("updated_by") != "repaired"  # untouched rungs unstamped
        assert by_id[b].get("updated_by") != "repaired"

    def test_fix_skipped_when_file_unparseable(self, bon_dir):
        """A repair must not rewrite a file it can't fully read — a malformed
        line would be silently dropped by a parsed-items rewrite."""
        self._minted_dup(bon_dir)
        path = bon_dir / ".bon" / "items.jsonl"
        before = path.read_text() + "{not json\n"
        path.write_text(before)
        r = run_bon("doctor", "--fix", cwd=bon_dir)
        assert r.returncode == 0
        assert "malformed JSON" in r.stdout
        assert "Resequenced" not in r.stdout
        assert path.read_text() == before  # file untouched
        assert "duplicate order values" in r.stdout  # still reported, unfixed

    def test_fix_normalises_none_orders_in_group(self, bon_dir):
        """A resequenced group comes out fully 1..N — None-order siblings
        sort last and gain real rungs."""
        a, b, c, d = self._minted_dup(bon_dir)
        path = bon_dir / ".bon" / "items.jsonl"
        lines = []
        for line in path.read_text().splitlines():
            item = json.loads(line)
            if item["id"] == a:
                item.pop("order", None)
            lines.append(json.dumps(item, ensure_ascii=False))
        path.write_text("\n".join(lines) + "\n")
        run_bon("doctor", "--fix", cwd=bon_dir)
        orders = _orders(bon_dir)
        assert sorted(orders.values()) == [1, 2, 3, 4]
        assert orders[a] == 4  # None sorts last

    def test_done_siblings_untouched(self, bon_dir):
        a, b, c, d = self._minted_dup(bon_dir)
        run_bon("done", a, cwd=bon_dir)
        run_bon("doctor", "--fix", cwd=bon_dir)
        orders = _orders(bon_dir)
        assert orders[a] == 1  # done item keeps its historical order
        assert sorted(v for k, v in orders.items() if k != a) == [1, 2, 3]


def test_doctor_gitignored_bon_advisory(bon_dir):
    """A root .gitignore that swallows .bon/ strands understanding.md and the
    bottle silently (bon-kizeje) — doctor surfaces it as an advisory, never an
    issue. Handoffs left the probe list in bon-sedoze: they no longer live
    under .bon/, so a .bon/ ignore cannot reach them."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=bon_dir, check=True)
    (bon_dir / ".gitignore").write_text(".bon/\n")

    result = run_bon("doctor", cwd=bon_dir)

    assert result.returncode == 0
    assert "Sync hazard (advisory" in result.stdout
    assert ".bon/understanding.md" in result.stdout
    assert ".bon/README.md" in result.stdout
    assert ".bon/items.jsonl" in result.stdout  # JSONL board: the board itself is stranded too
    assert ".bon/handoffs" not in result.stdout, "retired probe (bon-sedoze)"
    assert "All clear." in result.stdout  # advisory rides a clean bill, not an issue count


def test_doctor_no_sync_advisory_when_bon_tracked(bon_dir):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=bon_dir, check=True)

    result = run_bon("doctor", cwd=bon_dir)

    assert "Sync hazard" not in result.stdout
    assert "All clear." in result.stdout  # positive control: doctor ran and reported


def test_doctor_no_sync_advisory_outside_git(bon_dir):
    result = run_bon("doctor", cwd=bon_dir)

    assert "Sync hazard" not in result.stdout
    assert "All clear." in result.stdout
