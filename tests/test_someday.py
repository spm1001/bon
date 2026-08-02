"""Tests for bon someday / unsomeday — Someday/Maybe parking (bon-majoca).

Design (adjudicated with Sameer, 2026-08-02): a flag, not a status. The
`someday` field holds the REQUIRED revisit condition; status stays open/done
so older clients and raw readers never lose sight of the item. Children
inherit parked-ness at read time. The default list collapses parked items to
one honest tail line.
"""
import json

import pytest
from conftest import run_bon


def new_outcome(bon_dir, title):
    r = run_bon("new", title, "--why", "w", "--what", "x", "--done", "d", "-q",
                cwd=bon_dir)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def new_child(bon_dir, parent, title):
    r = run_bon("new", title, "--parent", parent, "--why", "w", "--what", "x",
                "--done", "d", "-q", cwd=bon_dir)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def read_item(bon_dir, item_id):
    for line in (bon_dir / ".bon" / "items.jsonl").read_text().splitlines():
        item = json.loads(line)
        if item["id"] == item_id:
            return item
    raise AssertionError(f"{item_id} not found")


class TestSomedayVerbs:
    def test_park_requires_condition(self, bon_dir):
        oid = new_outcome(bon_dir, "Parked things thrive")
        result = run_bon("someday", oid, cwd=bon_dir)
        assert result.returncode != 0  # argparse: condition is positional+required

    def test_blank_condition_refused(self, bon_dir):
        oid = new_outcome(bon_dir, "Parked things thrive")
        result = run_bon("someday", oid, "   ", cwd=bon_dir)
        assert result.returncode == 1
        assert "condition" in result.stderr.lower()

    def test_park_sets_field_and_verb(self, bon_dir):
        oid = new_outcome(bon_dir, "Parked things thrive")
        result = run_bon("someday", oid, "when Mary picks it up", cwd=bon_dir)
        assert result.returncode == 0
        assert "parked" in result.stdout.lower()
        item = read_item(bon_dir, oid)
        assert item["someday"] == "when Mary picks it up"
        assert item["updated_by"] == "parked"
        assert item["status"] == "open"  # a flag, not a status

    def test_unsomeday_clears(self, bon_dir):
        oid = new_outcome(bon_dir, "Parked things thrive")
        run_bon("someday", oid, "next quarter", cwd=bon_dir)
        result = run_bon("unsomeday", oid, cwd=bon_dir)
        assert result.returncode == 0
        item = read_item(bon_dir, oid)
        assert not item.get("someday")
        assert item["updated_by"] == "unparked"

    def test_park_done_item_refused(self, bon_dir):
        oid = new_outcome(bon_dir, "Already finished")
        run_bon("done", oid, cwd=bon_dir)
        result = run_bon("someday", oid, "never", cwd=bon_dir)
        assert result.returncode == 1

    def test_park_with_active_tactical_refused(self, bon_dir):
        """Unlike bon wait (which silently discards tactical progress — the
        documented landmine), someday refuses and names the way out."""
        oid = new_outcome(bon_dir, "Has live work")
        aid = new_child(bon_dir, oid, "Step through this")
        run_bon("work", aid, "step one", "step two", cwd=bon_dir)
        result = run_bon("someday", aid, "later", cwd=bon_dir)
        assert result.returncode == 1
        assert "tactical" in result.stderr.lower()
        item = read_item(bon_dir, aid)
        assert item.get("tactical")  # untouched
        assert not item.get("someday")


