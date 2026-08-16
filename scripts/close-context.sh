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

# Resolve where this session's handoff is written. The shared resolver walks
# up to the board root and prefers a visible handoffs/ over the legacy
# .bon/handoffs/ — the SAME resolution /open reads from, so a handoff is read
# from exactly where it was written.
HANDOFF_DIR=""
HANDOFF_DIR_SOURCE=""
if board_root "$CWD" >/dev/null 2>&1; then
    HANDOFF_DIR=$(handoff_write_dir "$CWD")
    HANDOFF_DIR_SOURCE="board-walkup"
fi

# Walk-up missed — cwd is not in a board repo (an owner bucket like
# ~/repos/spm1001, or ~/.claude). Scan down for child board repos via the
# shared helper (prune rules live there). The rule (bon-gojeni): exactly ONE
# candidate resolves silently; two or more is AMBIGUOUS — an owner bucket's
# siblings give no basis for choosing, and most-recent-commit is estate
# noise, not session identity (the live repro resolved to whichever repo the
# last publish had touched). In the ambiguous case HANDOFF_DIR is
# deliberately NOT emitted: the /close skill uses it verbatim, so a
# plausible-looking wrong path would relocate the trap, not close it.
SCAN_CANDIDATES=""
if [ -z "$HANDOFF_DIR" ]; then
    SCAN_CANDIDATES=$(scan_down_candidates "$CWD")
    if [ -n "$SCAN_CANDIDATES" ]; then
        if [ "$(printf '%s\n' "$SCAN_CANDIDATES" | wc -l)" -eq 1 ]; then
            HANDOFF_DIR=$(handoff_write_dir "$SCAN_CANDIDATES")
            HANDOFF_DIR_SOURCE="scan-down:$SCAN_CANDIDATES"
        else
            HANDOFF_DIR_SOURCE="ambiguous"
        fi
    fi
fi

# Fallback: global bon handoffs (never legacy ~/.claude/handoffs/). Named
# rather than silent — a handoff landing outside every repo never syncs, so
# /close has to know it took this branch. (Not on the ambiguous branch: that
# one HAS candidates; it refuses to pick among them.)
if [ -z "$HANDOFF_DIR" ] && [ "$HANDOFF_DIR_SOURCE" != "ambiguous" ]; then
    HANDOFF_DIR="$HOME/.bon/handoffs"
    HANDOFF_DIR_SOURCE="global-fallback"
fi

# Always output HANDOFF_DIR and SESSION_ID - even containers need handoffs.
# Except ambiguous: no dir is chosen, the candidate list IS the output.
if [ "$HANDOFF_DIR_SOURCE" = "ambiguous" ]; then
    echo "HANDOFF_DIR_SOURCE=ambiguous"
    while IFS= read -r cand; do
        echo "HANDOFF_CANDIDATE=$cand"
    done <<< "$SCAN_CANDIDATES"
    echo "HANDOFF_HINT=multiple sibling board repos under cwd and no basis to choose between them. Placement is WORK-based: pick the repo this session actually worked, then write into its handoffs dir (visible handoffs/ if present, else .bon/handoffs/)."
else
    echo "HANDOFF_DIR=$HANDOFF_DIR"
    echo "HANDOFF_DIR_SOURCE=$HANDOFF_DIR_SOURCE"
fi

# === SESSION IDENTITY ===
# The harness hands every session its own id. Ambient state does not.
#
# This was `ls -t` over the project's JSONL dir, which returns whoever WROTE
# most recently — a race readout, not an identity. Under concurrent sessions
# it handed four sessions a stranger's id in nine days (bon-casovo) and
# escaped destroying a completed handoff three times by luck. The id suffix
# exists FOR transcript linkage, so a wrong id is strictly worse than no id:
# it sends a future deglacer lookup confidently into the wrong conversation.
#
# CLAUDE_CODE_SESSION_ID is the caller's own id, verified present and correct
# on the interactive `cli` surface from a clean parent environment (hublot,
# 2026-08-03 — the value matched the session's own transcript filename, on
# both a polluted and a scrubbed parent). The absent branch is therefore
# vestigial, and it FAILS LOUD rather than guessing.
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
if [ -n "$SESSION_ID" ]; then
    SESSION_ID_SOURCE="env:CLAUDE_CODE_SESSION_ID"
else
    SESSION_ID_SOURCE="unavailable"
