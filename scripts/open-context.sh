#!/bin/bash
# Session context gathering — enriched briefing
# Stdout: handoff + structured summary (understanding.md loaded via /open skill)
# Disk: full bon hierarchy (bon.txt) for on-demand reading

set -euo pipefail

# === CROSS-PLATFORM HELPERS ===
if stat -c '%Y' /dev/null &>/dev/null; then
    file_mtime() { stat -c '%Y' "$1"; }
else
    file_mtime() { stat -f '%m' "$1"; }
fi

# === PATHS ===
BASE_CONTEXT_DIR="$HOME/.claude/.session-context"
CWD=$(pwd -P)
ENCODED_PATH=$(echo "$CWD" | sed 's/[^a-zA-Z0-9-]/-/g')
CONTEXT_DIR="$BASE_CONTEXT_DIR/$ENCODED_PATH"
mkdir -p "$CONTEXT_DIR"

# === SELF-VALIDATION ===
validate_dependencies() {
    local missing=""
    command -v python3 &>/dev/null || missing="$missing python3"
    command -v stat &>/dev/null || missing="$missing stat"
    if [ -n "$missing" ]; then
        echo "ERROR: missing dependencies:$missing"
        exit 1
    fi
}
validate_dependencies

# === HELPERS ===
time_ago() {
    local seconds=$1
    if [ "$seconds" -lt 3600 ]; then
        local mins=$((seconds / 60))
        [ "$mins" -le 1 ] && echo "just now" || echo "${mins}m ago"
    elif [ "$seconds" -lt 86400 ]; then
        echo "$((seconds / 3600))h ago"
    elif [ "$seconds" -lt 172800 ]; then
        echo "yesterday"
    else
        echo "$((seconds / 86400))d ago"
    fi
}