class TestSomedayViews:
    def test_default_list_hides_parked_and_says_so(self, bon_dir):
        new_outcome(bon_dir, "Live outcome stays")
        pid = new_outcome(bon_dir, "Dormant outcome vanishes")
        run_bon("someday", pid, "when it bites again", cwd=bon_dir)
        result = run_bon("list", cwd=bon_dir)
        assert result.returncode == 0
        assert "Live outcome stays" in result.stdout
        assert "Dormant outcome vanishes" not in result.stdout
        assert "Someday: 1 parked" in result.stdout
        assert "bon list --someday" in result.stdout

    def test_no_tail_line_when_nothing_parked(self, bon_dir):
        new_outcome(bon_dir, "Live outcome stays")
        result = run_bon("list", cwd=bon_dir)
        assert "Someday:" not in result.stdout

    def test_someday_view_shows_condition(self, bon_dir):
        new_outcome(bon_dir, "Live outcome stays")
        pid = new_outcome(bon_dir, "Dormant outcome shows here")
        run_bon("someday", pid, "when it bites again", cwd=bon_dir)
        result = run_bon("list", "--someday", cwd=bon_dir)
        assert result.returncode == 0
        assert "Dormant outcome shows here" in result.stdout
        assert "when it bites again" in result.stdout
        assert "Live outcome stays" not in result.stdout

    def test_children_inherit_parking(self, bon_dir):
        pid = new_outcome(bon_dir, "Dormant parent")
        new_child(bon_dir, pid, "Child goes quiet too")
        run_bon("someday", pid, "next winter", cwd=bon_dir)
        listed = run_bon("list", cwd=bon_dir)
        assert "Child goes quiet too" not in listed.stdout
        ready = run_bon("list", "--ready", cwd=bon_dir)
        assert "Child goes quiet too" not in ready.stdout
        parked_view = run_bon("list", "--someday", cwd=bon_dir)
        assert "Child goes quiet too" in parked_view.stdout

    def test_all_mode_shows_parked_marked(self, bon_dir):
        pid = new_outcome(bon_dir, "Dormant but visible in all")
        run_bon("someday", pid, "someday soon", cwd=bon_dir)
        result = run_bon("list", "--all", cwd=bon_dir)
        assert "Dormant but visible in all" in result.stdout
        assert "someday soon" in result.stdout

    def test_json_default_excludes_parked(self, bon_dir):
        new_outcome(bon_dir, "Live outcome stays")
        pid = new_outcome(bon_dir, "Dormant outcome vanishes")
        run_bon("someday", pid, "later", cwd=bon_dir)
        result = run_bon("list", "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        titles = [o["title"] for o in data["outcomes"]]
        assert "Live outcome stays" in titles
        assert "Dormant outcome vanishes" not in titles

    def test_json_someday_view(self, bon_dir):
        pid = new_outcome(bon_dir, "Dormant outcome vanishes")
        run_bon("someday", pid, "later", cwd=bon_dir)
        result = run_bon("list", "--someday", "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        assert [o["title"] for o in data["outcomes"]] == ["Dormant outcome vanishes"]

    def test_show_displays_condition(self, bon_dir):
        pid = new_outcome(bon_dir, "Dormant outcome")
        run_bon("someday", pid, "when the tripwire fires", cwd=bon_dir)
        result = run_bon("show", pid, cwd=bon_dir)
        assert "Someday" in result.stdout
        assert "when the tripwire fires" in result.stdout

    def test_parked_child_of_live_parent_appears_in_someday_view(self, bon_dir):
        """A parked action under an UNPARKED outcome must still render in the
        parked view — its parent isn't there to hang it under, so it shows as
        standalone rather than silently vanishing (found live on aby-moditu)."""
        oid = new_outcome(bon_dir, "Live parent outcome")
        aid = new_child(bon_dir, oid, "Parked child action")
        run_bon("someday", aid, "when the stars align", cwd=bon_dir)
        result = run_bon("list", "--someday", cwd=bon_dir)
        assert "Parked child action" in result.stdout
        assert "when the stars align" in result.stdout
        assert "Live parent outcome" not in result.stdout  # parent isn't parked

    def test_json_someday_includes_parked_child_of_live_parent(self, bon_dir):
        oid = new_outcome(bon_dir, "Live parent outcome")
        aid = new_child(bon_dir, oid, "Parked child action")
        run_bon("someday", aid, "when the stars align", cwd=bon_dir)
        result = run_bon("list", "--someday", "--json", cwd=bon_dir)
        data = json.loads(result.stdout)
        titles = [a["title"] for a in data["standalone"]]
        assert "Parked child action" in titles
