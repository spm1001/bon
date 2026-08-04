"""
Tests for `brief.badly` — the pre-registered falsifier (bon-meliga).

`--done` asks how we know the work is COMPLETE, which a Claude can satisfy by
construction and routinely does. `--badly` asks what would show it went WRONG,
written before work starts by whoever wants the answer. It restores the half of
GTD's Natural Planning Model phase 1 that bon's four-field brief dropped:
purpose AND principles.

Two properties the tests pin down, because both are easy to lose later:

  ADDITIVE, NEVER BACKFILLED — an outcome without a falsifier keeps a brief of
  exactly {why, what, done} on disk, while `--json` reports `badly: null`. The
  contract lives at the read boundary (the jejuge precedent), so every existing
  item is covered for free and no shared store gets bulk-mutated.

  COACHED, NOT VALIDATED — a falsifier on an action is a nudge, not a refusal.
  The data layer has no business rejecting a field someone had a reason to write.

The authorship rule (the human writes it; a Claude leaves it absent) is
deliberately NOT tested here — it cannot be: the data layer sees a string, not a
hand. It lives in the /plan skill and docs/CONTRACT.md's falsifier seam.
"""

import json

import pytest
from conftest import run_bon

FALSIFIER = (
    "If the fix makes a single session slower to start, or if anyone has to think "
    "about session identity while doing ordinary work, we solved the wrong problem."
)


def _items(bon_dir) -> dict:
    text = (bon_dir / ".bon" / "items.jsonl").read_text().strip()
    return {i["id"]: i for i in (json.loads(ln) for ln in text.splitlines() if ln)}


def _new_outcome(bon_dir, *, badly: str | None = None, title: str = "Sessions stay honest") -> str:
    brief = {"why": "w", "what": "x", "done": "d"}
    if badly is not None:
        brief["badly"] = badly
    result = run_bon("new", "-q", cwd=bon_dir, input=json.dumps({"title": title, "brief": brief}))
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TestFalsifierCreate:
    def test_new_stores_badly_from_json_stdin(self, bon_dir):
        oid = _new_outcome(bon_dir, badly=FALSIFIER)
        assert _items(bon_dir)[oid]["brief"]["badly"] == FALSIFIER

    def test_new_stores_badly_from_a_flag(self, bon_dir):
        result = run_bon("new", "Sessions stay honest", "--why", "w", "--what", "x",
                         "--done", "d", "--badly", FALSIFIER, "-q", cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir)[result.stdout.strip()]["brief"]["badly"] == FALSIFIER

    def test_brief_without_badly_is_still_valid(self, bon_dir):
        """Optional means optional — three fields remain the whole requirement."""
        oid = _new_outcome(bon_dir)
        assert sorted(_items(bon_dir)[oid]["brief"]) == ["done", "what", "why"]


class TestFalsifierDisplay:
    def test_show_renders_badly_beside_done(self, bon_dir):
        oid = _new_outcome(bon_dir, badly=FALSIFIER)
        out = run_bon("show", oid, cwd=bon_dir).stdout
        assert "--badly:" in out
        assert FALSIFIER in out
        # The pairing is the point: complete, then wrong-way-round.
        assert out.index("--done:") < out.index("--badly:")

    def test_show_omits_badly_when_absent(self, bon_dir):
        oid = _new_outcome(bon_dir)
        assert "--badly:" not in run_bon("show", oid, cwd=bon_dir).stdout


class TestFalsifierJson:
    def test_json_emits_the_value_when_present(self, bon_dir):
        oid = _new_outcome(bon_dir, badly=FALSIFIER)
        data = json.loads(run_bon("show", oid, "--json", cwd=bon_dir).stdout)
        assert data["brief"]["badly"] == FALSIFIER

    def test_json_emits_null_when_absent(self, bon_dir):
        """The key is always present so consumers need no None-guard."""
        oid = _new_outcome(bon_dir)
        data = json.loads(run_bon("show", oid, "--json", cwd=bon_dir).stdout)
        assert "badly" in data["brief"]
        assert data["brief"]["badly"] is None

    def test_read_time_default_does_not_pollute_stored_data(self, bon_dir):
        """No backfill: the null exists at the output boundary, not on disk."""
        oid = _new_outcome(bon_dir)
        run_bon("show", oid, "--json", cwd=bon_dir)
        run_bon("list", "--json", cwd=bon_dir)
        assert "badly" not in _items(bon_dir)[oid]["brief"]

    def test_list_json_normalizes_outcomes_and_their_actions(self, bon_dir):
        oid = _new_outcome(bon_dir)
        run_bon("new", "A step", "--outcome", oid, "--why", "w", "--what", "x",
                "--done", "d", "-q", cwd=bon_dir)
        data = json.loads(run_bon("list", "--json", cwd=bon_dir).stdout)
        outcome = data["outcomes"][0]
        assert outcome["brief"]["badly"] is None
        assert outcome["actions"][0]["brief"]["badly"] is None


