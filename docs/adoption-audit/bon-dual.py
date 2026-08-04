#!/usr/bin/env python3
"""Two independent instruments for 'did this session use bon', on any host.

  A) CLI:   bon <verb> parsed out of Bash tool_use command fields
  B) SKILL: attributionPlugin/attributionSkill == bon on assistant entries,
            plus Skill tool_use calls naming a bon skill

Sameer's suggestion (B) is cleaner — a first-class field, no shell parsing. But a
newer field can't see older sessions, so this also reports attributionSkill
coverage BY CC VERSION. Agreement between two instruments is the point; where they
disagree, the disagreement is the finding.

stdlib only; runs under any python3.9+. Prints a JSON blob for aggregation.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

BON_CMD = re.compile(r"\bbon\s+(--version|--help|[a-z][a-z-]{1,12})")
KNOWN = {"init", "list", "show", "new", "done", "wait", "unwait", "work", "step",
         "edit", "convert", "move", "status", "archive", "doctor", "migrate",
         "register", "reopen", "someday", "unsomeday", "--version", "--help"}
TS = re.compile(rb'"timestamp":"(\d{4}-\d{2}-\d{2})')
VER = re.compile(rb'"version":"([0-9.]+)"')

root = Path.home() / ".claude" / "projects"
out = []
files = sorted(root.glob("*/*.jsonl"))
for n, f in enumerate(files, 1):
    if n % 1000 == 0:
        print(f"  ...{n}/{len(files)}", file=sys.stderr, flush=True)
    turns = 0
    day = None
    ver = None
    verbs = Counter()
    skill_hits = 0
    skill_names = Counter()
    any_attrib = False          # did ANY entry in this file carry attributionSkill?
    try:
        with f.open("rb") as fh:
            for line in fh:
                if b'"type":"assistant"' in line:
                    turns += 1
                if day is None:
                    m = TS.search(line)
                    if m:
                        day = m.group(1).decode()
                if ver is None:
                    m = VER.search(line)
                    if m:
                        ver = m.group(1).decode()
                has_attrib = b'"attributionSkill"' in line
                if has_attrib:
                    any_attrib = True
                # --- instrument B: skill attribution + Skill tool calls ---
                if has_attrib or b'"name":"Skill"' in line:
                    try:
                        d = json.loads(line)
                    except Exception:
                        d = None
                    if d:
                        sk = d.get("attributionSkill")
                        if sk:
                            skill_names[sk] += 1
                            if (d.get("attributionPlugin") == "bon"
                                    or str(sk).startswith("bon")):
                                skill_hits += 1
                        for blk in (d.get("message") or {}).get("content") or []:
                            if isinstance(blk, dict) and blk.get("name") == "Skill":
                                s = (blk.get("input") or {}).get("skill") or ""
                                skill_names[f"call:{s}"] += 1
                                if s.startswith("bon"):
                                    skill_hits += 1
                # --- instrument A: bon CLI in Bash commands ---
                if b"bon" in line and b'"name":"Bash"' in line:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    for blk in (d.get("message") or {}).get("content") or []:
                        if not isinstance(blk, dict) or blk.get("name") != "Bash":
                            continue
                        cmd = (blk.get("input") or {}).get("command") or ""
                        for v in BON_CMD.findall(cmd):
                            if v in KNOWN:
                                verbs[v] += 1
    except Exception:
        continue
    out.append(dict(proj=f.parent.name, day=day, ver=ver, turns=turns,
                    cli=sum(verbs.values()), skill=skill_hits,
                    attrib_present=any_attrib))

print(json.dumps(out))