# === LOCAL HANDOFF WARNING ===
LOCAL_HANDOFFS=$(find . -maxdepth 1 -name '.handoff*' 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOCAL_HANDOFFS" -gt 0 ]; then
    echo "Warning: $LOCAL_HANDOFFS orphaned local .handoff* files (should move to .bon/handoffs/)"
    echo ""
fi

# === GATHER TO DISK (silent) ===

# --- Handoff resolution ---
# Primary: .bon/handoffs/ (walk up from CWD)
# Fallback: ~/.bon/handoffs/ (global, for container sessions)
NOW=$(date +%s)

# Walk up to find .bon/handoffs/
BON_HANDOFF_DIR=""
WALK="$CWD"
while [ "$WALK" != "/" ]; do
    if [ -d "$WALK/.bon/handoffs" ]; then
        BON_HANDOFF_DIR="$WALK/.bon/handoffs"
        break
    fi
    WALK=$(dirname "$WALK")
done

GLOBAL_BON_DIR="$HOME/.bon/handoffs"

# Find the most recent handoff across both locations
LATEST_FILE=""
LATEST_PURPOSE=""
LATEST_STR=""

# Rank by the date in the handoff header ("# Handoff — YYYY-MM-DD"), with
# mtime only breaking same-day ties: a fresh clone flattens every mtime to
# checkout time, so mtime-first picks an arbitrary (often ancient) handoff.
# Emits "sortkey|path"; header-less files rank by mtime alone at the bottom.
find_latest_in() {
    local dir="$1" best_key="" best_file="" f d mt key
    [ -d "$dir" ] || return 0
    for f in "$dir"/*.md; do
        [ -e "$f" ] || continue
        d=$(sed -n 's/^# Handoff — \([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\).*/\1/p' "$f" 2>/dev/null | head -1)
        [ -z "$d" ] && d="0000-00-00"
        mt=$(file_mtime "$f")
        key=$(printf '%s.%012d' "$d" "$mt")
        if [ -z "$best_key" ] || [ "$key" \> "$best_key" ]; then
            best_key="$key"
            best_file="$f"
        fi
    done
    [ -n "$best_file" ] && echo "${best_key}|${best_file}"
}

CANDIDATE_BON=$(find_latest_in "$BON_HANDOFF_DIR")
CANDIDATE_GLOBAL=$(find_latest_in "$GLOBAL_BON_DIR")

# Pick the better of the two locations by the same key
BEST_KEY=""
for CANDIDATE in "$CANDIDATE_BON" "$CANDIDATE_GLOBAL"; do
    if [ -n "$CANDIDATE" ]; then
        KEY="${CANDIDATE%%|*}"
        FILE="${CANDIDATE#*|}"
        if [ -z "$BEST_KEY" ] || [ "$KEY" \> "$BEST_KEY" ]; then
            BEST_KEY="$KEY"
            LATEST_FILE="$FILE"
        fi
    fi
done

if [ -n "$LATEST_FILE" ]; then
    LATEST_TIME=$(file_mtime "$LATEST_FILE")
    LATEST_AGO=$((NOW - LATEST_TIME))
    LATEST_STR=$(time_ago $LATEST_AGO)
    LATEST_PURPOSE=$(grep "^purpose:" "$LATEST_FILE" 2>/dev/null | head -1 | cut -d: -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true)
    if [ -z "$LATEST_PURPOSE" ]; then
        LATEST_PURPOSE=$(grep -A1 "^## Done" "$LATEST_FILE" 2>/dev/null | tail -1 | sed 's/^- //' | cut -c1-60 || true)
    fi
fi

# --- Bon context ---
BON_FILE="$CONTEXT_DIR/bon.txt"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BON_READ="$SCRIPT_DIR/bon-read.sh"
[ -x "$BON_READ" ] || BON_READ="$HOME/.claude/scripts/bon-read.sh"
BON_LIST_OUTPUT=""
BON_READY_OUTPUT=""
BON_CURRENT_OUTPUT=""

# Walk up to the board root, mirroring the CLI's discovery: at CWD any
# .bon counts; above it only one with a prefix file (skips bare handoff
# stashes like ~/.bon); a .git boundary stops the walk so a nested repo
# never adopts an outer repo's board.
BON_BACKEND="none"
BON_ROOT=""
BWALK=$(pwd -P)
BSTART="$BWALK"
while [ "$BWALK" != "/" ]; do
    if [ -d "$BWALK/.bon" ] && { [ "$BWALK" = "$BSTART" ] || [ -f "$BWALK/.bon/prefix" ]; }; then
        BON_ROOT="$BWALK"
        break
    fi
    [ -e "$BWALK/.git" ] && break
    BWALK=$(dirname "$BWALK")
done
if [ -n "$BON_ROOT" ]; then
    if [ -f "$BON_ROOT/.bon/backend" ] && [ "$(cat "$BON_ROOT/.bon/backend" 2>/dev/null)" = "dolt" ]; then
        BON_BACKEND="dolt"
    elif [ -f "$BON_ROOT/.bon/items.jsonl" ]; then
        BON_BACKEND="jsonl"
    fi
fi

# Invocations run from the board root: bon-read.sh reads .bon/ relative
# to cwd, and older installed bon CLIs don't walk up.
if [ "$BON_BACKEND" = "jsonl" ]; then
    if [ -x "$BON_READ" ]; then
        BON_LIST_OUTPUT=$(cd "$BON_ROOT" && "$BON_READ" list 2>/dev/null || true)
        BON_READY_OUTPUT=$(cd "$BON_ROOT" && "$BON_READ" ready 2>/dev/null || true)
        BON_CURRENT_OUTPUT=$(cd "$BON_ROOT" && "$BON_READ" current 2>/dev/null || true)
    elif command -v bon &>/dev/null; then
        BON_LIST_OUTPUT=$(cd "$BON_ROOT" && bon list 2>/dev/null || true)
        BON_READY_OUTPUT=$(cd "$BON_ROOT" && bon list --ready 2>/dev/null || true)
        BON_CURRENT_OUTPUT=$(cd "$BON_ROOT" && bon show --current 2>/dev/null || true)
    fi
elif [ "$BON_BACKEND" = "dolt" ]; then
    if command -v bon &>/dev/null; then
        BON_LIST_OUTPUT=$(cd "$BON_ROOT" && bon list 2>&1 || true)
        BON_READY_OUTPUT=$(cd "$BON_ROOT" && bon list --ready 2>&1 || true)
        BON_CURRENT_OUTPUT=$(cd "$BON_ROOT" && bon show --current 2>/dev/null || true)
        if echo "$BON_LIST_OUTPUT" | grep -q "Cannot connect"; then
            BON_DOLT_ERROR="$BON_LIST_OUTPUT"
            BON_LIST_OUTPUT=""
            BON_READY_OUTPUT=""
        fi
    else
        BON_DOLT_ERROR="Backend is dolt but bon CLI not in PATH"
    fi
fi

# Write full hierarchy to disk (detail on demand)
if [ -n "$BON_LIST_OUTPUT" ]; then
    {
        echo "# Bon Context (generated $(date '+%Y-%m-%d %H:%M'))"
        echo "# Generated for: $CWD"
        echo "# Backend: $BON_BACKEND"
        echo ""
        echo "## Ready Work"
        echo "$BON_READY_OUTPUT"
        echo ""
        echo "## Full Hierarchy"
        echo "$BON_LIST_OUTPUT"
    } > "$BON_FILE"
elif [ -n "${BON_DOLT_ERROR:-}" ]; then
    {
        echo "# Bon Context (generated $(date '+%Y-%m-%d %H:%M'))"
        echo "# Generated for: $CWD"
        echo "# Backend: dolt (CONNECTION FAILED)"
        echo ""
        echo "## Error"
        echo "$BON_DOLT_ERROR"
        echo ""
        echo "Recovery: systemctl --user start dolt-bon.service"
    } > "$BON_FILE"
else
    rm -f "$BON_FILE"
fi

# === GHOST FILE WARNING ===
if [ "$BON_BACKEND" = "dolt" ] && [ -f ".bon/items.jsonl" ]; then
    echo "Warning: .bon/items.jsonl exists but backend is Dolt — this file is stale (pre-migration ghost)."
    echo "  Remove it: rm .bon/items.jsonl"
    echo ""
fi

# === STDOUT BRIEFING ===
echo "=== SESSION ==="

# --- 1. Greeting ---
CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_HOUR" -lt 12 ]; then TIME_OF_DAY="morning"
elif [ "$CURRENT_HOUR" -lt 17 ]; then TIME_OF_DAY="afternoon"
elif [ "$CURRENT_HOUR" -lt 21 ]; then TIME_OF_DAY="evening"
else TIME_OF_DAY="night"
fi
echo "Good $TIME_OF_DAY. It's $(date '+%-d %b %Y, %H:%M')."
echo ""

# --- 2. Latest handoff in full ---
if [ -n "$LATEST_FILE" ]; then
    echo "Last session ($LATEST_STR): $LATEST_PURPOSE"
    echo ""
    cat "$LATEST_FILE"
    echo ""
fi

# --- 3. Outcomes only ---
if [ "$BON_BACKEND" != "none" ]; then
    if [ -n "${BON_DOLT_ERROR:-}" ]; then
        echo "Bon: backend is dolt but server is unreachable"
        echo "  Run: systemctl --user start dolt-bon.service"
        echo ""
    elif [ -n "$BON_LIST_OUTPUT" ]; then
        echo "Outcomes we're working towards:"
        echo "$BON_LIST_OUTPUT" | grep -E '^○' | while IFS= read -r line; do
            echo "  $line"
        done
        echo ""
    fi
fi

# --- 4. Active work / nothing in progress ---
if [ -n "${BON_DOLT_ERROR:-}" ]; then
    true  # Already reported above
elif [ "$BON_BACKEND" != "none" ]; then
    if [ -z "$BON_CURRENT_OUTPUT" ]; then
        echo "Nothing in progress — pick an action to start."
        echo ""
    fi
fi

# --- 5. Suggested (from handoff Opportunities or Next section) ---
if [ -n "$LATEST_FILE" ]; then
    # fond-v1: ### Opportunities under ## For the next Claude
    NEXT_LINES=$(sed -n '/^### Opportunities/,/^#/{/^#/d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' || true)
    # Legacy: ## Next (flat section)
    [ -z "$NEXT_LINES" ] && NEXT_LINES=$(sed -n '/^## Next/,/^## /{/^## /d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' || true)
    if [ -n "$NEXT_LINES" ]; then
        echo "Suggested:"
        echo "$NEXT_LINES" | while IFS= read -r line; do
            echo "  $line"
        done
        echo ""
    fi
fi

# --- 6. Contributions pending ---
if [ -d ".bon/contributions" ]; then
    CONTRIB_FILES=$(ls -1 .bon/contributions/*.md 2>/dev/null || true)
    if [ -n "$CONTRIB_FILES" ]; then
        CONTRIB_COUNT=$(echo "$CONTRIB_FILES" | wc -l | tr -d ' ')
        echo "Contributions pending ($CONTRIB_COUNT):"
        echo "$CONTRIB_FILES" | while IFS= read -r f; do
            echo "  $(basename "$f")"
        done
        echo ""
    fi
fi
