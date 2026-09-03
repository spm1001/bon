"""Unit tests for the review skill's net_motion.py (bon-dajusi).

The script ships with the review skill, outside src/, so it is loaded by path
like audit_survey. The Dolt path is exercised only as the LOUD degrade (a port
nothing listens on); the live Dolt tally is a run-time check, not a unit test.
"""

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "skills" / "review" / "scripts" / "net_motion.py"
_spec = importlib.util.spec_from_file_location("net_motion", SCRIPT)
nm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm)


class TestWeeks:
    @pytest.mark.parametrize("stamp", [
        "2026-07-08T10:00:00Z",              # bon's usual shape (20 chars)
        "2026-07-08T10:00:00.123456Z",       # microseconds + Z (27)
        "2026-07-08T10:00:00.123456",        # microseconds, no zone (26)
        "2026-07-08T10:00:00+00:00",         # explicit offset
        "2026-07-08",                        # bare date
    ])
    def test_every_stamp_shape_buckets_to_the_same_week(self, stamp):
        assert nm.week_of(stamp) == "2026-W28"

    @pytest.mark.parametrize("bad", [None, "", "garbage", "2026-13-40T00:00:00Z", "T10:00:00Z"])
    def test_unparseable_is_none_not_a_crash(self, bad):
        assert nm.week_of(bad) is None

    def test_iso_week_year_boundary(self):
        # 2026-12-31 is a Thursday -> ISO week 53 of 2026; 2027-01-04 is W01 of 2027
        assert nm.week_of("2026-12-31T00:00:00Z") == "2026-W53"
        assert nm.week_of("2027-01-04T00:00:00Z") == "2027-W01"

    def test_week_range_inclusive(self):
        assert nm.week_range("2026-W27", "2026-W29") == ["2026-W27", "2026-W28", "2026-W29"]

    def test_week_range_refuses_reversed_and_malformed(self):
        with pytest.raises(ValueError):
            nm.week_range("2026-W30", "2026-W27")
        with pytest.raises(ValueError):
            nm.parse_week("2026-07")
        with pytest.raises(ValueError):
            nm.parse_week("2026-W60")

    def test_weeks_back_ends_in_current_week(self):
        weeks = nm.weeks_back(3, today=date(2026, 9, 3))
        assert weeks == ["2026-W34", "2026-W35", "2026-W36"]


def _rec(id_, status, created, done=None, backend="jsonl", board="b"):
    return {"id": id_, "prefix": id_.split("-")[0], "board": board, "backend": backend,
            "status": status, "created_at": created, "done_at": done}


WEEKS = ["2026-W27", "2026-W28", "2026-W29"]


class TestTally:
    def test_net_is_closed_minus_minted_and_residual_zero(self):
        recs = [
            _rec("b-1", "done", "2026-06-01T00:00:00Z", "2026-07-07T00:00:00Z"),   # pre-window mint, W28 close
            _rec("b-2", "open", "2026-06-15T00:00:00Z"),                           # open at start, still open
            _rec("b-3", "open", "2026-07-01T00:00:00Z"),                           # W27 mint
            _rec("b-4", "done", "2026-07-01T00:00:00Z", "2026-07-15T00:00:00Z"),   # W27 mint, W29 close
            _rec("b-5", "done", "2026-05-01T00:00:00Z", "2026-05-02T00:00:00Z"),   # all before window
        ]
        t = nm.tally(recs, WEEKS)
        by = {w["week"]: w for w in t["weeks"]}
        assert (by["2026-W27"]["minted"], by["2026-W27"]["closed"], by["2026-W27"]["net"]) == (2, 0, -2)
        assert by["2026-W28"]["net"] == +1
        assert by["2026-W29"]["net"] == +1
        j = t["sources"]["jsonl"]
        assert (j["open_at_start"], j["open_now"], j["sum_net"]) == (2, 2, 0)
        assert j["residual"] == 0
        assert t["sources"]["dolt"]["items"] == 0
        assert t["boards"]["b"]["net"] == 0 and t["boards"]["b"]["open_now"] == 2

    def test_done_without_done_at_goes_red_in_the_residual(self):
        # A closed item whose stamp is missing cannot be placed in any week:
        # it must show as a non-zero residual and be named, never absorbed.
        recs = [_rec("b-1", "done", "2026-06-01T00:00:00Z", None)]
        t = nm.tally(recs, WEEKS)
        j = t["sources"]["jsonl"]
        assert j["done_without_stamp"] == 1
        assert j["residual"] == -1  # counted open-at-start, never closed, not open now

    def test_unparseable_created_at_is_counted_not_dropped(self):
        recs = [_rec("b-1", "open", "not-a-date")]
        j = nm.tally(recs, WEEKS)["sources"]["jsonl"]
        assert j["unparseable_created"] == 1
        assert j["residual"] == 1  # open now, but never minted anywhere the table can see

    def test_sources_are_kept_apart(self):
        recs = [_rec("d-1", "open", "2026-07-01T00:00:00Z", backend="dolt", board="D"),
                _rec("j-1", "done", "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z")]
        t = nm.tally(recs, WEEKS)
        w27 = t["weeks"][0]["by_source"]
        assert w27["dolt"] == {"minted": 1, "closed": 0, "net": -1}
        assert w27["jsonl"] == {"minted": 1, "closed": 1, "net": 0}
        assert t["boards"]["D"]["backend"] == "dolt"


