#!/bin/bash
# Session context gathering
# Stdout: compact briefing for human and Claude to orient from
# Disk: full detail (bon.txt) for Claude to read on demand

set -euo pipefail

# === CROSS-PLATFORM HELPERS ===
# GNU stat (Linux) vs BSD stat (macOS) have incompatible flags.
# Detect once, define a function, use everywhere.
if stat -c '%Y' /dev/null &>/dev/null; then
    file_mtime() { stat -c '%Y' "$1"; }
else
    file_mtime() { stat -f '%m' "$1"; }
fi

# === PATHS ===
BASE_CONTEXT_DIR="$HOME/.claude/.session-context"
CWD=$(pwd -P)
# Encoded path always starts with '-' — never use as bare arg; always prefix with absolute path
ENCODED_PATH=$(echo "$CWD" | sed 's/[^a-zA-Z0-9-]/-/g')
CONTEXT_DIR="$BASE_CONTEXT_DIR/$ENCODED_PATH"
mkdir -p "$CONTEXT_DIR"

# === SELF-VALIDATION ===
validate_dependencies() {
    local missing=""
    if ! command -v python3 &>/dev/null; then
        missing="$missing python3"
    fi
    if ! command -v stat &>/dev/null; then
        missing="$missing stat"
    fi
    if [ -n "$missing" ]; then
        echo "ERROR: missing dependencies:$missing"
        exit 1
    fi
}
validate_dependencies

# === HELPERS ===
time_ago() {
    local seconds=$1
    local timestamp=$2
    local absolute=$(date -r "$timestamp" '+%Y-%m-%d %H:%M' 2>/dev/null || date -d "@$timestamp" '+%Y-%m-%d %H:%M' 2>/dev/null)
    local relative
    if [ "$seconds" -lt 3600 ]; then
        local mins=$((seconds / 60))
        [ "$mins" -le 1 ] && relative="just now" || relative="${mins}m ago"
    elif [ "$seconds" -lt 86400 ]; then
        local hours=$((seconds / 3600))
        relative="${hours}h ago"
    elif [ "$seconds" -lt 172800 ]; then
        relative="yesterday"
    else
        local days=$((seconds / 86400))
        relative="${days}d ago"
    fi
    echo "$relative"
}

# === LOCAL HANDOFF WARNING ===
LOCAL_HANDOFFS=$(find . -maxdepth 1 -name '.handoff*' 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOCAL_HANDOFFS" -gt 0 ]; then
    echo "Warning: $LOCAL_HANDOFFS orphaned local .handoff* files (should move to ~/.claude/handoffs/)"
    echo ""
fi

# === GATHER TO DISK (silent) ===

# --- Handoff index ---
ARCHIVE_DIR="$HOME/.claude/handoffs"
NOW=$(date +%s)
PROJECT_FOLDER="$ARCHIVE_DIR/$ENCODED_PATH"

# Cross-machine fallback: if native path not found, try alternate home prefixes
# Handles Mac→Linux migration (/Users/modha → /home/modha) and vice versa
if [ ! -d "$PROJECT_FOLDER" ]; then
    ALT_ENCODED=""
    case "$ENCODED_PATH" in
        -home-modha-*)  ALT_ENCODED=$(echo "$ENCODED_PATH" | sed 's/^-home-modha-/-Users-modha-/') ;;
        -Users-modha-*) ALT_ENCODED=$(echo "$ENCODED_PATH" | sed 's/^-Users-modha-/-home-modha-/') ;;
    esac
    if [ -n "$ALT_ENCODED" ] && [ -d "$ARCHIVE_DIR/$ALT_ENCODED" ]; then
        PROJECT_FOLDER="$ARCHIVE_DIR/$ALT_ENCODED"
    fi
fi

LATEST_FILE=""
LATEST_PURPOSE=""
LATEST_STR=""

