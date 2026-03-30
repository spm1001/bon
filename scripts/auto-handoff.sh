#!/bin/bash
# Auto-handoff: mechanical safety net for sessions that end without /close
#
# Called by session-end.sh when no handoff was written by /close.
# Generates a minimal handoff from git + bon state so the next session
# gets *something* rather than a cold start.
#
# The (auto) marker in the header tells /open this was mechanical,
# not reflective — gotchas/risks sections are absent.
#
# Usage: auto-handoff.sh <cwd> <session_id> [transcript_path]

set -euo pipefail

CWD="${1:-$(pwd -P)}"
SESSION_ID="${2:-}"
TRANSCRIPT_PATH="${3:-}"

[ -z "$SESSION_ID" ] && exit 0

# Walk up from CWD to find .bon/
BON_ROOT=""
SEARCH="$CWD"
while [ "$SEARCH" != "/" ]; do
    if [ -d "$SEARCH/.bon" ]; then
        BON_ROOT="$SEARCH"
        break
    fi
    SEARCH=$(dirname "$SEARCH")
done

# No .bon/ found — not a bon project, nothing to do
[ -z "$BON_ROOT" ] && exit 0

HANDOFF_DIR="$BON_ROOT/.bon/handoffs"

# Legacy location for backwards-compat fast-path check
ENCODED=$(echo "$CWD" | sed 's/[^a-zA-Z0-9-]/-/g')
LEGACY_HANDOFF_DIR="$HOME/.claude/handoffs/$ENCODED"

SHORT_ID="${SESSION_ID:0:8}"

# If /close already wrote a handoff for this session, skip
# Check both new location (.bon/handoffs/) and legacy (~/.claude/handoffs/)
for CHECK_DIR in "$HANDOFF_DIR" "$LEGACY_HANDOFF_DIR"; do
    if [ -f "$CHECK_DIR/${SHORT_ID}.md" ]; then
        exit 0
    fi
    if ls "$CHECK_DIR"/*.md 2>/dev/null | xargs grep -l "session_id: $SESSION_ID" >/dev/null 2>&1; then
        exit 0
    fi
done

mkdir -p "$HANDOFF_DIR"

# --- Gather mechanical context (fast, always available) ---

DATE=$(date '+%Y-%m-%d')
HANDOFF_FILE="$HANDOFF_DIR/${SHORT_ID}.md"

# Recent git commits
GIT_DONE=""
if [ -e "$CWD/.git" ] || git -C "$CWD" rev-parse --git-dir &>/dev/null; then
    GIT_DONE=$(git -C "$CWD" log --oneline --since="8 hours ago" 2>/dev/null | head -10 || true)
fi

# Bon open/ready items
BON_NEXT=""
if command -v bon &>/dev/null; then
    BON_NEXT=$(cd "$CWD" && bon list --ready 2>/dev/null | head -20 || true)
fi

# --- LLM-mediated handoff (rich path) ---

# Requires: transcript file exists, ccconv available, claude CLI available
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ] && command -v claude &>/dev/null; then
    # Find ccconv for transcript preprocessing
    CCCONV=""
    if command -v ccconv &>/dev/null; then
        CCCONV="ccconv"
    elif [ -f "$HOME/Repos/scratch/ccconv.py" ]; then
        CCCONV="python3 $HOME/Repos/scratch/ccconv.py"
    fi

    if [ -n "$CCCONV" ]; then
        # Background: user isn't waiting, session is already over
        nohup bash -c '
            CCCONV="'"$CCCONV"'"
            TRANSCRIPT_PATH="'"$TRANSCRIPT_PATH"'"
            HANDOFF_FILE="'"$HANDOFF_FILE"'"
            SESSION_ID="'"$SESSION_ID"'"
            DATE="'"$DATE"'"
            GIT_DONE="'"$(echo "$GIT_DONE" | sed "s/'/'\\''/g")"'"
            BON_NEXT="'"$(echo "$BON_NEXT" | sed "s/'/'\\''/g")"'"

            # Convert transcript to readable conversation (no tool details)
            CONVERSATION=$($CCCONV "$TRANSCRIPT_PATH" 2>/dev/null)
            [ -z "$CONVERSATION" ] && exit 1

            # Build the prompt with all context
            PROMPT=$(cat <<PROMPTEOF
You are generating a handoff document from a Claude Code session that ended
without a reflective /close. Produce a concise, informative handoff so the
next Claude session has context.

## Git commits this session
${GIT_DONE:-"(none)"}

## Open bon items
${BON_NEXT:-"(none)"}

## Session transcript
$CONVERSATION

---

Write a markdown handoff with EXACTLY this format:

# Handoff — $DATE (auto)

session_id: $SESSION_ID
purpose: (one-line summary of what the session was about)

## Done
(bullet list of what was accomplished — be specific, include file names and bon IDs)

## Next
(bullet list of suggested next steps — include bon IDs where relevant)

## Gotchas
- Auto-generated handoff — no reflective close was performed
(add any other gotchas you spotted in the transcript)

Be concise. Preserve bon item IDs (bon-xxxxx). Include file paths and
technical details. Do not add sections beyond Done/Next/Gotchas.
PROMPTEOF
            )

            # Generate via claude -p in bare mode (no hooks, no plugins)
            RESULT=$(echo "$PROMPT" | claude -p --bare --model haiku 2>/dev/null)

            if [ -n "$RESULT" ]; then
                echo "$RESULT" > "$HANDOFF_FILE"
            fi
        ' &>/dev/null &
        disown
        exit 0
    fi
fi

# --- Mechanical fallback (no transcript or no claude/ccconv) ---

PURPOSE=""
if [ -n "$GIT_DONE" ]; then
    PURPOSE=$(echo "$GIT_DONE" | head -1 | cut -d' ' -f2-)
else
    PURPOSE="Session ended without /close"
fi

{
    echo "# Handoff — $DATE (auto)"
    echo ""
    echo "session_id: $SESSION_ID"
    echo "purpose: $PURPOSE"
    echo ""
    echo "## Done"
    if [ -n "$GIT_DONE" ]; then
        echo "$GIT_DONE" | while IFS= read -r line; do
            echo "- $line"
        done
    else
        echo "- (no commits detected in session)"
    fi
    echo ""
    echo "## Next"
    if [ -n "$BON_NEXT" ]; then
        echo "$BON_NEXT" | while IFS= read -r line; do
            [ -n "$line" ] && echo "- $line"
        done
    else
        echo "- (check bon or project state)"
    fi
    echo ""
    echo "## Gotchas"
    echo "- Auto-generated handoff — no reflective close was performed"
} > "$HANDOFF_FILE"