class TestFalsifierEdit:
    def test_edit_sets_badly(self, bon_dir):
        oid = _new_outcome(bon_dir)
        result = run_bon("edit", oid, "--badly", FALSIFIER, cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir)[oid]["brief"]["badly"] == FALSIFIER

    def test_edit_empty_string_clears_badly(self, bon_dir):
        oid = _new_outcome(bon_dir, badly=FALSIFIER)
        result = run_bon("edit", oid, "--badly", "", cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert "badly" not in _items(bon_dir)[oid]["brief"]

    def test_edit_accepts_badly_via_piped_json(self, bon_dir):
        """Composes with bon-cefisu: a falsifier with backticks survives."""
        oid = _new_outcome(bon_dir)
        nasty = 'Wrong if `bon list` still prints $HOME or a "quoted" path.'
        result = run_bon("edit", oid, cwd=bon_dir, input=json.dumps({"badly": nasty}))
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir)[oid]["brief"]["badly"] == nasty

    def test_edit_badly_alone_counts_as_an_edit(self, bon_dir):
        """--badly must satisfy the at-least-one-flag check on its own."""
        oid = _new_outcome(bon_dir)
        result = run_bon("edit", oid, "--badly", "x", cwd=bon_dir)
        assert result.returncode == 0
        assert "At least one edit flag" not in result.stderr


class TestFalsifierPlacementCoaching:
    """Outcomes-shaped, but the CLI nudges rather than refuses."""

    def test_action_with_badly_warns_but_is_accepted(self, bon_dir):
        oid = _new_outcome(bon_dir)
        result = run_bon("new", "Fix the racing temp path", "--outcome", oid,
                         "--why", "w", "--what", "x", "--done", "d",
                         "--badly", "hmm", "-q", cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert "--badly on an action" in result.stderr
        aid = result.stdout.strip()
        assert _items(bon_dir)[aid]["brief"]["badly"] == "hmm", "the nudge must not drop the value"

    def test_outcome_with_badly_is_not_nudged(self, bon_dir):
        result = run_bon("new", "-q", cwd=bon_dir, input=json.dumps({
            "title": "Sessions stay honest",
            "brief": {"why": "w", "what": "x", "done": "d", "badly": FALSIFIER},
        }))
        assert "--badly on an action" not in result.stderr

    def test_editing_badly_onto_an_action_also_nudges(self, bon_dir):
        oid = _new_outcome(bon_dir)
        aid = run_bon("new", "A step", "--outcome", oid, "--why", "w", "--what", "x",
                      "--done", "d", "-q", cwd=bon_dir).stdout.strip()
        result = run_bon("edit", aid, "--badly", "hmm", cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert "--badly on an action" in result.stderr

    def test_no_nudge_when_clearing_badly_from_an_action(self, bon_dir):
        oid = _new_outcome(bon_dir)
        aid = run_bon("new", "A step", "--outcome", oid, "--why", "w", "--what", "x",
                      "--done", "d", "-q", cwd=bon_dir).stdout.strip()
        run_bon("edit", aid, "--badly", "hmm", cwd=bon_dir)
        result = run_bon("edit", aid, "--badly", "", cwd=bon_dir)
        assert "--badly on an action" not in result.stderr


class TestFalsifierBackwardCompatibility:
    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_existing_boards_load_and_render_unchanged(self, bon_dir_with_fixture):
        """Items predating the field must not trip validation or display."""
        listing = run_bon("list", cwd=bon_dir_with_fixture)
        assert listing.returncode == 0, listing.stderr
        assert "--badly" not in listing.stdout

        data = json.loads(run_bon("list", "--json", cwd=bon_dir_with_fixture).stdout)
        assert all(o["brief"]["badly"] is None for o in data["outcomes"])

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_editing_an_old_item_still_validates(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", "--badly", FALSIFIER, cwd=bon_dir_with_fixture)
        assert result.returncode == 0, result.stderr
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["badly"] == FALSIFIER
        assert item["brief"]["why"] == "New devs struggling with auth setup"
