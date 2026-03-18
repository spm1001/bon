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
# Exits silently (exit 0) if no .bon/ or .arc/ directory — graceful no-op.

set -euo pipefail

# Check .bon/ first, fall back to .arc/ (transition)
if [ -f ".bon/items.jsonl" ]; then
    ITEMS=".bon/items.jsonl"
elif [ -f ".arc/items.jsonl" ]; then
    ITEMS=".arc/items.jsonl"
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
            items.append(json.loads(line))

mode = "$MODE"

def by_order(item):
    return item.get("order", 999)

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
    for o in outcomes:
        mark = "\u2713" if o.get("status") == "done" else "\u25cb"
        print(f'{mark} {o["title"]} ({o["id"]})')
        for idx, a in enumerate(children.get(o["id"], []), 1):
            am = "\u2713" if a.get("status") == "done" else "\u25cb"
            print(f'  {idx}. {am} {a["title"]} ({a["id"]})')
        print()

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
    for o in outcomes:
        print(f'\u25cb {o["title"]} ({o["id"]})')
        for idx, a in enumerate(children.get(o["id"], []), 1):
            print(f'  {idx}. \u25cb {a["title"]} ({a["id"]})')
        print()

elif mode == "current":
    # Active tactical steps
    for item in items:
        if item.get("tactical") and item.get("status") == "open":
            t = item["tactical"]
            print(f'Working: {item["title"]} ({item["id"]})')
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
