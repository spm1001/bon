"""Tests for the area field — Areas of Focus grouping (bon-razonu).

`area` is an optional top-level item field in the someday mould: absent means
ungrouped, empty never stores, and in Dolt it is a real column (accepted
old-writer decay, same trade as someday). Grouping keys on top-level
entities — an outcome's whole subtree travels with the outcome's own area,
so an action's `area` matters only when the action is standalone.
"""
import json

import pytest
from conftest import run_bon


def new_outcome(bon_dir, title, area=None):
    args = ["new", title, "--why", "w", "--what", "x", "--done", "d", "-q"]
    if area is not None:
        args += ["--area", area]
    r = run_bon(*args, cwd=bon_dir)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def new_child(bon_dir, parent, title, area=None):
    args = ["new", title, "--parent", parent, "--why", "w", "--what", "x",
            "--done", "d", "-q"]
    if area is not None:
        args += ["--area", area]
    r = run_bon(*args, cwd=bon_dir)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def new_standalone(bon_dir, title, area=None):
    payload = {"type": "action", "title": title,
               "brief": {"why": "w", "what": "x", "done": "d"}}
    if area is not None:
        payload["area"] = area
    r = run_bon("new", "-q", cwd=bon_dir, input=json.dumps(payload))
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def read_item(bon_dir, item_id):
    for line in (bon_dir / ".bon" / "items.jsonl").read_text().splitlines():
        item = json.loads(line)
        if item["id"] == item_id:
            return item
    raise AssertionError(f"{item_id} not found")


