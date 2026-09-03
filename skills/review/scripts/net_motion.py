# /// script
# requires-python = ">=3.11"
# dependencies = ["pymysql"]
# ///
"""Net motion — minted vs closed per ISO week across EVERY board, Dolt and JSONL.

One table for the review ceremony's survey phase (bon-dajusi): per week, how
many items the estate minted (created_at) and closed (done_at), the net, and
the same split by backend, so a "we are in balance" belief can be checked
against both halves rather than the JSONL half alone.

Sources
* Dolt: the global `items` + `archive` tables (every prefix present, mapped in
  the `repos` table or not — an unmapped prefix is still a board that mints).
* JSONL: every `.bon/items.jsonl` (+ `archive.jsonl`) under the scan roots and
  the extra board dirs, discovered by audit_survey.discover_boards — so the
  plugin-cache copies of a board are excluded exactly as the survey excludes
  them. A `items.jsonl` sitting beside `.bon/backend = dolt` is a
  pre-migration ghost and is SKIPPED (named on stderr), never counted.

The parts are checked against the whole: for each source the script prints
`open now − (open at window start + Σ net)`, which is zero when every item has
a parseable created_at and every done item a parseable done_at. A non-zero
residual is reported, never silently absorbed, and unparseable stamps are
counted beside it.

Usage:
    uv run --script net_motion.py                      # last 10 ISO weeks, text
    uv run --script net_motion.py --from 2026-W27 --to 2026-W36
    uv run --script net_motion.py --json               # machine-readable
    uv run --script net_motion.py --top 12             # more boards in the growth table
Exit 2 on a malformed flag; a Dolt outage degrades LOUDLY (stderr + `dolt:
"unreachable"` in the output) and the JSONL half still prints.
"""

import argparse
import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("audit_survey", _HERE / "audit_survey.py")
audit_survey = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_survey)


# ---------- weeks ----------

def week_of(stamp: str | None) -> str | None:
    """ISO week label ('2026-W27') for an ISO-8601 stamp, keyed on its date part.

    Only the leading YYYY-MM-DD is read, so every zone suffix this estate has
    written (Z, +00:00, none, microseconds or not) buckets identically. Returns
    None for anything that does not start with a real date — the caller counts
    those, it does not drop them.
    """
    if not stamp or len(stamp) < 10:
        return None
    try:
        d = date.fromisoformat(stamp[:10])
    except ValueError:
        return None
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def parse_week(label: str) -> tuple[int, int]:
    """'2026-W27' -> (2026, 27); raises ValueError on anything else."""
    y, _, w = label.upper().partition("-W")
    if not (y.isdigit() and w.isdigit()):
        raise ValueError(f"not an ISO week label: {label!r} (want YYYY-Www)")
    year, week = int(y), int(w)
    date.fromisocalendar(year, week, 1)  # raises on week 54 etc.
    return year, week


def week_range(start: str, end: str) -> list[str]:
    """Every ISO week label from start to end inclusive."""
    y0, w0 = parse_week(start)
    y1, w1 = parse_week(end)
    d = date.fromisocalendar(y0, w0, 1)
    stop = date.fromisocalendar(y1, w1, 1)
    if d > stop:
        raise ValueError(f"--from {start} is after --to {end}")
    out = []
    while d <= stop:
        out.append(week_of(d.isoformat()))
        d += timedelta(days=7)
    return out


def current_week(today: date | None = None) -> str:
    today = today or datetime.now(timezone.utc).date()
    return week_of(today.isoformat())


def weeks_back(n: int, today: date | None = None) -> list[str]:
    """The last n ISO weeks ending in the current (partial) week."""
    today = today or datetime.now(timezone.utc).date()
    end = current_week(today)
    start_day = today - timedelta(days=7 * (n - 1))
    return week_range(week_of(start_day.isoformat()), end)


def week_start(label: str) -> date:
    y, w = parse_week(label)
    return date.fromisocalendar(y, w, 1)


# ---------- loading ----------

def _record(item: dict, board: str, backend: str) -> dict:
    return {
        "id": item.get("id"),
        "prefix": (item.get("id") or "").split("-", 1)[0],
        "board": board,
        "backend": backend,
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "done_at": item.get("done_at"),
    }


