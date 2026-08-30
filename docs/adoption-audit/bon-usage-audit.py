#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Measure bon USE vs bon MAINTENANCE across the whole CC session corpus.

The question: are we mostly working ON bon, or mostly using it? Sameer's claim is
the latter. This counts the denominator properly instead of eyeballing one repo.

Precision discipline (context/verification.md, "the lying number"): a regex over
transcripts mints candidates, not measurements. So:
  - bon invocations are read ONLY from Bash tool_use `command` fields, never prose
  - a captured verb must be in KNOWN_VERBS to count
  - every count prints examples beside it for hand-reading
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"

# \bbon won't match inside "carbon"/"ribbon" — word boundary needs a non-word char
BON_CMD = re.compile(r"\bbon\s+(--version|--help|[a-z][a-z-]{1,12})")
TS = re.compile(rb'"timestamp":"(\d{4}-\d{2}-\d{2})')

KNOWN_VERBS = {
    "init", "list", "show", "new", "done", "wait", "unwait", "work", "step",
    "edit", "convert", "move", "status", "archive", "doctor", "migrate",
    "register", "reopen", "someday", "unsomeday", "ready", "--version", "--help",
}
# Paths that mean "maintaining the tool". NOTE .bon/ and handoffs/ are both
# deliberately absent — editing understanding.md or a handoff is USING the
# rite, not building it. (handoffs/ sat under .bon/ until bon-sedoze; it is
# excluded now by simply not being listed, which is the same outcome.)
SRC_DIRS = ("src/", "tests/", "skills/", "scripts/", "hooks/", "docs/",
            "fixtures/", "CLAUDE.md", "README.md", "pyproject.toml",
            ".claude-plugin/")

rows = {}
files = sorted(PROJECTS.glob("*/*.jsonl"))
total = len(files)

for n, f in enumerate(files, 1):
    if n % 500 == 0:
        print(f"  ...{n}/{total}", file=sys.stderr, flush=True)
    proj = f.parent.name
    verbs = Counter()
    cmd_examples = []
    edited_src = set()
    turns = 0
    day = None
    try:
        with f.open("rb") as fh:
            for line in fh:
                if b'"type":"assistant"' in line:
                    turns += 1
                if day is None:
                    m = TS.search(line)
                    if m:
                        day = m.group(1).decode()
                # --- bon CLI invocations: Bash commands only ---
                if b"bon" in line and b'"name":"Bash"' in line:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    for blk in (d.get("message") or {}).get("content") or []:
                        if not isinstance(blk, dict) or blk.get("name") != "Bash":
                            continue
                        cmd = (blk.get("input") or {}).get("command") or ""
                        found = [v for v in BON_CMD.findall(cmd) if v in KNOWN_VERBS]
                        if found:
                            verbs.update(found)
                            if len(cmd_examples) < 3:
                                cmd_examples.append(cmd.strip().replace("\n", " ⏎ ")[:150])
                # --- edits to bon's own source ---
                if b"spm1001/bon/" in line and (b'"name":"Edit"' in line
                                                or b'"name":"Write"' in line):
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    for blk in (d.get("message") or {}).get("content") or []:
                        if not isinstance(blk, dict) or blk.get("name") not in ("Edit", "Write"):
                            continue
                        fp = (blk.get("input") or {}).get("file_path") or ""
                        if "spm1001/bon/" not in fp:
                            continue
                        rel = fp.split("spm1001/bon/", 1)[1]
                        if rel.startswith(".bon/"):
                            continue
                        if rel.startswith(SRC_DIRS):
                            edited_src.add(rel)
    except Exception as e:
        print(f"  !! {f.name}: {e}", file=sys.stderr)
        continue
    rows[str(f)] = dict(proj=proj, verbs=verbs, turns=turns, day=day,
                        examples=cmd_examples, edited_src=edited_src)

json.dump(
    {k: dict(proj=v["proj"], verbs=dict(v["verbs"]), turns=v["turns"], day=v["day"],
             examples=v["examples"], edited_src=sorted(v["edited_src"]))
     for k, v in rows.items()},
    open("/tmp/bon-usage-raw.json", "w"),
)
print(f"done: {len(rows)} sessions scanned -> /tmp/bon-usage-raw.json", file=sys.stderr)
