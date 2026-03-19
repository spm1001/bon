#!/bin/bash
#
# Session End Hook (lightweight)
# Generates auto-handoff if /close didn't run. No garde/extraction.
#
# Finds scripts relative to this hook's location (works in plugin cache).

# Skip for subagent invocations
[ -n "${GARDE_SUBAGENT:-}" ] && exit 0
[ -n "${MEM_SUBAGENT:-}" ] && exit 0
[ -n "${CLAUDE_SUBAGENT:-}" ] && exit 0

# Find scripts dir
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SCRIPTS="$(dirname "$HOOK_DIR")/scripts"

if [ -x "$PLUGIN_SCRIPTS/auto-handoff.sh" ]; then
    SCRIPTS_DIR="$PLUGIN_SCRIPTS"
else
    exit 0
fi

# Read hook input from stdin (JSON with session_id, cwd, etc.)
HOOK_INPUT=$(cat)

HOOK_SESSION_ID=$(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('session_id',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)
HOOK_CWD=$(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('cwd',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)
[ -z "$HOOK_CWD" ] && HOOK_CWD="$(pwd -P)"

# Auto-handoff safety net
if [ -n "$HOOK_SESSION_ID" ] && [ -x "$SCRIPTS_DIR/auto-handoff.sh" ]; then
    "$SCRIPTS_DIR/auto-handoff.sh" "$HOOK_CWD" "$HOOK_SESSION_ID" 2>/dev/null || true
fi

exit 0
