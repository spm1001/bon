#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Corrected maintenance pass.

The first pass keyed on `spm1001/bon/`, which is the repo's CURRENT path. It has
lived at ~/Repos/bon and ~/Repos/batterie/bon too, so the detector was blind to
every pre-move session and reported maintenance as starting in June 2026. That is
the instrument's limit read as a property of the subject.

Fix: key on the repo's SHAPE (a /bon/ dir containing bon's own subdirs), not its
location. Control printed below: the set of distinct repo roots matched, so a
wrong root shows up rather than silently inflating the count.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"

# Any bon clone, any location. Excludes .bon/ (board data = usage, not maintenance).
MAINT = re.compile(
    r"(?P<root>(?:/[^/\s\"]+)*/bon)/"
    r"(?:src/|tests/|skills/|scripts/|hooks/|docs/|fixtures/|\.claude-plugin/"
    r"|CLAUDE\.md|README\.md|pyproject\.toml)"
)
TS = re.compile(rb'"timestamp":"(\d{4}-\d{2}-\d{2})')

sessions, roots, by_month, paths = {}, Counter(), Counter(), Counter()
files = sorted(PROJECTS.glob("*/*.jsonl"))

for n, f in enumerate(files, 1):
    if n % 1000 == 0:
        print(f"  ...{n}/{len(files)}", file=sys.stderr, flush=True)
    hits, day = set(), None
    with f.open("rb") as fh:
        for line in fh:
            if day is None:
                m = TS.search(line)
                if m:
                    day = m.group(1).decode()
            if b"/bon/" not in line:
                continue
            if b'"name":"Edit"' not in line and b'"name":"Write"' not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            for blk in (d.get("message") or {}).get("content") or []:
                if not isinstance(blk, dict) or blk.get("name") not in ("Edit", "Write"):
                    continue
                fp = (blk.get("input") or {}).get("file_path") or ""
                m2 = MAINT.search(fp)
                if not m2:
                    continue
                root = m2.group("root")
                rel = fp[len(root) + 1:]
                hits.add(rel)
                roots[root] += 1
    if hits:
        sessions[str(f)] = dict(proj=f.parent.name, day=day, files=sorted(hits))
        if day:
            by_month[day[:7]] += 1
        for h in hits:
            paths[h.split("/")[0] if "/" in h else h] += 1

print("\n=== CONTROL: distinct repo roots matched (a wrong root would show here) ===")
for r, c in roots.most_common():
    print(f"  {c:6d} edits   {r}")
print(f"\n=== MAINTENANCE SESSIONS (corrected): {len(sessions)} ===")
print("\nper month:")
for m in sorted(by_month):
    print(f"  {m}  {by_month[m]:4d}")
print("\ntop areas touched:")
for p, c in paths.most_common(12):
    print(f"  {c:5d} sessions  {p}")
json.dump(sessions, open("/tmp/bon-maint.json", "w"))
