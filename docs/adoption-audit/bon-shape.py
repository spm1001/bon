#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read real bon command sequences in order, from busy sessions outside bon's repo.

Counts are a hypothesis until you read what they caught (context/verification.md).
"""
import json
import re
from collections import Counter
from pathlib import Path

BON_CMD = re.compile(r"\bbon\s+(--version|--help|[a-z][a-z-]{1,12})")
KNOWN = {"init","list","show","new","done","wait","unwait","work","step","edit",
         "convert","move","status","archive","doctor","migrate","register","reopen",
         "someday","unsomeday","--version","--help"}
BON_PROJ = {"-home-modha-repos-spm1001-bon","-home-modha-Repos-batterie-bon",
            "-home-modha-Repos-bon","-Users-modha-Repos-bon",
            "-home-modha-Repos-batterie-batterie-plugins-bon"}

use = json.load(open("/tmp/bon-usage-raw.json"))
cands = sorted(
    ((sum(v["verbs"].values()), k, v) for k, v in use.items()
     if v["verbs"] and v["proj"] not in BON_PROJ),
    reverse=True,
)

# --- transition matrix: which verb follows which, across all busy sessions ---
trans = Counter()
firsts, lasts = Counter(), Counter()
for _, k, v in cands[:120]:
    seq = []
    for line in Path(k).open("rb"):
        if b"bon" not in line or b'"name":"Bash"' not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        for blk in (d.get("message") or {}).get("content") or []:
            if not isinstance(blk, dict) or blk.get("name") != "Bash":
                continue
            for verb in BON_CMD.findall((blk.get("input") or {}).get("command") or ""):
                if verb in KNOWN:
                    seq.append(verb)
    if seq:
        firsts[seq[0]] += 1
        lasts[seq[-1]] += 1
        for a, b in zip(seq, seq[1:]):
            trans[(a, b)] += 1

print("=== FIRST bon verb of a session (how sessions enter the board) ===")
t = sum(firsts.values())
for v, c in firsts.most_common(8):
    print(f"  {c:4d}  {100*c/t:5.1f}%  {v}")
print("\n=== LAST bon verb of a session (how sessions leave it) ===")
t = sum(lasts.values())
for v, c in lasts.most_common(8):
    print(f"  {c:4d}  {100*c/t:5.1f}%  {v}")
print("\n=== most common verb-to-verb transitions (the actual grammar) ===")
t = sum(trans.values())
for (a, b), c in trans.most_common(16):
    print(f"  {c:5d}  {100*c/t:5.1f}%  {a:>8} -> {b}")

print("\n=== ONE SESSION IN FULL: the busiest non-bon-repo session ===")
n, k, v = cands[0]
print(f"  repo: {v['proj']}   day: {v['day']}   bon calls: {n}   turns: {v['turns']}")
seq = []
for line in Path(k).open("rb"):
    if b"bon" not in line or b'"name":"Bash"' not in line:
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    for blk in (d.get("message") or {}).get("content") or []:
        if not isinstance(blk, dict) or blk.get("name") != "Bash":
            continue
        cmd = (blk.get("input") or {}).get("command") or ""
        vs = [x for x in BON_CMD.findall(cmd) if x in KNOWN]
        if vs:
            seq.append((vs, cmd.strip().replace("\n", " ⏎ ")[:96]))
print("  verb sequence:")
print("   ", " → ".join(x for vs, _ in seq for x in vs))
print("\n  first 12 commands verbatim:")
for vs, cmd in seq[:12]:
    print(f"    {cmd}")