if [ -d "$PROJECT_FOLDER" ]; then
    # Latest handoff only — older ones are archive for mem, not startup
    LATEST_FILE=$(ls -t "$PROJECT_FOLDER"/*.md 2>/dev/null | head -1 || true)

    if [ -n "$LATEST_FILE" ]; then
        LATEST_TIME=$(file_mtime "$LATEST_FILE")
        LATEST_AGO=$((NOW - LATEST_TIME))
        LATEST_STR=$(time_ago $LATEST_AGO $LATEST_TIME)
        LATEST_PURPOSE=$(grep "^purpose:" "$LATEST_FILE" 2>/dev/null | head -1 | cut -d: -f2- | xargs || true)
        if [ -z "$LATEST_PURPOSE" ]; then
            LATEST_PURPOSE=$(grep -A1 "^## Done" "$LATEST_FILE" 2>/dev/null | tail -1 | sed 's/^- //' | cut -c1-60 || true)
        fi
    fi
fi

# --- Bon context ---
BON_FILE="$CONTEXT_DIR/bon.txt"
BON_READ="$HOME/.claude/scripts/bon-read.sh"
BON_LIST_OUTPUT=""
BON_READY_OUTPUT=""
BON_CURRENT_OUTPUT=""

if [ -f ".bon/items.jsonl" ] || [ -f ".arc/items.jsonl" ]; then
    if [ -x "$BON_READ" ]; then
        BON_LIST_OUTPUT=$("$BON_READ" list 2>/dev/null || true)
        BON_READY_OUTPUT=$("$BON_READ" ready 2>/dev/null || true)
        BON_CURRENT_OUTPUT=$("$BON_READ" current 2>/dev/null || true)
    elif command -v bon &>/dev/null; then
        # Fallback to bon CLI if bon-read.sh not installed
        BON_LIST_OUTPUT=$(bon list 2>/dev/null || true)
        BON_READY_OUTPUT=$(bon list --ready 2>/dev/null || true)
        BON_CURRENT_OUTPUT=$(bon show --current 2>/dev/null || true)
    fi

    if [ -n "$BON_LIST_OUTPUT" ]; then
        # Write full hierarchy to disk
        {
            echo "# Bon Context (generated $(date '+%Y-%m-%d %H:%M'))"
            echo "# Generated for: $CWD"
            echo ""
            echo "## Ready Work"
            echo "$BON_READY_OUTPUT"
            echo ""
            echo "## Full Hierarchy"
            echo "$BON_LIST_OUTPUT"
        } > "$BON_FILE"
    else
        rm -f "$BON_FILE"
    fi
else
    rm -f "$BON_FILE"
fi

# === STDOUT BRIEFING ===
echo "=== SESSION ==="

# --- Greeting ---
CURRENT_HOUR=$(date +%H)
if [ "$CURRENT_HOUR" -lt 12 ]; then
    TIME_OF_DAY="morning"
elif [ "$CURRENT_HOUR" -lt 17 ]; then
    TIME_OF_DAY="afternoon"
elif [ "$CURRENT_HOUR" -lt 21 ]; then
    TIME_OF_DAY="evening"
else
    TIME_OF_DAY="night"
fi
echo "Good $TIME_OF_DAY. It's $(date '+%-d %b %Y, %H:%M')."
echo ""

# --- Bon: outcomes + zoom ---
if [ -f ".bon/items.jsonl" ] || [ -f ".arc/items.jsonl" ]; then
    # Detect which directory exists (.bon preferred)
    if [ -f ".bon/items.jsonl" ]; then
        BON_DIR=".bon"
    else
        BON_DIR=".arc"
    fi

    if [ -n "$BON_READY_OUTPUT" ]; then
        echo "Outcomes we're working towards:"
        echo "$BON_READY_OUTPUT" | while IFS= read -r line; do
            [ -n "$line" ] && echo "  $line"
        done
        echo ""
    fi

    # Zoom: show the outcome with active tactical steps (or note nothing active)
    if [ -z "$BON_CURRENT_OUTPUT" ]; then
        echo "Nothing in progress — pick an action to start."
        echo ""
    else
        # Get parent outcome from items.jsonl
        CURRENT_ACTION_ID=$(echo "$BON_CURRENT_OUTPUT" | head -1 | grep -oE '\([a-zA-Z0-9-]+\)' | tr -d '()' || true)
        if [ -n "$CURRENT_ACTION_ID" ]; then
            PARENT_ID=$(python3 -c "
import json, sys
for line in open('$BON_DIR/items.jsonl'):
    item = json.loads(line)
    if item.get('id') == '$CURRENT_ACTION_ID':
        print(item.get('parent', '')); break
" 2>/dev/null || true)
            if [ -n "$PARENT_ID" ]; then
                PARENT_TITLE=$(python3 -c "
import json
for line in open('$BON_DIR/items.jsonl'):
    item = json.loads(line)
    if item.get('id') == '$PARENT_ID':
        print(item.get('title', '')); break
" 2>/dev/null || true)
                if [ -n "$PARENT_TITLE" ]; then
                    echo "Last worked on: $PARENT_TITLE"
                    # Show actions from list output
                    PRINTING=false
                    while IFS= read -r line; do
                        if echo "$line" | grep -qF "$PARENT_ID"; then
                            PRINTING=true
                            continue
                        fi
                        if [ "$PRINTING" = true ]; then
                            if echo "$line" | grep -qE '^\s+[0-9]+\.'; then
                                TRIMMED=$(echo "$line" | sed 's/^[[:space:]]*//')
                                echo "  $TRIMMED"
                            else
                                break
                            fi
                        fi
                    done <<< "$BON_LIST_OUTPUT"
                    echo ""
                fi
            fi
        fi
    fi
elif [ -d ".bon" ] || [ -d ".arc" ]; then
    echo "Bon: directory exists but items not readable"
    echo ""
fi

# --- Handoff summary ---
if [ -n "$LATEST_FILE" ]; then
    echo "Last session ($LATEST_STR): $LATEST_PURPOSE"

    # Extract key sections from the handoff (strip blank lines before head to avoid empty-line-first bug)
    DONE_LINES=$(sed -n '/^## Done/,/^## /{/^## Done/d;/^## /d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' | head -3 | sed 's/^- //' || true)
    NEXT_LINES=$(sed -n '/^## Next/,/^## /{/^## Next/d;/^## /d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' | head -3 | sed 's/^- //' || true)
    GOTCHA_LINES=$(sed -n '/^## Gotchas/,/^## /{/^## Gotchas/d;/^## /d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' | head -2 | sed 's/^- //' || true)

    # Fallback: if no sections extracted, show first content lines
    if [ -z "$DONE_LINES" ] && [ -z "$NEXT_LINES" ] && [ -z "$GOTCHA_LINES" ]; then
        FALLBACK=$(sed -n '1,/^$/d; /^[^#]/p' "$LATEST_FILE" 2>/dev/null | head -3 || true)
        if [ -n "$FALLBACK" ]; then
            echo "  $FALLBACK"
        fi
    fi

    if [ -n "$DONE_LINES" ]; then
        echo "  Did:"
        echo "$DONE_LINES" | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
    fi
    if [ -n "$NEXT_LINES" ]; then
        echo "  Next:"
        echo "$NEXT_LINES" | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
    fi
    if [ -n "$GOTCHA_LINES" ]; then
        echo "  Watch out:"
        echo "$GOTCHA_LINES" | while IFS= read -r line; do
            [ -n "$line" ] && echo "    $line"
        done
    fi
    echo ""
fi

# --- Repo sync status (no network — uses cached remote tracking) ---
_BEHIND=0
_AHEAD=0
for dir in "$HOME/Repos"/*/; do
    [ -d "$dir/.git" ] || continue
    b=$(timeout 2s git -C "$dir" rev-list HEAD..@{u} --count 2>/dev/null || echo 0)
    a=$(timeout 2s git -C "$dir" rev-list @{u}..HEAD --count 2>/dev/null || echo 0)
    [ "$b" -gt 0 ] && _BEHIND=$((_BEHIND + 1))
    [ "$a" -gt 0 ] && _AHEAD=$((_AHEAD + 1))
done
if [ "$_BEHIND" -gt 0 ] || [ "$_AHEAD" -gt 0 ]; then
    _SYNC_MSG="Repos:"
    [ "$_BEHIND" -gt 0 ] && _SYNC_MSG="$_SYNC_MSG ${_BEHIND} pulling in background"
    [ "$_AHEAD" -gt 0 ] && _SYNC_MSG="$_SYNC_MSG | ${_AHEAD} need push"
    echo "$_SYNC_MSG"
    echo ""
fi

# --- News (only mention if present) ---
NEWS_FILE="$HOME/.claude/.update-news"
if [ -f "$NEWS_FILE" ]; then
    echo "News available: $NEWS_FILE"
fi