def _board(root: Path, name: str, prefix: str, items: list[dict], backend=None, archive=None):
    bon = root / name / ".bon"
    bon.mkdir(parents=True)
    (bon / "prefix").write_text(prefix)
    if backend:
        (bon / "backend").write_text(backend)
    (bon / "items.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    if archive is not None:
        (bon / "archive.jsonl").write_text("".join(json.dumps(i) + "\n" for i in archive))
    return bon


def _item(id_, status="open", created="2026-07-01T00:00:00Z", done=None):
    d = {"id": id_, "status": status, "created_at": created, "type": "action", "title": id_}
    if done:
        d["done_at"] = done
    return d


class TestLoadJsonl:
    def test_ghost_beside_dolt_backend_is_skipped_and_named(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nm.audit_survey, "EXTRA_BOARD_DIRS", [])
        _board(tmp_path, "live", "lv", [_item("lv-1")])
        ghost = _board(tmp_path, "migrated", "mg", [_item("mg-1"), _item("mg-2")], backend="dolt")
        recs, notes = nm.load_jsonl_records([tmp_path])
        assert [r["id"] for r in recs] == ["lv-1"]
        assert notes["ghosts_skipped"] == [str(ghost / "items.jsonl")]
        assert notes["boards"] == ["live"]

    def test_duplicate_id_across_two_boards_counted_once_and_named(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nm.audit_survey, "EXTRA_BOARD_DIRS", [])
        _board(tmp_path, "a-clone", "x", [_item("x-1")])
        _board(tmp_path, "b-clone", "x", [_item("x-1"), _item("x-2")])
        recs, notes = nm.load_jsonl_records([tmp_path])
        assert sorted(r["id"] for r in recs) == ["x-1", "x-2"]
        assert notes["duplicate_ids_skipped"] == [{"id": "x-1", "first": "a-clone", "again": "b-clone"}]

    def test_archive_is_folded_in(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nm.audit_survey, "EXTRA_BOARD_DIRS", [])
        _board(tmp_path, "r", "r", [_item("r-1")],
               archive=[_item("r-0", "done", "2026-06-01T00:00:00Z", "2026-07-08T00:00:00Z")])
        recs, _ = nm.load_jsonl_records([tmp_path])
        assert sorted(r["id"] for r in recs) == ["r-0", "r-1"]
        t = nm.tally(recs, WEEKS)
        assert t["weeks"][1]["closed"] == 1  # the archived close lands in W28


class TestConvergence:
    def test_median_is_sweep_robust(self):
        nets = [-40, +300, -50, -60, -45, -55]  # one bulk-close sweep in week 2
        weeks = [{"week": f"2026-W{30 + i}", "net": n, "minted": 0, "closed": 0} for i, n in enumerate(nets)]
        c = nm.convergence(weeks)
        assert c["last2_net"] == -100
        assert c["prior_mean"] == 37.5       # dragged positive by the sweep
        assert c["prior_median"] == -45.0    # what the ordinary week looks like
        assert c["weeks_minting_more"] == 5


class TestCli:
    def _run(self, *args, env=None):
        import os
        e = dict(os.environ, **(env or {}))
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=e)

    def test_from_without_to_exits_2(self):
        assert self._run("--from", "2026-W27").returncode == 2

    def test_zero_weeks_exits_2(self):
        assert self._run("--weeks", "0").returncode == 2

    def test_missing_root_exits_2(self, tmp_path):
        assert self._run("--roots", str(tmp_path / "nope")).returncode == 2

    def test_dolt_outage_degrades_loudly_and_jsonl_still_prints(self, tmp_path):
        # HOME is pointed at tmp so no real ~/.claude/.bon or dolt.toml is read;
        # port 1 has no listener, so the connect is refused at once.
        _board(tmp_path, "solo", "so", [_item("so-1", created="2026-07-01T00:00:00Z")])
        r = self._run("--roots", str(tmp_path), "--from", "2026-W27", "--to", "2026-W28", "--json",
                      env={"HOME": str(tmp_path), "BON_DOLT_HOST": "127.0.0.1", "BON_DOLT_PORT": "1"})
        assert r.returncode == 0, r.stderr
        assert "WARNING: Dolt unreachable" in r.stderr and "DEGRADED" in r.stderr
        out = json.loads(r.stdout)
        assert out["dolt"] == "unreachable"
        assert out["sources"]["jsonl"]["items"] >= 1  # the JSONL half is still there
        assert list(out["boards"]) == ["solo"]  # hermetic: only the tmp board
