#!/bin/bash
# PostToolUse hook for ExitPlanMode
# Fires after plan approval, before work starts.
# Reminds Claude to encode the plan as bon items.

# Only relevant if .bon/ exists in the working directory
HOOK_INPUT=$(cat)
CWD=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('cwd',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)
[ -n "$CWD" ] && [ -d "$CWD/.bon" ] || exit 0

cat << 'EOF'
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "Plans become bons. Read the plan file and encode it as bon outcomes + actions NOW, before touching code. The plan file is scratch — the bon hierarchy is the real artifact.\n\nUse the transmutation pattern:\n  --why from context/motivation\n  --how from approach/strategy/constraints\n  --what as numbered steps (become tactical steps)\n  --done as verifiable success criteria\n\nAfter creating the bons, delete the plan file."}}
EOF
