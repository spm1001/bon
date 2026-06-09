#!/bin/bash
#
# Session Start Hook
# Outputs session context to stdout (Claude sees this automatically).
# Instruction shard symlink is handled by ensure-bon.sh (runs first).
#
# Finds scripts relative to this hook's location (works in plugin cache).
# No set -euo pipefail — individual failures must not kill the whole hook.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$HOOK_DIR")"

# Read hook stdin (JSON with session metadata)
INPUT=$(cat)
SOURCE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('source',''))" 2>/dev/null || echo "")

# On resume, skip the full briefing — it's already in context.
# (A resume-time rm of the session's auto-handoff used to live here. Auto-handoffs
# were retired 2026-04-05 (2d451fe), so the only files the rm could still match
# were deliberate /close handoffs — and harness bridge-syncs fire SessionStart
# with source=resume on *closed* sessions, silently deleting committed handoffs.
# Never delete handoffs on resume.)

if [ "$SOURCE" != "resume" ]; then
    PLUGIN_SCRIPTS="$PLUGIN_ROOT/scripts"

    if [ -x "$PLUGIN_SCRIPTS/open-context.sh" ]; then
        "$PLUGIN_SCRIPTS/open-context.sh" 2>/dev/null || true
    fi
fi

# Check for incomplete /close from previous session
CHECKPOINT_FILE="$HOME/.claude/.close-checkpoint"
if [ -f "$CHECKPOINT_FILE" ]; then
    echo ""
    echo "=== INCOMPLETE CLOSE ==="
    echo "WARNING: Last session's /close was interrupted."
    echo ""
    cat "$CHECKPOINT_FILE"
    echo ""
    echo "Run '/close --resume' to complete, or delete checkpoint to ignore."
fi

exit 0
