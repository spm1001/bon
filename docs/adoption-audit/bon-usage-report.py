#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Analyse /tmp/bon-usage-raw.json. Every count prints examples beside it."""
import json
from collections import Counter, defaultdict

d = json.load(open("/tmp/bon-usage-raw.json"))

# The bon repo itself, under both current and legacy casings.
BON_REPO = {"-home-modha-repos-spm1001-bon", "-home-modha-Repos-bon", "-home-modha-Repos-spm1001-bon"}

def repo_label(p):
    return p.replace("-home-modha-", "").replace("repos-spm1001-", "").replace("-", "/") or p

total = len(d)
subst = {k: v for k, v in d.items() if v["turns"] >= 3}
used = {k: v for k, v in d.items() if v["verbs"]}
used_subst = {k: v for k, v in subst.items() if v["verbs"]}
maint = {k: v for k, v in d.items() if v["edited_src"]}

print("=" * 74)
print("DENOMINATOR")
print("=" * 74)
print(f"  all session files                       {total:5d}")
print(f"  substantive (>=3 assistant turns)      {len(subst):5d}")
print(f"  trivial/aborted (<3 turns)             {total - len(subst):5d}")
print()
print("=" * 74)
print("USE vs MAINTENANCE")
print("=" * 74)
print(f"  ran >=1 bon CLI command                {len(used):5d}  ({100*len(used)/total:.0f}% of all)")
print(f"    of substantive sessions              {len(used_subst):5d}  ({100*len(used_subst)/len(subst):.0f}% of substantive)")
print(f"  edited bon's own source (maintenance)  {len(maint):5d}  ({100*len(maint)/total:.1f}% of all)")
print()
in_repo = {k: v for k, v in used.items() if v["proj"] in BON_REPO}
outside = {k: v for k, v in used.items() if v["proj"] not in BON_REPO}
print(f"  bon-using sessions INSIDE the bon repo {len(in_repo):5d}")
print(f"  bon-using sessions ELSEWHERE           {len(outside):5d}  <-- pure use")
print(f"  ratio  use-elsewhere : maintenance     {len(outside)/max(len(maint),1):.1f} : 1")
print()

print("=" * 74)
print("WHERE bon IS USED  (top 25 repos by sessions that ran bon)")
print("=" * 74)
byrepo = Counter(v["proj"] for v in used.values())
allrepo = Counter(v["proj"] for v in subst.values())
print(f"  {'repo':<38} {'bon sessions':>12} {'substantive':>12} {'share':>7}")
for proj, c in byrepo.most_common(25):
    tot = allrepo.get(proj, 0)
    share = f"{100*c/tot:.0f}%" if tot else "-"
    print(f"  {repo_label(proj)[:38]:<38} {c:>12} {tot:>12} {share:>7}")
print(f"\n  distinct repos where bon was used: {len(byrepo)}")
print()

print("=" * 74)
print("HOW bon IS USED  (verb totals; invocations, not sessions)")
print("=" * 74)
verbs_all, verbs_out = Counter(), Counter()
for v in used.values():
    verbs_all.update(v["verbs"])
for v in outside.values():
    verbs_out.update(v["verbs"])
tot_all = sum(verbs_all.values())
print(f"  {'verb':<14} {'all calls':>10} {'share':>7}   {'outside bon repo':>17} {'share':>7}")
for verb, c in verbs_all.most_common():
    o = verbs_out.get(verb, 0)
    print(f"  {verb:<14} {c:>10} {100*c/tot_all:>6.1f}%   {o:>17} "
          f"{100*o/max(sum(verbs_out.values()),1):>6.1f}%")
print(f"\n  total bon invocations: {tot_all}")
print()

print("=" * 74)
print("THE RHYTHM  (what shape does a bon-using session take?)")
print("=" * 74)
READ = {"list", "show", "status", "ready", "--version", "--help", "doctor"}
WRITE = {"new", "done", "edit", "wait", "unwait", "convert", "move", "archive",
         "reopen", "someday", "unsomeday", "register", "init", "migrate"}
TACT = {"work", "step"}
shapes = Counter()
for v in used.values():
    ks = set(v["verbs"])
    has_w, has_t, has_r = ks & WRITE, ks & TACT, ks & READ
    if has_t and has_w:
        shapes["full rhythm (read + write + tactical work/step)"] += 1
    elif has_t:
        shapes["tactical only (work/step, no board mutation)"] += 1
    elif has_w:
        shapes["capture/close (write verbs, no tactical)"] += 1
    elif has_r:
        shapes["read-only (orient, never mutate)"] += 1
for s, c in shapes.most_common():
    print(f"  {c:5d}  ({100*c/len(used):4.1f}%)  {s}")
print()
mutators = sum(c for s, c in shapes.items() if "read-only" not in s)
print(f"  sessions that MUTATED a board: {mutators} ({100*mutators/len(used):.0f}% of bon-using)")
print()

print("=" * 74)
print("TREND  (bon-using sessions per month)")
print("=" * 74)
mon_used, mon_all, mon_maint = Counter(), Counter(), Counter()
for k, v in d.items():
    if not v["day"]:
        continue
    m = v["day"][:7]
    if v["turns"] >= 3:
        mon_all[m] += 1
    if v["verbs"]:
        mon_used[m] += 1
    if v["edited_src"]:
        mon_maint[m] += 1
print(f"  {'month':<9} {'substantive':>11} {'used bon':>9} {'share':>7} {'maintained bon':>15}")
for m in sorted(mon_all):
    s = f"{100*mon_used[m]/mon_all[m]:.0f}%" if mon_all[m] else "-"
    print(f"  {m:<9} {mon_all[m]:>11} {mon_used[m]:>9} {s:>7} {mon_maint[m]:>15}")
print()

print("=" * 74)
print("HAND-READING: 20 real bon commands from sessions OUTSIDE the bon repo")
print("=" * 74)
shown = 0
for k, v in outside.items():
    for ex in v["examples"]:
        if shown >= 20:
            break
        print(f"  [{repo_label(v['proj'])[:22]:<22}] {ex[:112]}")
        shown += 1
    if shown >= 20:
        break
print()
print("=" * 74)
print("MAINTENANCE: what gets edited when we DO work on bon (top 15 paths)")
print("=" * 74)
paths = Counter()
for v in maint.values():
    for p in v["edited_src"]:
        paths[p.split("/")[0] if "/" in p else p] += 1
for p, c in paths.most_common(15):
    print(f"  {c:5d} sessions touched  {p}")