class TestAreaWrites:
    def test_new_flag_persists(self, bon_dir):
        oid = new_outcome(bon_dir, "Measurement holds up", area="measurement")
        assert read_item(bon_dir, oid)["area"] == "measurement"

    def test_new_json_persists(self, bon_dir):
        payload = {"title": "Tools stay sharp", "area": "tooling",
                   "brief": {"why": "w", "what": "x", "done": "d"}}
        r = run_bon("new", "-q", cwd=bon_dir, input=json.dumps(payload))
        assert r.returncode == 0, r.stderr
        assert read_item(bon_dir, r.stdout.strip())["area"] == "tooling"

    def test_new_json_unknown_key_still_errors(self, bon_dir):
        payload = {"title": "T", "are": "typo",
                   "brief": {"why": "w", "what": "x", "done": "d"}}
        r = run_bon("new", "-q", cwd=bon_dir, input=json.dumps(payload))
        assert r.returncode == 1
        assert "are" in r.stderr

    def test_empty_area_not_stored(self, bon_dir):
        oid = new_outcome(bon_dir, "Clean items stay clean", area="  ")
        assert "area" not in read_item(bon_dir, oid)

    def test_new_json_non_string_area_errors(self, bon_dir):
        payload = {"title": "T", "area": 7,
                   "brief": {"why": "w", "what": "x", "done": "d"}}
        r = run_bon("new", "-q", cwd=bon_dir, input=json.dumps(payload))
        assert r.returncode == 1
        assert "area" in r.stderr

    def test_edit_sets_and_clears(self, bon_dir):
        oid = new_outcome(bon_dir, "Areas can move")
        r = run_bon("edit", oid, "--area", "measurement", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert read_item(bon_dir, oid)["area"] == "measurement"
        r = run_bon("edit", oid, "--area", "", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "area" not in read_item(bon_dir, oid)

    def test_edit_json_sets(self, bon_dir):
        oid = new_outcome(bon_dir, "Areas arrive by pipe")
        r = run_bon("edit", oid, cwd=bon_dir, input='{"area": "tooling"}')
        assert r.returncode == 0, r.stderr
        assert read_item(bon_dir, oid)["area"] == "tooling"

    def test_edit_json_null_clears(self, bon_dir):
        oid = new_outcome(bon_dir, "Null unsets", area="tooling")
        r = run_bon("edit", oid, cwd=bon_dir, input='{"area": null}')
        assert r.returncode == 0, r.stderr
        assert "area" not in read_item(bon_dir, oid)

    def test_parented_action_warns_but_stores(self, bon_dir):
        oid = new_outcome(bon_dir, "Parents own the grouping")
        aid = new_child(bon_dir, oid, "Child step")
        r = run_bon("edit", aid, "--area", "elsewhere", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "inert" in r.stderr  # coaching, not validation
        assert read_item(bon_dir, aid)["area"] == "elsewhere"

    def test_show_renders_area(self, bon_dir):
        oid = new_outcome(bon_dir, "Areas are visible", area="measurement")
        r = run_bon("show", oid, cwd=bon_dir)
        assert r.returncode == 0
        assert "Area: measurement" in r.stdout

    def test_show_json_carries_area(self, bon_dir):
        oid = new_outcome(bon_dir, "Areas survive JSON", area="measurement")
        r = run_bon("show", oid, "--json", cwd=bon_dir)
        assert json.loads(r.stdout)["area"] == "measurement"


class TestAreaViews:
    def _seed(self, bon_dir):
        """Two areas + an ungrouped outcome + grouped/ungrouped standalones."""
        o_t = new_outcome(bon_dir, "Tools stay sharp", area="tooling")
        o_m = new_outcome(bon_dir, "Measurement holds up", area="measurement")
        o_u = new_outcome(bon_dir, "Loose ends resolve")
        c_t = new_child(bon_dir, o_t, "Sharpen the knives")
        s_t = new_standalone(bon_dir, "Oil the stone", area="tooling")
        s_u = new_standalone(bon_dir, "Sweep the floor")
        return o_t, o_m, o_u, c_t, s_t, s_u

    def test_group_by_headers_sorted_ungrouped_last(self, bon_dir):
        o_t, o_m, o_u, c_t, s_t, s_u = self._seed(bon_dir)
        r = run_bon("list", "--group-by", "area", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        out = r.stdout
        i_m, i_t, i_u = out.index("[measurement]"), out.index("[tooling]"), out.index("(ungrouped)")
        assert i_m < i_t < i_u  # alphabetical, ungrouped last
        # actions travel with their parent's area
        assert out.index("Sharpen the knives") > i_t
        assert out.index("Oil the stone") > i_t  # standalone by its own area
        assert out.index("Oil the stone") < i_u
        assert out.index("Sweep the floor") > i_u

    def test_group_by_no_areas_renders_one_ungrouped(self, bon_dir):
        new_outcome(bon_dir, "Plain boards stay plain")
        r = run_bon("list", "--group-by", "area", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("(ungrouped)")
        assert "[" not in r.stdout.split("\n")[0]

    def test_plain_list_unchanged_by_area_data(self, bon_dir):
        self._seed(bon_dir)
        r = run_bon("list", cwd=bon_dir)
        assert r.returncode == 0
        assert "[tooling]" not in r.stdout
        assert "(ungrouped)" not in r.stdout

    def test_area_filter(self, bon_dir):
        o_t, o_m, o_u, c_t, s_t, s_u = self._seed(bon_dir)
        r = run_bon("list", "--area", "tooling", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "Tools stay sharp" in r.stdout
        assert "Sharpen the knives" in r.stdout  # subtree travels
        assert "Oil the stone" in r.stdout
        assert "Measurement holds up" not in r.stdout
        assert "Sweep the floor" not in r.stdout

    def test_area_filter_json(self, bon_dir):
        self._seed(bon_dir)
        r = run_bon("list", "--area", "measurement", "--json", cwd=bon_dir)
        data = json.loads(r.stdout)
        titles = [o["title"] for o in data["outcomes"]]
        assert titles == ["Measurement holds up"]
        assert data["standalone"] == []

    def test_group_by_refuses_limit(self, bon_dir):
        self._seed(bon_dir)
        r = run_bon("list", "--group-by", "area", "--limit", "2", cwd=bon_dir)
        assert r.returncode == 1
        assert "--limit" in r.stderr

    def test_group_by_refuses_json(self, bon_dir):
        self._seed(bon_dir)
        r = run_bon("list", "--group-by", "area", "--json", cwd=bon_dir)
        assert r.returncode == 1
        assert "area" in r.stderr  # points at the per-item field instead

    def test_group_by_ready_mode(self, bon_dir):
        o_t, o_m, o_u, c_t, s_t, s_u = self._seed(bon_dir)
        r = run_bon("wait", c_t, "external review", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        r = run_bon("list", "--ready", "--group-by", "area", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "[tooling]" in r.stdout
        assert "Sharpen the knives" not in r.stdout  # waiting, not ready
        assert "(1 waiting)" in r.stdout or "(+1 waiting)" in r.stdout

    def test_group_by_someday_tail_once(self, bon_dir):
        o_t, o_m, o_u, c_t, s_t, s_u = self._seed(bon_dir)
        r = run_bon("someday", o_m, "next quarter", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        r = run_bon("list", "--group-by", "area", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "[measurement]" not in r.stdout  # parked subtree excluded
        assert r.stdout.count("🅿️ Someday: 1 parked") == 1  # one tail, not per group

    def test_group_by_someday_view(self, bon_dir):
        o_t, o_m, o_u, c_t, s_t, s_u = self._seed(bon_dir)
        run_bon("someday", o_m, "next quarter", cwd=bon_dir)
        r = run_bon("list", "--someday", "--group-by", "area", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert "[measurement]" in r.stdout
        assert "[tooling]" not in r.stdout
