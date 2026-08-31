# /// script
# requires-python = ">=3.11"
# dependencies = ["pymysql"]
# ///
"""Audit survey — estate-wide view of open bon items for the /review skill.

Hybrid survey (bon-fuwofi): the shared Dolt database is the PRIMARY index —
one global query covers every Dolt board in the estate, including repos with
no clone on this machine and boards outside the scan roots (~/.dotfiles).
The filesystem scan is demoted to a JSONL-straggler sweep: it only reads
boards without a Dolt backend (their items already arrive via the global
query).

Repo labels come from Dolt's self-registering `repos` mapping table
(prefix → repo_name, origin_url — see `bon register`). A prefix with no
mapping row surfaces as "<prefix> (unmapped)" — fail visible, never guess.

Each repo group carries `local_path` (a clone under the scan roots) or
`not_cloned_here: true` so the review skill can split verification
(local code checks) from survey-only visibility.

If the Dolt server is unreachable the survey falls back to the old
filesystem-only behaviour (including per-board `bon list --jsonl` for local
Dolt boards) and says so loudly — a degraded survey must never present
itself as the whole estate.

Default roots: whichever of ~/repos, ~/Repos, ~/notes exist (deduped by
realpath). REPOS_DIR env var overrides with a single root; --roots overrides
both. The ~/.claude board (JSONL, prefix carte) is probed directly rather
than walked: the walk skips hidden directories, and a recursive walk of
~/.claude would surface phantom boards from vendored marketplace clones.
Connection config: BON_DOLT_* env vars > ~/.config/bon/dolt.toml
(same resolution as bon's dolt.py, minus the macOS keychain).

Recent wins ride the same pass (bon-jagoha): each repo group carries
`recent_dones` (items closed inside the window, newest first, capped with the
true total in `recent_done_count`) and, where a clone exists, a light `git`
signal (commit count in the window + last commit line). The pyramid's
"Recent Progress" lines come from these, not a separate sweep.

Jobs grouping: each repo group carries `job` when assigned — Dolt boards from
the repos table's `job` column (`bon register --job`), JSONL boards from a
`.bon/job` marker file. Boards with open items and no job are listed in
`jobs_unassigned` — fail-visible for assignment, never guessed. `--job <slug>`
scopes the survey to one or more jobs groups.

Scoping is loud, never quiet (bon-libito). `--repos` and `--job` match WHOLE
labels — for repos, the whole label or its whole final path segment, so
`--repos sonner` finds `spm1001/sonner` but `--repos passe` no longer sweeps in
`spm1001/passe-partout`. A scope flag that quietly returns the wrong-sized
answer looks exactly like a good one, so four things are refused or announced:

* an unrecognised, misspelled, `=`-joined or repeated option exits — the parse
  refuses what it cannot read rather than ignoring it;
* a flag given with no values exits rather than widening to the estate;
* a value matching no board exits, listing the substring near-misses, so a
  caller relying on the old substring behaviour is told exactly what to type;
* a narrowing is named on stderr — both the near-misses one `--repos` value
  excludes (computed against the union of all values' hits, so a label another
  value pulled in is never reported as dropped) and, when `--repos` and `--job`
  compose, the boards `--repos` matched that `--job` then discarded.

Provenance, since it is the useful part: the empty-flag and no-match exits
shipped by design, while the whole first bullet and both refinements in the
last one came out of adversarial rounds AFTER the card looked finished. The
first version of this hardening still surveyed all 52 boards, silently, on
`--repos=bon`; the second still dropped a value after `--window-days`.

Usage:
    uv run --script audit_survey.py                        # JSON to stdout
    uv run --script audit_survey.py --repos trousse passe  # Filter by label
    uv run --script audit_survey.py --job toolmaking       # Filter by jobs group
    uv run --script audit_survey.py --roots ~/repos        # Explicit roots
    uv run --script audit_survey.py --window-days 14       # Recent-wins window
    uv run --script audit_survey.py --full-dones           # Lift the per-board
                                                           # recent_dones cap
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------- Dolt connection (mirrors bon/dolt.py resolution) ----------

_DOLT_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 3306,
    "database": "bon",
    "user": "root",
    "password": "",
}


def load_dolt_config() -> dict:
    """Connection config: env vars > ~/.config/bon/dolt.toml > defaults."""
    config = dict(_DOLT_DEFAULTS)
    config_path = Path.home() / ".config" / "bon" / "dolt.toml"
    if config_path.exists():
        try:
            import tomllib
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)
            for key in ("host", "port", "database", "user", "password"):
                if key in file_config:
                    config[key] = file_config[key]
        except Exception as e:
            print(f"Warning: failed to read {config_path}: {e}", file=sys.stderr)

    env_map = {
        "BON_DOLT_HOST": "host",
        "BON_DOLT_PORT": "port",
        "BON_DOLT_DATABASE": "database",
        "BON_DOLT_USER": "user",
        "BON_DOLT_PASSWORD": "password",
    }
    for env_key, config_key in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            config[config_key] = int(val) if config_key == "port" else val
    return config


def query_dolt_global(
    done_cutoff: str,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]], dict[str, dict]]:
    """One global pass: open items and recent dones grouped by prefix, plus repos map.

    Returns (open_by_prefix, dones_by_prefix, repos_map). `done_cutoff` is an
    ISO-8601 Z timestamp; done_at is stored in the same format, so the string
    comparison is a correct date comparison. Raises on any connection/query
    failure — the caller decides the fallback.
    """
    import pymysql

    config = load_dolt_config()
    conn = pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            # `someday` arrived August 2026 (bon-majoca) — fall back to the
            # older shape if this server's schema hasn't migrated yet.
            try:
                cur.execute(
                    "SELECT id, type, title, status, brief, parent, waiting_for, "
                    "someday, created_at FROM items WHERE status = 'open'"
                )
                rows = cur.fetchall()
            except pymysql.err.MySQLError:
                cur.execute(
                    "SELECT id, type, title, status, brief, parent, waiting_for, "
                    "created_at FROM items WHERE status = 'open'"
                )
                rows = cur.fetchall()
            cur.execute(
                "SELECT id, type, title, done_at, done_note FROM items "
                "WHERE status = 'done' AND done_at >= %s",
                (done_cutoff,),
            )
            done_rows = cur.fetchall()
            # `job` arrived August 2026; a server whose schema predates it
            # (migration rides the next bon CLI connection) must not break
            # the survey — fall back to the jobless shape.
            try:
                cur.execute("SELECT prefix, repo_name, origin_url, job FROM repos")
                repo_rows = cur.fetchall()
            except pymysql.err.MySQLError:
                cur.execute("SELECT prefix, repo_name, origin_url FROM repos")
                repo_rows = [dict(r, job=None) for r in cur.fetchall()]
            repos_map = {
                r["prefix"]: {
                    "repo_name": r["repo_name"],
                    "origin_url": r["origin_url"],
                    "job": r.get("job"),
                }
                for r in repo_rows
            }
    finally:
        conn.close()

    by_prefix: dict[str, list[dict]] = {}
    for row in rows:
        item = _dolt_row_to_item(row)
        prefix = item["id"].split("-", 1)[0]
        by_prefix.setdefault(prefix, []).append(item)
    dones_by_prefix: dict[str, list[dict]] = {}
    for row in done_rows:
        prefix = row["id"].split("-", 1)[0]
        dones_by_prefix.setdefault(prefix, []).append(dict(row))
    return by_prefix, dones_by_prefix, repos_map


def _dolt_row_to_item(row: dict) -> dict:
    """Minimal row→item conversion (brief JSON, waiting_for list-or-legacy)."""
    item = dict(row)
    brief = item.get("brief")
    if isinstance(brief, str):
        try:
            item["brief"] = json.loads(brief)
        except json.JSONDecodeError:
            item["brief"] = {}
    wf = item.get("waiting_for")
    if isinstance(wf, str):
        item["waiting_for"] = json.loads(wf) if wf.startswith("[") else [wf]
    return item


# ---------- JSONL boards (filesystem) ----------

def load_items_jsonl(bon_path: Path) -> list[dict]:
    """Load items from a .bon/items.jsonl file, deduping by last occurrence."""
    items = {}
    with open(bon_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            items[item["id"]] = item  # last wins (union merge dedup)
    return list(items.values())


def load_items_dolt_via_cli(repo_path: Path) -> list[dict]:
    """Fallback only: read a local Dolt board via `bon list --jsonl`."""
    try:
        result = subprocess.run(
            ["bon", "list", "--jsonl"],
            cwd=repo_path,
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        items = {}
        for line in result.stdout.strip().splitlines():
            if line:
                item = json.loads(line)
                items[item["id"]] = item
        return list(items.values())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_backend(bon_dir: Path) -> str:
    """Read .bon/backend to determine storage type. Absent = jsonl."""
    backend_file = bon_dir / "backend"
    if backend_file.exists():
        return backend_file.read_text().strip()
    return "jsonl"


def get_prefix(bon_dir: Path) -> str | None:
    """Read .bon/prefix (None when the marker is absent, e.g. fresh clone)."""
    prefix_file = bon_dir / "prefix"
    if prefix_file.exists():
        return prefix_file.read_text().strip()
    return None


def get_job(bon_dir: Path) -> str | None:
    """Read .bon/job — the JSONL board's jobs-group marker (Dolt boards use
    the repos table's job column instead; see `bon register --job`)."""
    job_file = bon_dir / "job"
    if job_file.exists():
        return job_file.read_text().strip() or None
    return None


