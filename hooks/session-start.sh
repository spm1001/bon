#!/bin/bash
#
# Session Start Hook
# Outputs session context to stdout (Claude sees this automatically)
#
# Finds scripts relative to this hook's location (works in plugin cache).

set -euo pipefail

# Find scripts dir: sibling to hooks/ in the same repo/plugin
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_SCRIPTS="$(dirname "$HOOK_DIR")/scripts"

if [ -x "$PLUGIN_SCRIPTS/open-context.sh" ]; then
    SCRIPTS_DIR="$PLUGIN_SCRIPTS"
else
    exit 0  # No scripts available — silent
fi

# === CONTEXT OUTPUT (stdout → Claude) ===
"$SCRIPTS_DIR/open-context.sh" 2>/dev/null || true

# === BACKGROUND UPDATES (no stdout — runs silently) ===
if [ -x "$SCRIPTS_DIR/update-all.sh" ]; then
    mkdir -p "$HOME/.claude/logs"
    nohup "$SCRIPTS_DIR/update-all.sh" >> "$HOME/.claude/logs/update.log" 2>&1 &
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
