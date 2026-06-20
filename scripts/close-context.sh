#!/bin/bash
# Consolidated context gathering for /close
# Outputs structured sections for Claude to parse

set -euo pipefail

# === SELF-VALIDATION ===
# Check critical dependencies before running. Fail fast with clear messages.
validate_dependencies() {
    local missing=""

    # python3: required for JSON parsing
    if ! command -v python3 &>/dev/null; then
        missing="$missing python3"
    fi

    if [ -n "$missing" ]; then
        echo "=== SCRIPT_ERROR ==="
        echo "ERROR: close-context.sh missing dependencies:$missing"
        echo "Install missing tools and retry."
        echo "SCRIPT_FAILED=true"
        exit 1
    fi
}

validate_dependencies

# Shared handoff/understanding.md resolution — keeps this WRITER and the
# /open READER (open-context.sh) in lockstep on the same convention.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-handoff.sh"

# === TIME ===
echo "=== TIME ==="
CURRENT_HOUR=$(date +%H)
CURRENT_DATE=$(date '+%Y-%m-%d')
CURRENT_TIME=$(date '+%H:%M')

if [ "$CURRENT_HOUR" -lt 12 ]; then
    TIME_OF_DAY="morning"
elif [ "$CURRENT_HOUR" -lt 17 ]; then
    TIME_OF_DAY="afternoon"
elif [ "$CURRENT_HOUR" -lt 21 ]; then
    TIME_OF_DAY="evening"
else
    TIME_OF_DAY="night"
fi

echo "NOW=$CURRENT_DATE $CURRENT_TIME"
echo "TIME_OF_DAY=$TIME_OF_DAY"
echo "YEAR=$(date +%Y)"
echo ""

# === GIT STATUS ===
echo "=== GIT ==="
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    DIRTY=$(git status --porcelain 2>/dev/null || true)
    UNPUSHED=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
    LAST_MSG=$(git log -1 --format='%s' 2>/dev/null || echo "")

    if [ -n "$DIRTY" ]; then
        FILE_COUNT=$(echo "$DIRTY" | wc -l | tr -d ' ')
        echo "UNCOMMITTED=$FILE_COUNT"
        echo "FILES:"
        echo "$DIRTY" | head -10
    else
        echo "UNCOMMITTED=0"
    fi

    echo "UNPUSHED=$UNPUSHED"
    [ -n "$LAST_MSG" ] && echo "LAST_COMMIT=$LAST_MSG"
    echo "GIT_EXISTS=true"
    # A worktree session's branch (commits AND handoffs) vanishes with the
    # worktree — surface it so /close escapes before declaring done
    case "$(pwd -P)" in
        *"/.claude/worktrees/"*)
            echo "WORKTREE_SESSION=true"
            echo "WORKTREE_RESCUE=push, merge, or PR this branch before ending the session — commits and handoffs here are deleted with the worktree"
            ;;
    esac
else
    echo "GIT_EXISTS=false"
fi

# === BON STATUS (default tracker) ===
echo ""
echo "=== BON ==="
# Walk up to the board root, mirroring the CLI's discovery: at CWD any
# .bon counts; above it only one with a prefix file (skips bare handoff
# stashes like ~/.bon); a .git boundary stops the walk so a nested repo
# never adopts an outer repo's board.
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
    # Find bon CLI - check PATH first, then known location
    BON_CMD=$(command -v bon 2>/dev/null || echo "$HOME/repos/spm1001/bon/.venv/bin/bon")

    if [ -x "$BON_CMD" ]; then
        # Bon doesn't track in_progress, but we can show open and waiting items
        # (run from the board root: the current CLI walks up itself, older ones don't)
        OPEN_OUTPUT=$(cd "$BON_ROOT" && "$BON_CMD" list 2>/dev/null || true)
        OPEN_COUNT=$(echo "$OPEN_OUTPUT" | grep -c "^○" 2>/dev/null) || OPEN_COUNT=0
        # ⏳ is a mid-line suffix on waiting items (never line-start),
        # on outcomes and actions alike — count lines containing it
        WAITING_COUNT=$(echo "$OPEN_OUTPUT" | grep -c "⏳" 2>/dev/null) || WAITING_COUNT=0

        echo "OPEN_COUNT=$OPEN_COUNT"
        echo "WAITING_COUNT=$WAITING_COUNT"
        if [ -n "$OPEN_OUTPUT" ]; then
            echo "ITEMS:"
            echo "$OPEN_OUTPUT"
        fi
        echo "BON_EXISTS=true"
    else
        echo "BON_EXISTS=false"
        echo "BON_ERROR=cli_not_found"
    fi