# ---------- shared shaping ----------

def age_flag(created_at: str | None) -> str | None:
    """Return an age flag based on item creation date."""
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days >= 60:
            return "very_old"
        if age_days >= 30:
            return "old"
        return None
    except (ValueError, TypeError):
        return None


def item_record(item: dict) -> dict:
    """Extract the fields the audit skill needs for verification."""
    record = {
        "id": item["id"],
        "title": item["title"],
        "type": item["type"],
        "status": item.get("status", "open"),
    }
    if item.get("parent"):
        record["parent"] = item["parent"]
    if item.get("waiting_for"):
        record["waiting_for"] = item["waiting_for"]
    if item.get("someday"):
        record["someday"] = item["someday"]
    if item.get("area"):
        record["area"] = item["area"]
    if item.get("created_at"):
        record["created_at"] = item["created_at"]
        flag = age_flag(item["created_at"])
        if flag:
            record["age_flag"] = flag
    brief = item.get("brief") or {}
    # `badly` rides here or the review's falsifier pass is inert — the skill
    # tells the reviewer to check work against the falsifier, and this record
    # is the only thing the verification subagents see. Exactly how `how` was
    # lost on the first big run (0 of 650 items carried it); add new brief
    # subfields to this tuple when they land.
    for field in ("why", "how", "what", "done", "badly"):
        if brief.get(field):
            record[field] = brief[field]
    return record


