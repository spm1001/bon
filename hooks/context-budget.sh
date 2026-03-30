#!/bin/bash
# context-budget.sh — Inject context usage warning into Claude's prompt.
# Fires on UserPromptSubmit. Reads transcript token usage, warns at >30%.
# Fails open (exit 0) on any error. Silent in subagents.

set -euo pipefail
trap 'exit 0' ERR

# Skip for subagent invocations
[ -n "${GARDE_SUBAGENT:-}" ] && exit 0
[ -n "${MEM_SUBAGENT:-}" ] && exit 0
[ -n "${CLAUDE_SUBAGENT:-}" ] && exit 0

# Require jq; fail open if missing
command -v jq &>/dev/null || exit 0

# Read CWD from hook stdin
HOOK_INPUT=$(cat)
CWD=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('cwd',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)
[ -n "$CWD" ] || CWD="$(pwd -P)"

# Find Claude Code project directory for this CWD
PROJECT_DIR="$HOME/.claude/projects/$(echo "$CWD" | tr '/' '-')"
[ -d "$PROJECT_DIR" ] || exit 0

# Find the most recently modified .jsonl transcript (skip subagent dirs)
TRANSCRIPT=""
LATEST_MTIME=0
for f in "$PROJECT_DIR"/*.jsonl; do
    [ -f "$f" ] || continue
    MTIME=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0)
    if [ "$MTIME" -gt "$LATEST_MTIME" ]; then
        LATEST_MTIME="$MTIME"
        TRANSCRIPT="$f"
    fi
done
[ -n "$TRANSCRIPT" ] || exit 0

# Parse last assistant message's token usage from the transcript.
_reverse() { if command -v tac &>/dev/null; then tac "$1"; else tail -r "$1"; fi; }
USAGE=$(_reverse "$TRANSCRIPT" \
    | jq -r 'select(.type == "assistant" and .message.usage != null)
              | .message.usage
              | "\(.input_tokens // 0) \(.cache_creation_input_tokens // 0) \(.cache_read_input_tokens // 0)"' \
    2>/dev/null \
    | head -1)
[ -n "$USAGE" ] || exit 0

read -r INPUT CACHE_CREATE CACHE_READ <<< "$USAGE"
TOTAL_IN=$(( INPUT + CACHE_CREATE + CACHE_READ ))
[ "$TOTAL_IN" -gt 0 ] 2>/dev/null || exit 0

# Context window size — read from statusline sidecar if available
ppid_comm=$(ps -o comm= -p $PPID 2>/dev/null | tr -d ' ')
if [ "$ppid_comm" = "claude" ]; then
    cc_pid=$PPID
else
    cc_pid=$(ps -o ppid= -p $PPID 2>/dev/null | tr -d ' ')
fi
CTX_FILE="/tmp/.claude-ctx-${cc_pid:-$$}"
if [ -f "$CTX_FILE" ]; then
    MAX_TOKENS=$(cat "$CTX_FILE")
else
    MAX_TOKENS="${CLAUDE_CONTEXT_WINDOW:-200000}"
fi

# Calculate usage
USED_PCT=$(awk "BEGIN { printf \"%d\", $TOTAL_IN / $MAX_TOKENS * 100 }")
REMAINING_K=$(( (MAX_TOKENS - TOTAL_IN) / 1000 ))
USED_K=$(( TOTAL_IN / 1000 ))
MAX_K=$(( MAX_TOKENS / 1000 ))

# Only inject when >30% used
[ "$USED_PCT" -ge 30 ] || exit 0

# Tiered message
if [ "$USED_PCT" -ge 90 ]; then
    MSG="CONTEXT CRITICAL: ${USED_PCT}% used (${USED_K}k/${MAX_K}k). ~${REMAINING_K}k left. Wrap up or hand off NOW."
elif [ "$USED_PCT" -ge 75 ]; then
    MSG="Context budget: ${USED_PCT}% used (${USED_K}k/${MAX_K}k). ~${REMAINING_K}k remaining. Start wrapping up."
else
    MSG="Context: ${USED_PCT}% (${USED_K}k/${MAX_K}k, ~${REMAINING_K}k free)"
fi

# Canonical plugin hook output format
cat <<EOF
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "$MSG"}}
EOF
