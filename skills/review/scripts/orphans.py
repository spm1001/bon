#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Citation cross-check: commits vs the board (bon-nenine).

Convention: a commit doing work tracked by a bon cites it — trailing
'(bon-ID)' in the subject or body. This pass reads the citations back and
reports the mismatches worth a review verdict:

  CITED-BUT-OPEN  commits cite an item that is still open. Work moved; the
                  item may want closing (beads' 'bd orphans' direction).
  UNKNOWN-ID      a citation with this board's prefix naming no known item —
                  a typo, or an archived item (labelled when resolvable).
  CROSS-BOARD     citations whose prefix isn't this board's. Informational;
                  unverified against the other board.
  Coverage        commits citing anything / commits scanned — adoption
                  telemetry for the convention itself.

Deliberately NOT reported: open items never cited. On a backlog most open
items simply haven't started, so that direction is pure noise (decided at
the item's birth, bon-nenine). Only modern six-letter IDs are matched —
legacy short IDs (mise-qa6) predate the convention by definition.

Reads the board via the bon CLI (backend-agnostic: JSONL and Dolt). A board
read failure is a loud exit, never an empty-looking clean report. Override
the CLI with BON_CMD (e.g. "python3 -m bon.cli") for tests.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Trailing-parens citation, modern IDs only: lowercase alnum prefix,
# dash, six letters (mixed case allowed — legacy bon-huHida shape).
CITATION_RE = re.compile(r"\(([a-z][a-z0-9]*-[A-Za-z]{6})\)")
FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"


def fail(msg: str) -> None:
    print(f"orphans: {msg}", file=sys.stderr)
    sys.exit(2)


def bon_cmd() -> list:
    return shlex.split(os.environ.get("BON_CMD", "bon"))


def load_board(repo: Path) -> dict:
    """All items by id, parked included. Loud on any failure."""
    items = {}
    for flags in (["--all"], ["--someday"]):
        proc = subprocess.run(
            bon_cmd() + ["list", *flags, "--jsonl"],
            capture_output=True, text=True, cwd=repo,
        )
        if proc.returncode != 0:
            fail(
                f"board read failed (bon list {' '.join(flags)} --jsonl): "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                item = json.loads(line)
                items[item["id"]] = item
    return items


def load_archive_ids(repo: Path) -> set:
    """Archived IDs, best-effort: raw file on JSONL boards, empty on Dolt."""
    archive = repo / ".bon" / "archive.jsonl"
    ids = set()
    if archive.is_file():
        for line in archive.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    ids.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return ids


def scan_commits(repo: Path, since: str) -> list:
    cmd = ["git", "-C", str(repo), "log",
           f"--format=%H{FIELD_SEP}%ad{FIELD_SEP}%B{RECORD_SEP}",
           "--date=short"]
    if since:
        cmd.append(f"--since={since}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        fail(f"git log failed: {proc.stderr.strip()}")
    commits = []
    for record in proc.stdout.split(RECORD_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        sha, date, body = record.split(FIELD_SEP, 2)
        commits.append({
            "sha": sha.strip(), "date": date,
            "subject": body.splitlines()[0] if body.splitlines() else "",
            "cited": sorted(set(CITATION_RE.findall(body))),
        })
    return commits


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="path inside the repo (default: cwd)")
    ap.add_argument("--since", default="", help="git --since expression (default: full history)")
    args = ap.parse_args()

    top = subprocess.run(
        ["git", "-C", args.repo, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True,
    )
    if top.returncode != 0:
        fail(f"not a git repo: {args.repo}")
    repo = Path(top.stdout.strip())

    items = load_board(repo)
    if not items:
        fail(f"board at {repo} returned no items — empty board or wrong cwd; not reporting a clean pass on nothing")
    prefixes = {i.rsplit("-", 1)[0] for i in items}
    archive_ids = load_archive_ids(repo)
    commits = scan_commits(repo, args.since)

    per_id = defaultdict(list)          # cited id -> commits, newest first (git log order)
    citing_commits = 0
    for c in commits:
        if c["cited"]:
            citing_commits += 1
        for cid in c["cited"]:
            per_id[cid].append(c)

    cited_open, cited_done, unknown = [], [], []
    cross = defaultdict(set)            # foreign prefix -> distinct ids
    for cid, cs in sorted(per_id.items()):
        pfx = cid.rsplit("-", 1)[0]
        if pfx not in prefixes:
            cross[pfx].add(cid)
            continue
        item = items.get(cid)
        if item is None:
            unknown.append((cid, cs, cid in archive_ids))
        elif item.get("status") == "open":
            cited_open.append((cid, item, cs))
        else:
            cited_done.append(cid)

    window = f" since {args.since}" if args.since else ""
    print(f"Orphans check — board prefix(es) {'/'.join(sorted(prefixes))} @ {repo}")
    print(f"{len(commits)} commits scanned{window}, {citing_commits} citing; "
          f"{len(cited_done)} cited items already closed (healthy)\n")

    if cited_open:
        print("CITED-BUT-OPEN — work moved; wants a verdict:")
        for cid, item, cs in cited_open:
            last = cs[0]
            print(f"  {cid}  \"{item.get('title', '')}\" — {len(cs)} commit(s), "
                  f"last {last['date']} {last['sha'][:7]} \"{last['subject']}\"")
    else:
        print("CITED-BUT-OPEN: none")

    if unknown:
        print("\nUNKNOWN-ID — typo, or archived:")
        for cid, cs, archived in unknown:
            label = "in archive" if archived else "not on board or in readable archive"
            print(f"  {cid}  cited {len(cs)}x, last {cs[0]['date']} {cs[0]['sha'][:7]} — {label}")
    else:
        print("\nUNKNOWN-ID: none")

    if cross:
        print("\nCROSS-BOARD (unverified here, aggregated by prefix):")
        for pfx, ids in sorted(cross.items()):
            sample = f": {', '.join(sorted(ids))}" if len(ids) <= 3 else ""
            print(f"  {pfx}-*  {len(ids)} distinct id(s){sample}")

    pct = (100 * citing_commits // len(commits)) if commits else 0
    print(f"\nCoverage: {citing_commits}/{len(commits)} commits cite a bon ({pct}%)")


if __name__ == "__main__":
    main()