RECENT_DONES_CAP = 10


def done_records(
    done_items: list[dict], cap: int | None = RECENT_DONES_CAP
) -> tuple[list[dict], int]:
    """Shape recent-done items: newest first, capped, with the TRUE total.

    The cap keeps busy boards from flooding the output; the count states the
    remainder so a truncated list can't read as complete (no silent caps).

    `cap=None` lifts it — what `--full-dones` passes. The cap is right for the
    pyramid's "recent wins" lines and wrong for the queue-line annotation join,
    which needs every close in the window to match a line against its card: on
    hot boards (aboyeur 30, mise 93 dones in 30 days) the cap hid exactly the
    closes the annotation was looking for, forcing per-board `bon show`
    round-trips (bon-libito, from the 2026-08-30 lane ceremony).
    """
    recs = []
    for i in sorted(done_items, key=lambda x: x.get("done_at") or "", reverse=True):
        r = {"id": i["id"], "title": i["title"]}
        if i.get("type"):
            r["type"] = i["type"]
        if i.get("done_at"):
            r["done_at"] = i["done_at"]
        if i.get("done_note"):
            r["done_note"] = i["done_note"]
        recs.append(r)
    return (recs if cap is None else recs[:cap]), len(recs)


def git_activity(repo_path: Path, window_days: int) -> dict | None:
    """Light git signal: commit count in the window + the last commit line.

    Soft-fails to None — a board dir that isn't a git repo (or has no HEAD)
    must not break the survey.
    """
    try:
        count = subprocess.run(
            ["git", "-C", str(repo_path), "rev-list", "--count",
             f"--since={window_days}.days", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if count.returncode != 0:
            return None
        out = {"commits_window": int(count.stdout.strip() or 0)}
        last = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%cs %s"],
            capture_output=True, text=True, timeout=5,
        )
        if last.returncode == 0 and last.stdout.strip():
            out["last_commit"] = last.stdout.strip()
        return out
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def repo_entry(label: str, open_items: list[dict], **extra) -> dict:
    """Build one repo group for the output JSON.

    Outcomes carry `open_child_count` — the number of OPEN children in the same
    board — so a verifier (and the skill's outcome-rollup) can see at a glance
    which outcomes would strand children if closed (the kegewe trap). Parent
    links are within-prefix, so counting over this board's open items is exact.
    """
    open_child_count: dict[str, int] = {}
    for i in open_items:
        parent = i.get("parent")
        if parent:
            open_child_count[parent] = open_child_count.get(parent, 0) + 1

    outcomes = []
    for i in open_items:
        if i["type"] != "outcome":
            continue
        rec = item_record(i)
        n = open_child_count.get(i["id"], 0)
        if n:
            rec["open_child_count"] = n
        outcomes.append(rec)

    entry = {
        "repo": label,
        "open_count": len(open_items),
        "outcomes": outcomes,
        "actions": [item_record(i) for i in open_items if i["type"] == "action"],
    }
    entry.update(extra)
    return entry


# ---------- discovery ----------

def discover_boards(roots: list[Path]) -> list[dict]:
    """Find local .bon/ boards under the roots: {path, backend, prefix}."""
    boards = []
    seen: set[Path] = set()
    for root in roots:
        for bon_dir in sorted(root.rglob(".bon")):
            if not bon_dir.is_dir():
                continue
            real = bon_dir.resolve()
            if real in seen:
                continue
            seen.add(real)
            parts = bon_dir.parts
            if any(p.startswith(".") and p != ".bon" for p in parts):
                continue
            if "node_modules" in parts:
                continue
            boards.append({
                "bon_dir": bon_dir,
                "repo_path": bon_dir.parent,
                "root": root,
                "backend": get_backend(bon_dir),
                "prefix": get_prefix(bon_dir),
            })
    for bon_dir in EXTRA_BOARD_DIRS:
        if not bon_dir.is_dir():
            continue
        real = bon_dir.resolve()
        if real in seen:
            continue
        seen.add(real)
        boards.append({
            "bon_dir": bon_dir,
            "repo_path": bon_dir.parent,
            "root": bon_dir.parent.parent,
            "backend": get_backend(bon_dir),
            "prefix": get_prefix(bon_dir),
        })
    return boards


def repo_label(repo_path: Path, root: Path) -> str:
    """Derive a human-readable repo label relative to its scan root."""
    try:
        label = str(repo_path.relative_to(root))
    except ValueError:
        return repo_path.name
    return root.name if label == "." else label


def _norm_origin(url: str | None) -> str | None:
    """Normalise a git remote URL to host/owner/repo for identity comparison."""
    if not url:
        return None
    u = url.strip().lower().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    if u.startswith("git@"):
        return u[4:].replace(":", "/", 1)
    u = u.split("://", 1)[-1]
    if "@" in u.split("/", 1)[0]:
        u = u.split("@", 1)[1]
    return u


def board_origin(repo_path: Path) -> str | None:
    """Normalised origin URL of the board's repo (None: no repo / no remote)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return _norm_origin(r.stdout.strip())


def detect_duplicate_prefixes(
    boards: list[dict],
    repos_map: dict[str, dict],
    origin_resolver=None,
) -> list[dict]:
    """Boards sharing a prefix without sharing an origin are squatters (bon-kafono).

    Two layers, so the check doesn't depend on the rightful owner being cloned
    here: (1) local boards grouped by prefix — more than one distinct origin
    flags the group (same-origin clones, e.g. a marketplace cache checkout of
    the same repo, are the estate's normal shape and exempt); (2) a JSONL board
    whose prefix carries a repos-table row pointing at a different origin — the
    shared-DB owner needn't be cloned locally to be squatted on. A Dolt board
    whose mapping origin drifted is a stale registration, not a squat, and is
    deliberately not flagged here. A board with no origin remote counts as its
    own identity: fail-visible beats a silent merge.
    """
    resolve = origin_resolver or board_origin
    by_prefix: dict[str, list[dict]] = {}
    for b in boards:
        if b["prefix"]:
            by_prefix.setdefault(b["prefix"], []).append(b)

    findings = []
    for prefix, group in sorted(by_prefix.items()):
        mapping = repos_map.get(prefix)
        mapped_origin = _norm_origin(mapping.get("origin_url")) if mapping else None
        needs_origins = len(group) > 1 or (
            mapped_origin and any(b["backend"] != "dolt" for b in group)
        )
        if not needs_origins:
            continue
        entries = [
            {
                "local_path": str(b["repo_path"]),
                "backend": b["backend"],
                "origin": resolve(b["repo_path"]),
            }
            for b in group
        ]
        identities = {e["origin"] or e["local_path"] for e in entries}
        jsonl_squat = mapped_origin and any(
            e["backend"] != "dolt" and e["origin"] != mapped_origin
            for e in entries
        )
        if len(identities) > 1 or jsonl_squat:
            finding = {"prefix": prefix, "boards": entries}
            if mapping:
                finding["repos_table"] = {
                    "repo_name": mapping.get("repo_name"),
                    "origin_url": mapping.get("origin_url"),
                }
            findings.append(finding)
    return findings


# Boards at fixed locations the walk can't reach: the walk-roots filter skips
# hidden directories (and ~/.claude is one), so probe these directly — bounded,
# and immune to the phantom boards a recursive walk of plugins/marketplaces/
# clones would surface.
EXTRA_BOARD_DIRS = [Path.home() / ".claude" / ".bon"]


def default_roots() -> list[Path]:
    """Existing scan roots, deduped by realpath (Mac's ~/Repos == ~/repos)."""
    candidates = [Path.home() / "repos", Path.home() / "Repos", Path.home() / "notes"]
    seen, roots = set(), []
    for c in candidates:
        if c.is_dir():
            rp = c.resolve()
            if rp not in seen:
                seen.add(rp)
                roots.append(rp)
    return roots


# ---------- survey ----------

def survey(
    roots: list[Path],
    repo_filter: list[str] | None = None,
    window_days: int = 30,
    job_filter: list[str] | None = None,
    full_dones: bool = False,
) -> dict:
    """Hybrid estate survey. Returns the full output document."""
    boards = discover_boards(roots)
    dones_cap = None if full_dones else RECENT_DONES_CAP
    local_dolt_by_prefix = {
        b["prefix"]: b for b in boards if b["backend"] == "dolt" and b["prefix"]
    }
    done_cutoff = (
        datetime.now(timezone.utc) - timedelta(days=window_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    dolt_mode = "global"
    dolt_items: dict[str, list[dict]] = {}
    dolt_dones: dict[str, list[dict]] = {}
    repos_map: dict[str, dict] = {}
    try:
        dolt_items, dolt_dones, repos_map = query_dolt_global(done_cutoff)
    except Exception as e:
        dolt_mode = "unreachable"
        print(
            f"WARNING: Dolt server unreachable ({e}).\n"
            f"Falling back to filesystem survey: repos not cloned under "
            f"{', '.join(str(r) for r in roots)} are MISSING from this output, "
            f"and local Dolt-backed boards will also read empty while the "
            f"server is down — this output is effectively JSONL boards only.",
            file=sys.stderr,
        )

    results = []
    unmapped = []
    seen_ids: set[str] = set()

    if dolt_mode == "global":
        # Primary index: every Dolt board in the estate, cloned here or not.
        # Iterate the union of open and recently-done prefixes: a board whose
        # work all closed this window has no open items but IS a recent win.
        all_prefixes = sorted(set(dolt_items) | set(dolt_dones))
        for prefix in all_prefixes:
            items = dolt_items.get(prefix, [])
            open_items = [i for i in items if i["id"] not in seen_ids]
            seen_ids.update(i["id"] for i in open_items)
            recent, recent_total = done_records(
                dolt_dones.get(prefix, []), cap=dones_cap
            )
            if not open_items and not recent:
                continue
            mapping = repos_map.get(prefix)
            local = local_dolt_by_prefix.get(prefix)
            if mapping:
                label = mapping["repo_name"]
            else:
                label = f"{prefix} (unmapped)"
                unmapped.append(prefix)
            extra = {
                "prefix": prefix,
                "backend": "dolt",
                "recent_dones": recent,
                "recent_done_count": recent_total,
            }
            if mapping and mapping.get("job"):
                extra["job"] = mapping["job"]
            if mapping and mapping.get("origin_url"):
                extra["origin_url"] = mapping["origin_url"]
            if local:
                extra["local_path"] = str(local["repo_path"])
            else:
                extra["not_cloned_here"] = True
            results.append(repo_entry(label, open_items, **extra))

    # Straggler sweep: JSONL boards only (Dolt boards arrived via the global
    # query). In fallback mode, local Dolt boards are read via the CLI so the
    # survey still covers everything visible from this machine.
    for board in boards:
        if board["backend"] == "dolt":
            if dolt_mode == "global":
                continue
            items = load_items_dolt_via_cli(board["repo_path"])
        else:
            items_path = board["bon_dir"] / "items.jsonl"
            items = load_items_jsonl(items_path) if items_path.exists() else []
        open_items = [
            i for i in items
            if i.get("status") == "open" and i["id"] not in seen_ids
        ]
        seen_ids.update(i["id"] for i in open_items)
        recent, recent_total = done_records(
            [
                i for i in items
                if i.get("status") == "done"
                and (i.get("done_at") or "") >= done_cutoff
            ],
            cap=dones_cap,
        )
        if not open_items and not recent:
            continue
        label = repo_label(board["repo_path"], board["root"])
        extra = {
            "prefix": board["prefix"],
            "backend": board["backend"],
            "local_path": str(board["repo_path"]),
            "recent_dones": recent,
            "recent_done_count": recent_total,
        }
        job = get_job(board["bon_dir"])
        if job:
            extra["job"] = job
        results.append(repo_entry(label, open_items, **extra))

    if repo_filter:
        results = apply_repo_filter(results, repo_filter)

    if job_filter:
        results = apply_job_filter(
            results, job_filter, report_drops=bool(repo_filter)
        )

    # Light git signal for every board with a clone here — the pyramid's
    # "recent wins" line wants motion, and board writes alone under-report it.
    for r in results:
        if r.get("local_path"):
            g = git_activity(Path(r["local_path"]), window_days)
            if g:
                r["git"] = g

    results.sort(key=lambda r: r["open_count"], reverse=True)

    # Visibility is split by backend. Dolt boards come from the shared database,
    # so they're visible from ANY machine. JSONL boards are only seen when their
    # repo is cloned under the scan roots — so the JSONL total is machine- and
    # clone-dependent, and the headline count jumps when clones appear (the
    # 491→650 overnight move on 2026-07-08 was purely tube gaining JSONL clones,
    # not new work). Annotate it so the next run reads a jump correctly.
    dolt_open = sum(r["open_count"] for r in results if r.get("backend") == "dolt")
    jsonl_open = sum(r["open_count"] for r in results if r.get("backend") != "dolt")
    visibility_note = (
        f"{dolt_open} open on Dolt boards (visible from any machine — shared DB is "
        f"the index); {jsonl_open} open on JSONL boards (visible ONLY where cloned — "
        f"this run saw clones under {', '.join(str(r) for r in roots)}). The JSONL "
        f"total changes per machine; a headline jump between runs is usually clones "
        f"appearing, not work created."
    )

    return {
        "roots": [str(r) for r in roots],
        "dolt": dolt_mode,
        "window_days": window_days,
        "unmapped_prefixes": sorted(unmapped),
        "duplicate_prefixes": detect_duplicate_prefixes(boards, repos_map),
        "jobs_unassigned": sorted(
            r["repo"] for r in results if not r.get("job")
        ),
        "total_open": sum(r["open_count"] for r in results),
        "total_recent_dones": sum(r.get("recent_done_count", 0) for r in results),
        "dolt_open": dolt_open,
        "jsonl_open": jsonl_open,
        "visibility_note": visibility_note,
        "repos_reported": len(results),
        "repos": results,
    }


def flag_values(argv: list[str], flag: str) -> list[str] | None:
    """Values following `flag` up to the next `--option`, or None if absent.

    An empty list is a real answer here, not a shrug — `--repos --roots ~/x`
    means the caller asked for a filter and named nothing. Callers must
    distinguish it from None; `require_values` is the guard.
    """
    if flag not in argv:
        return None
    idx = argv.index(flag)
    vals = []
    for a in argv[idx + 1:]:
        if a.startswith("--"):
            break
        vals.append(a)
    return vals


def require_values(vals: list[str] | None, flag: str) -> list[str] | None:
    """Refuse an empty flag rather than letting it read as "not given".

    `--repos` with no values used to yield [], which the filter check treated
    as no-filter — the survey silently widened to the whole estate while the
    caller believed it was scoped (bon-libito). A scope flag that widens on a
    typo is the worst shape available: the output looks like a complete answer.
    """
    if vals is not None and not vals:
        print(
            f"{flag} was given with no values — refusing rather than guessing. "
            f"An empty {flag} used to widen the survey to the whole estate "
            f"while looking scoped. Name at least one value, or drop the flag.",
            file=sys.stderr,
        )
        sys.exit(2)
    return vals


def match_repo(label: str, value: str) -> bool:
    """Does `value` name this repo? Whole label, or whole final path segment.

    Labels are heterogeneous — bare (`bon`, `trousse`) and owner-bucketed
    (`spm1001/sonner`, `itv/mit-kg`) — so bare-name filtering has to keep
    working; `--repos sonner` must still find `spm1001/sonner`. What it must
    NOT do is the old substring match, under which `--repos passe` silently
    swept in `spm1001/passe-partout` and `--repos trousse` swept in
    `spm1001/trousse-personal`.
    """
    return value == label or value == label.rsplit("/", 1)[-1]


def apply_repo_filter(results: list[dict], repo_filter: list[str]) -> list[dict]:
    """Filter by repo label, reporting every narrowing and every miss.

    Two loud paths, because the danger here is a quiet answer of the wrong
    size (bon-libito, and the reason the whole card exists):

    * a value naming no board EXITS — with the substring near-misses listed,
      so a caller who relied on the old semantics is told exactly what to type;
    * a value that matches but leaves substring near-misses behind SAYS SO, so
      a narrowing relative to the old behaviour can never pass unnoticed.
    """
    labels = [r["repo"] for r in results]
    # Near-misses are computed against the union of ALL values' hits, not one
    # value's. `--repos passe passe-partout` otherwise reported
    # spm1001/passe-partout as excluded while the second value was pulling it
    # in — a loud channel that lies is worse than a quiet one, because the
    # whole design rests on believing it.
    per_value = {v: [l for l in labels if match_repo(l, v)] for v in repo_filter}
    all_hits = {l for hits in per_value.values() for l in hits}

    kept: list[str] = []
    misses: list[str] = []
    notes: list[str] = []

    for value in repo_filter:
        hits = per_value[value]
        near = [l for l in labels if value in l and l not in all_hits]
        if not hits:
            misses.append(
                f"  {value!r} matched no board"
                + (f" — did you mean: {', '.join(sorted(near))}?" if near else "")
            )
            continue
        kept.extend(hits)
        if near:
            notes.append(
                f"  {value!r} → {', '.join(sorted(hits))} "
                f"(NOT matched, though they contain {value!r}: "
                f"{', '.join(sorted(near))} — pass the full label to include them)"
            )

    if misses:
        print(
            "--repos matched nothing for:\n" + "\n".join(misses)
            + "\n\nMatching is whole label or whole final path segment "
              "(so `sonner` finds `spm1001/sonner`), NOT substring.",
            file=sys.stderr,
        )
        sys.exit(2)

    if notes:
        print("--repos narrowed:\n" + "\n".join(notes), file=sys.stderr)

    keep = set(kept)
    return [r for r in results if r["repo"] in keep]


def apply_job_filter(
    results: list[dict], job_filter: list[str], report_drops: bool = False
) -> list[dict]:
    """Filter by jobs-group slug — the dial the skill text already described.

    Jobs were readable in the output but not selectable, so the review skill's
    "scope by jobs group" position documented a workaround (run the full survey,
    narrow the later phases by eye) rather than a mechanism. Exact slug match:
    slugs are curated by `bon register --job` / `.bon/job`, so a near-miss is a
    typo, not a shorthand — and an unknown slug exits naming the live set rather
    than returning a confidently empty survey.

    `report_drops` is set when a repo filter ran first, and it exists because
    composing the two filters reopened the exact hole the card was closing:
    `--repos bon notes --job batterie` returned only `bon`, exit 0, silent —
    a board the caller had named by hand, matched by `--repos`, dropped here
    with no signal (found by this card's essayeur, 2026-08-31). Naming a board
    and then discarding it needs to be said out loud.
    """
    known = sorted({r["job"] for r in results if r.get("job")})
    unknown = [j for j in job_filter if j not in known]
    if unknown:
        print(
            f"--job matched no board for: {', '.join(repr(j) for j in unknown)}\n"
            f"Jobs assigned on this run: "
            f"{', '.join(known) if known else '(none — see jobs_unassigned)'}",
            file=sys.stderr,
        )
        sys.exit(2)

    wanted = set(job_filter)
    kept = [r for r in results if r.get("job") in wanted]

    if report_drops:
        dropped = [r for r in results if r.get("job") not in wanted]
        if dropped:
            named = ", ".join(
                f"{r['repo']} (job={r['job']})" if r.get("job")
                else f"{r['repo']} (no job assigned)"
                for r in sorted(dropped, key=lambda r: r["repo"])
            )
            print(
                f"--job further narrowed what --repos matched — "
                f"{len(dropped)} board(s) dropped: {named}",
                file=sys.stderr,
            )

    return kept


# Every option this script understands, and HOW MANY values it takes:
# 0 = bare switch, 1 = exactly one, None = one or more.
#
# The arity is the load-bearing part, not decoration. A boolean "takes values"
# left `--repos bon --window-days 7 notes` accepting `notes` as belonging to
# `--window-days`, which reads only argv[idx+1) — so a scope value the caller
# typed was dropped at exit 0 with empty stderr, which is this card's fault
# reappearing inside the guard built to end it (found by the post-repair
# essayeur, 2026-08-31).
KNOWN_FLAGS = {
    "--roots": None,
    "--repos": None,
    "--job": None,
    "--window-days": 1,
    "--full-dones": 0,
}


def reject_unknown_argv(argv: list[str]) -> None:
    """Refuse any token the parser does not understand.

    The parse reads each flag by `argv.index`, so anything it fails to
    recognise is silently ignored — and an ignored SCOPE flag is the original
    bug wearing a different hat. Measured 2026-08-31 against the first version
    of this hardening: `--repos=bon`, the ordinary GNU spelling, surveyed all
    52 boards and 864 items at exit 0 with nothing on stderr, because the
    token `--repos=bon` is simply not the token `--repos`. `--repo`, `--jobs`
    and a repeated `--repos` all failed the same way.

    So the guard is the parse itself: every token is either a known option or
    a value belonging to the option before it, and anything else stops the run.
    The empty-value check next door is one door; this is the corridor.
    """
    seen: set[str] = set()
    current: str | None = None
    taken = 0
    known = ", ".join(sorted(KNOWN_FLAGS))

    for tok in argv:
        if tok.startswith("--"):
            if tok not in KNOWN_FLAGS:
                hint = ""
                head = tok.split("=", 1)[0]
                if "=" in tok and head in KNOWN_FLAGS:
                    hint = (
                        f"\nValues follow a space, not an '=': "
                        f"`{head} {tok.split('=', 1)[1]}`"
                    )
                print(
                    f"Unrecognised option {tok!r} — refusing rather than "
                    f"ignoring it, because an ignored scope flag surveys the "
                    f"whole estate while looking scoped.\n"
                    f"Known options: {known}{hint}",
                    file=sys.stderr,
                )
                sys.exit(2)
            if tok in seen:
                print(
                    f"{tok} given more than once — only the first would have "
                    f"been read. Pass all its values after a single {tok}.",
                    file=sys.stderr,
                )
                sys.exit(2)
            seen.add(tok)
            current = tok if KNOWN_FLAGS[tok] != 0 else None
            taken = 0
        elif current is None:
            print(
                f"Unexpected argument {tok!r} — it follows no option that "
                f"takes values.\nKnown options: {known}",
                file=sys.stderr,
            )
            sys.exit(2)
        else:
            taken += 1
            arity = KNOWN_FLAGS[current]
            if arity is not None and taken > arity:
                print(
                    f"{current} takes {arity} value(s); {tok!r} is one too "
                    f"many. It would have been read by nothing at all — which "
                    f"is how a scope value gets dropped in silence.",
                    file=sys.stderr,
                )
                sys.exit(2)


def main():
    argv = sys.argv[1:]
    reject_unknown_argv(argv)

    # Root priority: --roots flag > REPOS_DIR env > defaults
    root_vals = require_values(flag_values(argv, "--roots"), "--roots")
    if root_vals is not None:
        roots = [Path(v).expanduser() for v in root_vals]
    elif os.environ.get("REPOS_DIR"):
        roots = [Path(os.environ["REPOS_DIR"])]
    else:
        roots = default_roots()

    repo_filter = require_values(flag_values(argv, "--repos"), "--repos")
    job_filter = require_values(flag_values(argv, "--job"), "--job")
    full_dones = "--full-dones" in argv

    window_days = 30
    if "--window-days" in argv:
        idx = argv.index("--window-days")
        try:
            window_days = int(argv[idx + 1])
        except (IndexError, ValueError):
            print("--window-days needs an integer argument", file=sys.stderr)
            sys.exit(2)

    output = survey(
        roots,
        repo_filter,
        window_days=window_days,
        job_filter=job_filter,
        full_dones=full_dones,
    )

    if output["unmapped_prefixes"]:
        print(
            f"Note: unmapped prefixes (no repos-table row — run `bon register` "
            f"from a clone, or triage as orphaned): "
            f"{', '.join(output['unmapped_prefixes'])}",
            file=sys.stderr,
        )

    if output["duplicate_prefixes"]:
        dupes = "; ".join(
            f"{d['prefix']}: " + ", ".join(
                f"{b['local_path']} ({b['backend']})" for b in d["boards"]
            )
            for d in output["duplicate_prefixes"]
        )
        print(
            f"WARNING: duplicate prefixes — two boards minting the same "
            f"id-space (re-prefix the squatter; see duplicate_prefixes in "
            f"the JSON): {dupes}",
            file=sys.stderr,
        )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