else
    echo "BON_EXISTS=false"
fi

# === WORK LOCATION DETECTION ===
echo ""
echo "=== LOCATION ==="
CWD=$(pwd -P)  # -P resolves symlinks for consistent encoding

# Check if cwd is a container directory
# Uses [[ ]] for glob pattern matching (case doesn't expand globs)
is_container() {
    [[ "$1" == "$HOME/Repos" ]] && return 0
    [[ "$1" == "$HOME/.claude" ]] && return 0
    [[ "$1" == "$HOME/Library/CloudStorage/GoogleDrive-"*"/My Drive/Work" ]] && return 0
    return 1
}

# Encoded path always starts with '-' — never use as bare arg; always prefix with absolute path
ENCODED_PATH=$(echo "$CWD" | sed 's/[^a-zA-Z0-9-]/-/g')

# Resolve where this session's handoff is written. The shared resolver walks
# up to the board root and prefers a visible handoffs/ over the legacy
# .bon/handoffs/ — the SAME resolution /open reads from, so a handoff is read
# from exactly where it was written.
HANDOFF_DIR=""
if board_root "$CWD" >/dev/null 2>&1; then
    HANDOFF_DIR=$(handoff_write_dir "$CWD")
fi

# Walk-up missed — container dir (e.g. ~/Repos) where work happened in a child
# repo. Scan down for the repo with the most recent commit, then resolve its
# handoff dir visible-first via the same helper.
if [ -z "$HANDOFF_DIR" ]; then
    BEST_REPO=""
    BEST_TIME=0
    while IFS= read -r bon_dir; do
        repo_dir=$(dirname "$bon_dir")
        # Skip non-git dirs (e.g. pytest temp dirs)
        git -C "$repo_dir" rev-parse --git-dir &>/dev/null || continue
        latest=$(git -C "$repo_dir" log -1 --format=%ct 2>/dev/null || echo "0")
        latest=${latest:-0}
        if [ "$latest" -gt "$BEST_TIME" ]; then
            BEST_TIME=$latest
            BEST_REPO="$repo_dir"
        fi
    done < <(find "$CWD" -maxdepth 4 -name ".bon" -type d 2>/dev/null)
    [ -n "$BEST_REPO" ] && HANDOFF_DIR=$(handoff_write_dir "$BEST_REPO")
fi

# Fallback: global bon handoffs (never legacy ~/.claude/handoffs/)
[ -z "$HANDOFF_DIR" ] && HANDOFF_DIR="$HOME/.bon/handoffs"

# Always output HANDOFF_DIR and SESSION_ID - even containers need handoffs
echo "HANDOFF_DIR=$HANDOFF_DIR"
SESSION_ID=$(ls -t "$HOME/.claude/projects/$ENCODED_PATH"/*.jsonl 2>/dev/null \
    | grep -v agent \
    | head -1 \
    | xargs -I{} basename {} .jsonl 2>/dev/null \
    || true)
echo "SESSION_ID=${SESSION_ID}"

# Generate handoff filename: YYYY-MM-DD-{first 8 chars of session ID}.md
TODAY=$(date +%Y-%m-%d)
if [ -n "$SESSION_ID" ]; then
    HANDOFF_FILE="${TODAY}-${SESSION_ID:0:8}.md"
else
    HANDOFF_FILE="${TODAY}-$(date +%H%M).md"
fi
echo "HANDOFF_FILE=$HANDOFF_FILE"

if is_container "$CWD"; then
    echo "IS_CONTAINER=true"
    echo "CWD=$CWD"

    # Find repos with today's commits
    echo "RECENT_WORK:"
    for dir in "$HOME/Repos"/* "$HOME/.claude"; do
        if [ -e "$dir/.git" ]; then
            if git -C "$dir" log --since="midnight" --oneline 2>/dev/null | head -1 | grep -q .; then
                echo "  $dir"
            fi
        fi
    done
else
    echo "IS_CONTAINER=false"
    echo "CWD=$CWD"
    echo "HANDOFF_TARGET=$CWD"
fi

# === DATE ===
echo ""
echo "=== META ==="
echo "TODAY=$(date +%Y-%m-%d)"