def _read_jsonl(path: Path) -> list[dict]:
    """Rows of a .bon JSONL file, last occurrence of an id wins (bon's own dedup)."""
    by_id: dict[str, dict] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                item = json.loads(line)
                by_id[item["id"]] = item
    return list(by_id.values())


def load_jsonl_records(roots: list[Path]) -> tuple[list[dict], dict]:
    """Every JSONL board's items + archive under the roots, as records.

    Returns (records, notes) where notes carries what was NOT counted and why:
    ghosts (items.jsonl beside backend=dolt), duplicate ids seen in a second
    board (counted once, first board wins), and the board list.
    """
    boards = audit_survey.discover_boards(roots)
    records: list[dict] = []
    seen: dict[str, str] = {}
    ghosts: list[str] = []
    duplicates: list[dict] = []
    board_labels: list[str] = []
    for b in boards:
        items_path = b["bon_dir"] / "items.jsonl"
        label = audit_survey.repo_label(b["repo_path"], b["root"])
        if b["backend"] != "jsonl":
            if items_path.exists():
                ghosts.append(str(items_path))
            continue
        if not items_path.exists():
            continue
        board_labels.append(label)
        rows = _read_jsonl(items_path)
        archive_path = b["bon_dir"] / "archive.jsonl"
        if archive_path.exists():
            rows += _read_jsonl(archive_path)
        for item in rows:
            iid = item.get("id")
            if iid in seen:
                duplicates.append({"id": iid, "first": seen[iid], "again": label})
                continue
            seen[iid] = label
            records.append(_record(item, label, "jsonl"))
    notes = {
        "boards": sorted(board_labels),
        "ghosts_skipped": ghosts,
        "duplicate_ids_skipped": duplicates,
    }
    return records, notes


