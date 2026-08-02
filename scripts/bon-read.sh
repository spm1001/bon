#!/bin/bash
#
# bon-read.sh — fast reads from .bon/items.jsonl
# Replaces bon CLI for read-only operations in hooks and scripts.
#
# Usage:
#   bon-read.sh list          # Full hierarchy (outcomes + actions)
#   bon-read.sh ready         # Ready items only (open, not waiting)
#   bon-read.sh current       # Active tactical steps
#
# Reads from .bon/items.jsonl in current directory.
# Exits silently (exit 0) if no .bon/ directory — graceful no-op.

set -euo pipefail

# Dolt backend: fall back to bon CLI (slower but correct)
if [ -f ".bon/backend" ] && grep -q dolt ".bon/backend"; then
    MODE="${1:-}"
    if [ "$MODE" = "list" ]; then
        bon list 2>/dev/null
    elif [ "$MODE" = "ready" ]; then
        bon list --ready 2>/dev/null
    elif [ "$MODE" = "current" ]; then
        bon show --current 2>/dev/null
    else
        echo "Usage: bon-read.sh {list|ready|current}" >&2
        exit 1
    fi
    exit $?
fi

if [ -f ".bon/items.jsonl" ]; then
    ITEMS=".bon/items.jsonl"
else
    exit 0
fi

MODE="${1:-}"

python3 << PYEOF
import json, sys

items = []
with open("$ITEMS") as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass

mode = "$MODE"

def by_order(item):
    return item.get("order", 999)

# Someday/Maybe (bon-majoca): parked subtrees leave the default views.
# The someday field holds the revisit condition; children inherit at read
# time. Mirrors the CLI's queries.someday_ids — keep in step.
_flagged = {i["id"] for i in items if i.get("someday")}
_parked = {i["id"] for i in items
           if i.get("someday") or i.get("parent") in _flagged}
_n_parked = sum(1 for i in items
                if i.get("someday") and i.get("status") == "open")
if mode in ("list", "ready"):
    items = [i for i in items if i["id"] not in _parked]

if mode == "list":
    # Group actions by parent
    children = {}
    for item in items:
        p = item.get("parent")
        if p:
            children.setdefault(p, []).append(item)
    for v in children.values():
        v.sort(key=by_order)
    # Show open outcomes
    outcomes = sorted(
        [i for i in items if i.get("type") == "outcome" and i.get("status") == "open" and not i.get("parent")],
        key=by_order,
    )
    for i, o in enumerate(outcomes):
        mark = "\u2713" if o.get("status") == "done" else "\u25cb"
        kids = children.get(o["id"], [])
        if kids:
            done_n = sum(1 for a in kids if a.get("status") == "done")
            progress = f" [{done_n}\u2713/{len(kids)}]"
        else:
            progress = ""
        print(f'{mark} {o["title"]} ({o["id"]}){progress}')
        for a in kids:
            am = "\u2713" if a.get("status") == "done" else "\u25cb"
            num = a.get("order", 1)
            print(f'  {num}. {am} {a["title"]} ({a["id"]})')
        if i < len(outcomes) - 1:
            print()
    # Standalone actions (open, no parent) — the CLI's second bucket, else
    # a board whose open work is all standalone reads as empty.
    standalone = sorted(
        [it for it in items if it.get("type") == "action"
         and not it.get("parent") and it.get("status") == "open"],
        key=by_order,
    )
    if standalone:
        if outcomes:
            print()
        print("Standalone:")
        for a in standalone:
            print(f'  ○ {a["title"]} ({a["id"]})')
    if _n_parked:
        if outcomes or standalone:
            print()
        print(f"\U0001f17f️ Someday: {_n_parked} parked — bon list --someday")

elif mode == "ready":
    # Ready: open outcomes with only open, non-waiting actions
    children = {}
    for item in items:
        p = item.get("parent")
        if p and item.get("status") == "open" and not item.get("waiting_for"):
            children.setdefault(p, []).append(item)
    for v in children.values():
        v.sort(key=by_order)
    outcomes = sorted(
        [i for i in items if i.get("type") == "outcome" and i.get("status") == "open" and not i.get("parent")],
        key=by_order,
    )
    for i, o in enumerate(outcomes):
        print(f'\u25cb {o["title"]} ({o["id"]})')
        for idx, a in enumerate(children.get(o["id"], []), 1):
            print(f'  {idx}. \u25cb {a["title"]} ({a["id"]})')
        if i < len(outcomes) - 1:
            print()
    # Standalone ready actions (open, non-waiting, no parent)
    standalone = sorted(
        [it for it in items if it.get("type") == "action"
         and not it.get("parent") and it.get("status") == "open"
         and not it.get("waiting_for")],
        key=by_order,
    )
    if standalone:
        if outcomes:
            print()
        print("Standalone:")
        for a in standalone:
            print(f'  \u25cb {a["title"]} ({a["id"]})')

elif mode == "current":
    # Active tactical steps
    for item in items:
        if item.get("tactical") and item.get("status") == "open":
            t = item["tactical"]
            print(f'Working: {item["title"]} ({item["id"]})')
            how = item.get("brief", {}).get("how")
            if how:
                print(f'Approach: {how}')
            for idx, step in enumerate(t.get("steps", [])):
                current = t.get("current", 0)
                if idx < current:
                    mark = "\u2713"
                elif idx == current:
                    mark = "\u2192"
                else:
                    mark = " "
                suffix = " [current]" if idx == current else ""
                print(f'{mark} {idx + 1}. {step}{suffix}')
            break

else:
    print("Usage: bon-read.sh {list|ready|current}", file=sys.stderr)
    sys.exit(1)
PYEOF
