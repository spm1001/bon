#!/bin/bash
# Session context gathering — enriched briefing
# Stdout: full orientation (understanding + handoff + structured summary)
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

find_latest_in() {
    local dir="$1"
    [ -d "$dir" ] && ls -t "$dir"/*.md 2>/dev/null | head -1 || true
}

CANDIDATE_BON=$(find_latest_in "$BON_HANDOFF_DIR")
CANDIDATE_GLOBAL=$(find_latest_in "$GLOBAL_BON_DIR")

# Pick the most recent candidate by mtime
BEST_MTIME=0
for CANDIDATE in "$CANDIDATE_BON" "$CANDIDATE_GLOBAL"; do
    if [ -n "$CANDIDATE" ]; then
        MT=$(file_mtime "$CANDIDATE")
        if [ "$MT" -gt "$BEST_MTIME" ]; then
            BEST_MTIME=$MT
            LATEST_FILE="$CANDIDATE"
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

BON_BACKEND="none"
if [ -d ".bon" ] || [ -d ".arc" ]; then
    if [ -f ".bon/backend" ] && [ "$(cat .bon/backend 2>/dev/null)" = "dolt" ]; then
        BON_BACKEND="dolt"
    elif [ -f ".bon/items.jsonl" ] || [ -f ".arc/items.jsonl" ]; then
        BON_BACKEND="jsonl"
    fi
fi

if [ "$BON_BACKEND" = "jsonl" ]; then
    if [ -x "$BON_READ" ]; then
        BON_LIST_OUTPUT=$("$BON_READ" list 2>/dev/null || true)
        BON_READY_OUTPUT=$("$BON_READ" ready 2>/dev/null || true)
        BON_CURRENT_OUTPUT=$("$BON_READ" current 2>/dev/null || true)
    elif command -v bon &>/dev/null; then
        BON_LIST_OUTPUT=$(bon list 2>/dev/null || true)
        BON_READY_OUTPUT=$(bon list --ready 2>/dev/null || true)
        BON_CURRENT_OUTPUT=$(bon show --current 2>/dev/null || true)
    fi
elif [ "$BON_BACKEND" = "dolt" ]; then
    if command -v bon &>/dev/null; then
        BON_LIST_OUTPUT=$(bon list 2>&1 || true)
        BON_READY_OUTPUT=$(bon list --ready 2>&1 || true)
        BON_CURRENT_OUTPUT=$(bon show --current 2>/dev/null || true)
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

# --- 2. understanding.md in full ---
if [ -f ".bon/understanding.md" ]; then
    cat ".bon/understanding.md"
    echo ""
elif [ -f "understanding.md" ]; then
    cat "understanding.md"
    echo ""
fi

# --- 3. Latest handoff in full ---
if [ -n "$LATEST_FILE" ]; then
    echo "Last session ($LATEST_STR): $LATEST_PURPOSE"
    echo ""
    cat "$LATEST_FILE"
    echo ""
fi

# --- 4. Outcomes only ---
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

# --- 5. Active work / nothing in progress ---
if [ -n "${BON_DOLT_ERROR:-}" ]; then
    true  # Already reported above
elif [ "$BON_BACKEND" != "none" ]; then
    if [ -z "$BON_CURRENT_OUTPUT" ]; then
        echo "Nothing in progress — pick an action to start."
        echo ""
    fi
fi

# --- 6. Suggested (from handoff Opportunities or Next section) ---
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

# --- 7. Contributions pending ---
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