fi
echo "SESSION_ID=${SESSION_ID}"
echo "SESSION_ID_SOURCE=${SESSION_ID_SOURCE}"

# Generate handoff filename: YYYY-MM-DD-{first 8 chars of session ID}.md
TODAY=$(date +%Y-%m-%d)
if [ -n "$SESSION_ID" ]; then
    HANDOFF_BASE="${TODAY}-${SESSION_ID:0:8}"
else
    HANDOFF_BASE="${TODAY}-$(date +%H%M)"
    echo "SESSION_ID_CUE=could not determine this session's id — the filename carries a timestamp instead of a transcript-linkable id. Do NOT invent one: leave session_id blank in the handoff frontmatter and say so in the close summary."
fi

# Never hand back a path that already holds a handoff. The Write tool refuses
# to clobber a file it has not read — but a session that COMPUTED the path has
# not read it, so that protection does not apply and the guard has to live
# here. With a real session id a collision means this session is closing twice
# in one day, which is legitimate: suffix rather than refuse, and name the
# collision so the other reading (something still deriving ids from ambient
# state) stays visible instead of being silently absorbed.
HANDOFF_FILE="${HANDOFF_BASE}.md"
if [ -e "$HANDOFF_DIR/$HANDOFF_FILE" ]; then
    echo "HANDOFF_FILE_TAKEN=$HANDOFF_FILE"
    SUFFIX=2
    while [ "$SUFFIX" -lt 100 ] && [ -e "$HANDOFF_DIR/${HANDOFF_BASE}-${SUFFIX}.md" ]; do
        SUFFIX=$((SUFFIX + 1))
    done
    HANDOFF_FILE="${HANDOFF_BASE}-${SUFFIX}.md"
fi
echo "HANDOFF_FILE=$HANDOFF_FILE"

# A repo can gitignore `.bon/` wholesale to keep volatile board state out of
# git — which also catches handoffs and understanding.md. `git add` then
# refuses, and the handoff is written to disk but never syncs, so the next
# session on another machine cannot see it (bon-kizeje; live in mit-plongeur,
# whose 13 handoffs are all force-added by hand). Detect it here so /close
# force-adds deliberately rather than depending on someone noticing.
if [ -n "$HANDOFF_DIR" ]; then
    IGNORE_PROBE="$HANDOFF_DIR"
    while [ ! -d "$IGNORE_PROBE" ] && [ "$IGNORE_PROBE" != "/" ]; do
        IGNORE_PROBE=$(dirname "$IGNORE_PROBE")
    done
    if git -C "$IGNORE_PROBE" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        && git -C "$IGNORE_PROBE" check-ignore -q "$HANDOFF_DIR/$HANDOFF_FILE" 2>/dev/null; then
        echo "HANDOFF_GITIGNORED=true"
        echo "HANDOFF_ADD_CMD=git add -f -- $HANDOFF_DIR/$HANDOFF_FILE"
    fi
fi

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

# === ROOMS INDEX (bon-walile) ===
# Eager regen: if the worked repo has ADOPTED a rooms.md (a drift-proof
# existence index of its CLAUDE.md rooms), refresh it so it rides this close's
# commit — same-session freshness. Adoption is opt-in by the file's presence:
# repos without a rooms.md are left untouched (no churn — the trap a
# SessionStart hook would fall into). The nightly Hezza timer is the
# all-surface guarantee; this is only the eager half. Fully guarded so a
# generator hiccup can never abort /close (the script runs under `set -e`).
echo ""
echo "=== ROOMS ==="
ROOMS_REPO=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -n "$ROOMS_REPO" ] && [ -f "$ROOMS_REPO/rooms.md" ]; then
    GEN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gen-rooms.py"
    if [ -f "$GEN" ] && command -v python3 &>/dev/null; then
        if python3 "$GEN" "$ROOMS_REPO" >/dev/null 2>&1; then
            echo "ROOMS_REGENERATED=$ROOMS_REPO/rooms.md"
        else
            echo "ROOMS_REGENERATED=false (generator error — non-fatal)"
        fi
    else
        echo "ROOMS_REGENERATED=false (generator unavailable)"
    fi
else
    echo "ROOMS_ADOPTED=false"
fi

# === DATE ===
echo ""
echo "=== META ==="
echo "TODAY=$(date +%Y-%m-%d)"