def load_dolt_records() -> tuple[list[dict], dict]:
    """Every row of Dolt's items + archive tables, labelled via the repos table.

    Raises on connection failure — the caller decides how loudly to degrade.
    An unmapped prefix (no repos row) is labelled `<prefix> (unmapped)` and
    COUNTED: it is still a board that minted and closed.
    """
    import pymysql

    config = audit_survey.load_dolt_config()
    conn = pymysql.connect(
        host=config["host"], port=config["port"], user=config["user"],
        password=config["password"], database=config["database"],
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, created_at, done_at FROM items")
            rows = list(cur.fetchall())
            cur.execute("SELECT id, status, created_at, done_at FROM archive")
            archive_rows = list(cur.fetchall())
            cur.execute("SELECT prefix, repo_name FROM repos")
            repos = {r["prefix"]: r["repo_name"] for r in cur.fetchall()}
    finally:
        conn.close()
    records = []
    unmapped: set[str] = set()
    for row in rows + archive_rows:
        prefix = row["id"].split("-", 1)[0]
        name = repos.get(prefix)
        if name is None:
            unmapped.add(prefix)
            name = f"{prefix} (unmapped)"
        records.append(_record(row, name, "dolt"))
    notes = {
        "boards": sorted({r["board"] for r in records}),
        "repos_rows": len(repos),
        "unmapped_prefixes": sorted(unmapped),
        "archive_rows": len(archive_rows),
    }
    return records, notes


# ---------- tally ----------

def tally(records: list[dict], weeks: list[str]) -> dict:
    """Bucket records by ISO week of created_at / done_at, per source and per board.

    Returns a dict with:
      weeks: [{week, minted, closed, net, by_source: {dolt: {...}, jsonl: {...}}}]
      boards: {label: {backend, minted, closed, net, net_last2, open_now}}
      sources: {dolt|jsonl: {open_now, open_at_start, sum_net, residual,
                             unparseable_created, unparseable_done, items}}
    net = closed − minted (negative: the backlog grew), matching the 2026-09-01
    handoff figures. The residual is open_now − (open_at_start − Σ net); it is
    zero when every stamp inside and before the window parsed. Items whose
    done_at is missing while status is done are counted in `done_without_stamp`
    (they inflate open_at_start and show up as a positive residual).
    """
    wk = {w: i for i, w in enumerate(weeks)}
    start = week_start(weeks[0])
    last2 = set(weeks[-2:])
    per_week = {w: {"dolt": [0, 0], "jsonl": [0, 0]} for w in weeks}
    boards: dict[str, dict] = {}
    src = {
        s: {"items": 0, "open_now": 0, "open_at_start": 0, "sum_net": 0,
            "unparseable_created": 0, "unparseable_done": 0,
            "done_without_stamp": 0}
        for s in ("dolt", "jsonl")
    }
    for r in records:
        s = r["backend"]
        st = src[s]
        st["items"] += 1
        b = boards.setdefault(r["board"], {
            "backend": s, "minted": 0, "closed": 0, "net": 0,
            "net_last2": 0, "open_now": 0,
        })
        is_open = r["status"] == "open"
        if is_open:
            st["open_now"] += 1
            b["open_now"] += 1
        cw = week_of(r["created_at"])
        if cw is None:
            st["unparseable_created"] += 1
        elif cw in wk:
            per_week[cw][s][0] += 1
            b["minted"] += 1
            if cw in last2:
                b["net_last2"] -= 1
        # open_at_start: created before the window, not yet done before it
        created_before = cw is not None and week_start(cw) < start
        dw = week_of(r["done_at"]) if r["done_at"] else None
        if r["status"] == "done" and not r["done_at"]:
            st["done_without_stamp"] += 1
        elif r["done_at"] and dw is None:
            st["unparseable_done"] += 1
        if dw is not None and dw in wk:
            per_week[dw][s][1] += 1
            b["closed"] += 1
            if dw in last2:
                b["net_last2"] += 1
        done_before = dw is not None and week_start(dw) < start
        if created_before and not done_before:
            st["open_at_start"] += 1
    out_weeks = []
    for w in weeks:
        d, j = per_week[w]["dolt"], per_week[w]["jsonl"]
        minted, closed = d[0] + j[0], d[1] + j[1]
        out_weeks.append({
            "week": w, "minted": minted, "closed": closed, "net": closed - minted,
            "by_source": {
                "dolt": {"minted": d[0], "closed": d[1], "net": d[1] - d[0]},
                "jsonl": {"minted": j[0], "closed": j[1], "net": j[1] - j[0]},
            },
        })
        src["dolt"]["sum_net"] += d[1] - d[0]
        src["jsonl"]["sum_net"] += j[1] - j[0]
    for s in src.values():
        s["residual"] = s["open_now"] - (s["open_at_start"] - s["sum_net"])
    for b in boards.values():
        b["net"] = b["closed"] - b["minted"]
    return {"weeks": out_weeks, "boards": boards, "sources": src}


def convergence(weeks: list[dict]) -> dict:
    """Last-fortnight net against the mean weekly net of the weeks before it."""
    if len(weeks) < 3:
        return {"last2_net": sum(w["net"] for w in weeks), "prior_mean": None}
    last2 = weeks[-2:]
    prior = weeks[:-2]
    prior_mean = sum(w["net"] for w in prior) / len(prior)
    prior_sorted = sorted(w["net"] for w in prior)
    mid = len(prior_sorted) // 2
    prior_median = (prior_sorted[mid] if len(prior_sorted) % 2
                    else (prior_sorted[mid - 1] + prior_sorted[mid]) / 2)
    last2_net = sum(w["net"] for w in last2)
    return {
        "last2_weeks": [w["week"] for w in last2],
        "last2_net": last2_net,
        "last2_mean": last2_net / 2,
        "prior_weeks": [prior[0]["week"], prior[-1]["week"]],
        "prior_mean": round(prior_mean, 1),
        "prior_median": round(prior_median, 1),
        "weeks_minting_more": sum(1 for w in weeks if w["net"] < 0),
        "weeks_total": len(weeks),
    }


# ---------- rendering ----------

def _fmt_net(n: int) -> str:
    return f"{n:+d}" if n else "0"


def render_text(result: dict, top: int) -> str:
    weeks = result["weeks"]
    src = result["sources"]
    cur = result["current_week"]
    lines = []
    dolt_state = result["dolt"]
    lines.append(
        f"Net motion {weeks[0]['week']}..{weeks[-1]['week']} — net = closed − minted "
        f"(negative: backlog grew). Dolt: {dolt_state}"
        + (f", {len(result['dolt_notes']['boards'])} boards" if dolt_state == "global" else "")
        + f"; JSONL: {len(result['jsonl_notes']['boards'])} boards."
    )
    lines.append(f"{'week':<10}| {'all':>17} | {'dolt':>17} | {'jsonl':>17}")
    lines.append(f"{'':<10}| {'minted clsd  net':>17} | {'minted clsd  net':>17} | {'minted clsd  net':>17}")
    for w in weeks:
        d, j = w["by_source"]["dolt"], w["by_source"]["jsonl"]
        mark = "*" if w["week"] == cur else " "
        lines.append(
            f"{w['week']}{mark:<2}| {w['minted']:>6} {w['closed']:>4} {_fmt_net(w['net']):>5} | "
            f"{d['minted']:>6} {d['closed']:>4} {_fmt_net(d['net']):>5} | "
            f"{j['minted']:>6} {j['closed']:>4} {_fmt_net(j['net']):>5}"
        )
    tm = sum(w["minted"] for w in weeks)
    tc = sum(w["closed"] for w in weeks)
    lines.append(
        f"{'Σ window':<10}| {tm:>6} {tc:>4} {_fmt_net(tc - tm):>5} | "
        f"{'':>11} {_fmt_net(src['dolt']['sum_net']):>5} | {'':>11} {_fmt_net(src['jsonl']['sum_net']):>5}"
    )
    if cur in {w["week"] for w in weeks}:
        days_in = (date.fromisoformat(result["today"]) - week_start(cur)).days + 1
        lines.append(f"* {cur} is the current week — partial: {days_in} of 7 days, through {result['today']}. "
                     f"A fortnight read on day 1–2 of a week is mostly the prior week.")
    lines.append("")
    lines.append("Whole vs parts (residual = open now − (open at window start − Σ net); 0 = the parts account for the whole):")
    for s in ("dolt", "jsonl"):
        x = src[s]
        extra = []
        if x["unparseable_created"]:
            extra.append(f"{x['unparseable_created']} unparseable created_at")
        if x["unparseable_done"]:
            extra.append(f"{x['unparseable_done']} unparseable done_at")
        if x["done_without_stamp"]:
            extra.append(f"{x['done_without_stamp']} done without done_at")
        flag = "" if x["residual"] == 0 else "  <-- NON-ZERO: parts do not account for the whole"
        lines.append(
            f"  {s:<6} items {x['items']:>5}  open now {x['open_now']:>4}  open at start {x['open_at_start']:>4}"
            f"  Σ net {_fmt_net(x['sum_net']):>5}  residual {x['residual']:>3}{flag}"
            + (f"  ({'; '.join(extra)})" if extra else "")
        )
    open_total = src["dolt"]["open_now"] + src["jsonl"]["open_now"]
    lines.append(f"  open now, whole estate: {open_total} (dolt {src['dolt']['open_now']} + jsonl {src['jsonl']['open_now']})")
    conv = result["convergence"]
    lines.append("")
    if conv.get("prior_mean") is not None:
        lines.append(
            f"Convergence: {conv['weeks_minting_more']} of {conv['weeks_total']} weeks minted more than they closed; "
            f"last fortnight ({conv['last2_weeks'][0]}, {conv['last2_weeks'][1]}) net {_fmt_net(conv['last2_net'])} "
            f"({conv['last2_mean']:+.1f}/wk) against {conv['prior_mean']:+.1f}/wk mean, "
            f"{conv['prior_median']:+.1f}/wk median, over {conv['prior_weeks'][0]}..{conv['prior_weeks'][1]} "
            f"(median is the sweep-robust one: a bulk-close week skews the mean)."
        )
    growth = sorted(result["boards"].items(), key=lambda kv: (kv[1]["net"], -kv[1]["minted"]))
    lines.append("")
    lines.append(f"Boards carrying the growth (most negative net over the window first, top {top}):")
    lines.append(f"  {'board':<34}{'be':<6}{'minted':>7}{'closed':>7}{'net':>6}{'last2':>7}{'open':>6}")
    for label, b in growth[:top]:
        lines.append(
            f"  {label:<34}{b['backend']:<6}{b['minted']:>7}{b['closed']:>7}"
            f"{_fmt_net(b['net']):>6}{_fmt_net(b['net_last2']):>7}{b['open_now']:>6}"
        )
    shrinking = [(label, b) for label, b in growth if b["net"] > 0]
    if shrinking:
        best = sorted(shrinking, key=lambda kv: -kv[1]["net"])[:5]
        lines.append("  shrinking: " + ", ".join(f"{label} {_fmt_net(b['net'])}" for label, b in best))
    notes = []
    jn = result["jsonl_notes"]
    if jn["ghosts_skipped"]:
        notes.append(f"{len(jn['ghosts_skipped'])} pre-migration ghost items.jsonl skipped (beside backend=dolt): "
                     + ", ".join(jn["ghosts_skipped"]))
    if jn["duplicate_ids_skipped"]:
        notes.append(f"{len(jn['duplicate_ids_skipped'])} duplicate ids seen in a second JSONL board, counted once "
                     f"(e.g. {jn['duplicate_ids_skipped'][0]})")
    dn = result.get("dolt_notes") or {}
    if dn.get("unmapped_prefixes"):
        notes.append(f"Dolt prefixes with no repos row, counted as '(unmapped)': {', '.join(dn['unmapped_prefixes'])}")
    if notes:
        lines.append("")
        lines.append("Notes:")
        lines.extend(f"  - {n}" for n in notes)
    return "\n".join(lines)


# ---------- main ----------

def run(weeks: list[str], roots: list[Path], today: date) -> dict:
    """Load both sources, tally, and return the full result dict (JSON-safe)."""
    dolt_state, dolt_records, dolt_notes = "global", [], None
    try:
        dolt_records, dolt_notes = load_dolt_records()
    except Exception as e:  # pymysql errors, socket errors — all mean "not read"
        dolt_state = "unreachable"
        print(
            f"WARNING: Dolt unreachable ({type(e).__name__}: {e}) — this table is "
            f"DEGRADED: JSONL boards only, every Dolt board missing.",
            file=sys.stderr,
        )
    jsonl_records, jsonl_notes = load_jsonl_records(roots)
    result = tally(dolt_records + jsonl_records, weeks)
    result["convergence"] = convergence(result["weeks"])
    result.update({
        "dolt": dolt_state,
        "dolt_notes": dolt_notes,
        "jsonl_notes": jsonl_notes,
        "roots": [str(r) for r in roots],
        "current_week": current_week(today),
        "today": today.isoformat(),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Estate-wide net motion per ISO week (Dolt + JSONL).")
    ap.add_argument("--weeks", type=int, default=10, help="window length ending in the current week (default 10)")
    ap.add_argument("--from", dest="start", help="first ISO week, e.g. 2026-W27 (with --to)")
    ap.add_argument("--to", dest="end", help="last ISO week, e.g. 2026-W36")
    ap.add_argument("--roots", nargs="+", type=Path, help="scan roots for JSONL boards (default: ~/repos, ~/Repos, ~/notes)")
    ap.add_argument("--top", type=int, default=10, help="boards to list in the growth table")
    ap.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = ap.parse_args(argv)

    today = datetime.now(timezone.utc).date()
    try:
        if args.start or args.end:
            if not (args.start and args.end):
                ap.error("--from and --to go together")
            weeks = week_range(args.start, args.end)
        else:
            if args.weeks < 1:
                ap.error("--weeks must be >= 1")
            weeks = weeks_back(args.weeks, today)
    except ValueError as e:
        ap.error(str(e))
    roots = [r.expanduser().resolve() for r in args.roots] if args.roots else audit_survey.default_roots()
    missing = [str(r) for r in roots if not r.is_dir()]
    if missing:
        ap.error(f"root does not exist: {', '.join(missing)}")

    result = run(weeks, roots, today)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_text(result, args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
