#!/bin/bash
#
# Session Start Hook
# Outputs session context to stdout (Claude sees this automatically)
#
# Finds scripts relative to this hook's location (works in plugin cache).

set -euo pipefail

# Symlink instruction shard into rules/ (survives plugin version changes)
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$HOOK_DIR")"
if [ -f "$PLUGIN_ROOT/instructions.md" ]; then
    mkdir -p "$HOME/.claude/rules"
    ln -sf "$PLUGIN_ROOT/instructions.md" "$HOME/.claude/rules/bon.md"
fi

# Read hook stdin (JSON with session metadata)
INPUT=$(cat)
SOURCE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('source',''))" 2>/dev/null || echo "")

# On resume, skip the full briefing — it's already in context
# Also delete any auto-handoff for this session (session isn't over, just reloading)
if [ "$SOURCE" = "resume" ]; then
    SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null || echo "")
    if [ -n "$SESSION_ID" ]; then
        SHORT_ID="${SESSION_ID:0:8}"
        # Walk up to find .bon/
        SEARCH=$(pwd -P)
        while [ "$SEARCH" != "/" ]; do
            if [ -d "$SEARCH/.bon/handoffs" ]; then
                rm -f "$SEARCH/.bon/handoffs/${SHORT_ID}.md" 2>/dev/null
                break
            fi
            SEARCH=$(dirname "$SEARCH")
        done
    fi
fi

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
