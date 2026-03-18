#!/bin/bash
# Bon tactical step reminder — UserPromptSubmit hook
# Injects current tactical step into every prompt so Claude stays on track.
# Silent when: no .bon/, no active tactical, python3 not available.

command -v python3 &>/dev/null || exit 0

# Read hook stdin once (consumed on first read) and cd to session CWD
HOOK_INPUT=$(cat)
CWD=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('cwd',''))" <<< "$HOOK_INPUT" 2>/dev/null)
[ -n "$CWD" ] && cd "$CWD" 2>/dev/null

# Check .bon/ first, fall back to .arc/ during transition
if [ -f .bon/items.jsonl ]; then
    ITEMS_FILE=.bon/items.jsonl
elif [ -f .arc/items.jsonl ]; then
    ITEMS_FILE=.arc/items.jsonl
else
    exit 0
fi

tactical=$(python3 << 'PYEOF'
import json, sys

items_file = sys.argv[1] if len(sys.argv) > 1 else ".bon/items.jsonl"
lines = []
try:
    with open(items_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if item.get("tactical") and item.get("status") == "open":
                t = item["tactical"]
                lines.append(f'Working: {item["title"]} ({item["id"]})')
                for idx, step in enumerate(t.get("steps", [])):
                    current = t.get("current", 0)
                    if idx < current:
                        mark = "\u2713"
                    elif idx == current:
                        mark = "\u2192"
                    else:
                        mark = " "
                    suffix = " [current]" if idx == current else ""
                    lines.append(f"{mark} {idx + 1}. {step}{suffix}")
                break
except Exception:
    pass

if lines:
    print("\n".join(lines))
PYEOF
)

[ -z "$tactical" ] && exit 0

escaped=$(echo "$tactical" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')

cat <<EOF
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "🎯 Active bon tactical:\n${escaped}\n\nWork on the CURRENT step. Run 'bon step' when it's complete before moving on."}}
EOF
