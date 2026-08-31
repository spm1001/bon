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

# === BOARD MOTION (bon-racafo) ===
# Cards closed versus cards minted since the previous close. Sessions file
# discoveries rather than chase them — correctly — so a productive session
# quietly replenishes the board, and that residue has to be SEEN rather than
# left implicit in the per-item notes.
#
# The counts are DERIVED here, never narrated by the closing Claude. That is
# the point: this card's falsifier is evasive behaviour when nobody is
# watching, whose scoreboard face is pressure to close rather than file
# honestly, and an agent cannot inflate a count it did not compute. Two more
# properties earn their keep for the same reason — every id is NAMED, so a
# suppressed filing is visible to anyone who scrolls; and CARRIED (minted in
# the window and still open) sits beside the totals so a card minted and
# closed within the session cannot read as board growth.
#
# Callable twice on purpose. The full script runs at Orient, but /close mints
# new bons and closes knocked-out ones later, in Act — so an Orient-time tally
# would undercount exactly the filings this exists to surface, and in the one
# direction the falsifier cares about. `--motion-only <since>` re-derives it
# at summary time from one source of truth rather than a copy in skill prose.
emit_board_motion() {
    local since="$1" root="$2" cmd="$3"
    (cd "$root" && "$cmd" log -n 500 --json 2>/dev/null) \
        | MOTION_SINCE="$since" python3 -c '
import json, os, sys

since = os.environ["MOTION_SINCE"]
try:
    events = json.load(sys.stdin)
except Exception:
    print("MOTION_ERROR=could not read bon log — state the tally as unavailable")
    sys.exit(0)

# bon log stamps UTC with a trailing Z, and `since` is UTC too — the caller
# converts, because handoff filenames carry LOCAL time. Both sides UTC means
# the string compare is a real instant comparison rather than a coincidence.
window = [e for e in events if (e.get("time") or "").rstrip("Z") >= since]
closed = sorted({e["id"] for e in window if e.get("verb") == "completed"})
minted = sorted({e["id"] for e in window if e.get("verb") == "created"})
carried = sorted(set(minted) - set(closed))

print(f"MOTION_CLOSED={len(closed)}" + (" " + ", ".join(closed) if closed else ""))
print(f"MOTION_MINTED={len(minted)}" + (" " + ", ".join(minted) if minted else ""))
print(f"MOTION_CARRIED={len(carried)}" + (" " + ", ".join(carried) if carried else ""))
# The cap only hides something if the OLDEST event returned is still inside
# the window; otherwise the log reached past it and the counts are exact.
# A cap that cannot have trimmed anything must not cry wolf.
if len(events) >= 500 and events and (events[-1].get("time") or "").rstrip("Z") >= since:
    print("MOTION_TRUNCATED=true — the log cap was reached and the oldest "
          "event is still inside the window, so these counts are floors")
'
}

# Handoff FILENAMES carry local time (`date +%H%M`); `bon log` stamps UTC with
# a trailing Z. Comparing them as one clock silently drops the first hour of
# every window under BST, and double-counts under GMT — measured live on
# 2026-08-31, when an item minted half an hour after the previous close
# reported MOTION_MINTED=0. Worse, at-close filings land minutes after Orient,
# so their UTC stamps sit up to an hour BEFORE the next window's local-time
# boundary: they would have been invisible to both tallies, which is exactly
# the filing this feature exists to make visible.
#
# Input "YYYY-MM-DD HH:MM:SS" in LOCAL time; output the same instant in UTC.
# Two-step via epoch because BSD `date -u -j -f` reads its INPUT as UTC too,
# so the one-liner that works on tube would be wrong on the Macs this ships to.
_local_to_utc() {
    local epoch
    epoch=$(date -d "$1" +%s 2>/dev/null) \
        || epoch=$(date -j -f '%Y-%m-%d %H:%M:%S' "$1" +%s 2>/dev/null) \
        || return 1
    date -u -d "@$epoch" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null \
        || date -u -r "$epoch" '+%Y-%m-%dT%H:%M:%S' 2>/dev/null
}

if [ "${1:-}" = "--motion-only" ]; then
    MOTION_SINCE_ARG="${2:-}"
    if [ -z "$MOTION_SINCE_ARG" ]; then
        echo "MOTION_ERROR=--motion-only needs the MOTION_SINCE value the full run printed"
        exit 2
    fi
    MROOT=$(board_root "$(pwd -P)") || {
        echo "MOTION_ERROR=no board found from $(pwd -P)"; exit 0
    }
    MCMD=$(command -v bon 2>/dev/null || echo "$HOME/repos/spm1001/bon/.venv/bin/bon")
    if [ ! -x "$MCMD" ]; then
        echo "MOTION_ERROR=bon CLI not found"; exit 0
    fi
    echo "=== BOARD MOTION ==="
    echo "MOTION_SINCE=$MOTION_SINCE_ARG (re-derived at summary time)"
    emit_board_motion "$MOTION_SINCE_ARG" "$MROOT" "$MCMD"
    exit 0
fi

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
# Board root via lib-handoff's shared resolver: at CWD any .bon counts;
# above it only one with a prefix file (skips bare handoff stashes like
# ~/.bon); a .git boundary stops the walk so a nested repo never adopts an
# outer repo's board. This file used to carry its own byte-alike copy of that
# walk, and bon-racafo briefly added a third — one rule, one reader.
BON_ROOT=$(board_root "$(pwd -P)" || true)

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

# Converge any legacy .bon/handoffs pile onto the visible convention before
# resolving (bon-sedoze). /open does the same on the way in; doing it here too
# covers the repo whose next contact with bon is a close rather than an open.
# The scan-down branch below migrates again, for the case this call cannot
# reach — the two are mutually exclusive, so the keys emitted after the
# resolution block always describe whichever one actually ran.
handoff_migrate_legacy "$CWD"

# Resolve where this session's handoff is written. The shared resolver walks
# up to the board root and picks the nearest visible handoffs/, defaulting to
# the board root's — the SAME resolution /open reads from, so a handoff is
# read from exactly where it was written.
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
            # cwd sits ABOVE this board, so the migration call earlier — which
            # walks UP from cwd — never saw it. Converge the child we are about
            # to write into, BEFORE resolving where that write lands, or the new
            # handoff joins a visible dir while the old pile stays stranded in a
            # location nothing reads any more (bon-sedoze).
            handoff_migrate_legacy "$SCAN_CANDIDATES"
            HANDOFF_DIR=$(handoff_write_dir "$SCAN_CANDIDATES")
            HANDOFF_DIR_SOURCE="scan-down:$SCAN_CANDIDATES"
        else
            # Ambiguous: we refuse to pick a repo, so we refuse to migrate one
            # too. Each converges on its own next open or close.
            HANDOFF_DIR_SOURCE="ambiguous"
        fi
    fi
fi

# Report the convergence (whichever call above ran — they are exclusive).
if [ "${HANDOFF_MIGRATED_N:-0}" -gt 0 ]; then
    echo "HANDOFF_MIGRATED=$HANDOFF_MIGRATED_N"
    echo "HANDOFF_MIGRATED_DEST=$HANDOFF_MIGRATED_DEST"
fi
if [ "${HANDOFF_MIGRATED_FAILED:-0}" -eq 1 ]; then
    echo "HANDOFF_MIGRATE_INCOMPLETE=true"
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
    echo "HANDOFF_HINT=multiple sibling board repos under cwd and no basis to choose between them. Placement is WORK-based: pick the repo this session actually worked, then write into its visible handoffs/ (at the room you worked, else the repo root)."
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

# Generate handoff filename: YYYY-MM-DD-HHMM-{first 8 chars of session ID}.md
# (v4, notes-sovike: HHMM so same-day siblings sort chronologically under a
# plain `ls` — the id8 is random, so without it the SUPERSEDED file could sort
# last. The reader also prefers this filename time over mtime on same-day
# ties, because clones and sync rebases flatten mtimes.)
TODAY=$(date +%Y-%m-%d)
# BON_TEST_NOW_HM: tests pin the minute so expected filenames aren't a race
# against the wall clock (same seam as the HOME isolation they already use).
NOW_HM="${BON_TEST_NOW_HM:-$(date +%H%M)}"
if [ -n "$SESSION_ID" ]; then
    HANDOFF_BASE="${TODAY}-${NOW_HM}-${SESSION_ID:0:8}"
else
    HANDOFF_BASE="${TODAY}-${NOW_HM}"
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

# Window for the tally: the newest handoff's filename date prefix. Fixed-width
# and string-sortable across both the dated and the dated+HHMM conventions, and
# deliberately not mtime — clones and sync rebases flatten mtimes (bon-wakaju).
# Note this window is "since the previous close", not "since this session
# started", which is wider on purpose: per-session windows leave gaps that
# nobody counts, and the label says which window it is.
if [ -n "${BON_ROOT:-}" ] && [ -n "${BON_CMD:-}" ] && [ -x "$BON_CMD" ]; then
    MOTION_SINCE=""
    MOTION_SINCE_SRC="fallback"
    if [ -n "${HANDOFF_DIR:-}" ] && [ -d "$HANDOFF_DIR" ]; then
        # `|| true` is load-bearing under `set -euo pipefail`: a grep matching
        # nothing exits 1, pipefail propagates it, and set -e then kills the
        # whole script mid-output — the bon-cuvice death, which took every
        # section after this one with it until a test caught it. Capture, then
        # test the RESULT for emptiness rather than the pipeline for success.
        LAST_HANDOFF=$(ls -1 "$HANDOFF_DIR" 2>/dev/null \
            | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort | tail -1 || true)
        if [ -n "$LAST_HANDOFF" ]; then
            MOTION_DATE="${LAST_HANDOFF:0:10}"
            case "$LAST_HANDOFF" in
                [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]-*)
                    MOTION_HHMM="${LAST_HANDOFF:11:4}"
                    MOTION_SINCE=$(_local_to_utc \
                        "$MOTION_DATE ${MOTION_HHMM:0:2}:${MOTION_HHMM:2:2}:00") || MOTION_SINCE=""
                    ;;
                *)
                    MOTION_SINCE=$(_local_to_utc "$MOTION_DATE 00:00:00") \
                        || MOTION_SINCE=""
                    ;;
            esac
            MOTION_SINCE_SRC="previous handoff ($LAST_HANDOFF)"
        fi
    fi
    if [ -z "$MOTION_SINCE" ]; then
        MOTION_SINCE=$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%S' 2>/dev/null \
            || date -u -v-24H '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || echo "")
        # Two different reasons land here and they want different messages: no
        # dated handoff at all, versus one whose timestamp would not convert
        # (a local time that does not exist on a DST-skip day, or a malformed
        # name). Saying "none found" when one WAS found points a future
        # debugger away from the cause, while the window itself stays honest.
        if [ -n "${LAST_HANDOFF:-}" ]; then
            MOTION_SINCE_SRC="last 24h — $LAST_HANDOFF has an unconvertible timestamp (window is not this session)"
        else
            MOTION_SINCE_SRC="last 24h (no dated handoff found — window is not this session)"
        fi
    fi

    if [ -n "$MOTION_SINCE" ]; then
        echo ""
        echo "=== BOARD MOTION ==="
        echo "MOTION_SINCE=$MOTION_SINCE ($MOTION_SINCE_SRC)"
        emit_board_motion "$MOTION_SINCE" "$BON_ROOT" "$BON_CMD"
    fi
fi

# (The HANDOFF_GITIGNORED / HANDOFF_ADD_CMD force-add probe lived here until
# bon-sedoze. It existed for one shape: a repo gitignoring `.bon/` wholesale,
# which also swallowed the handoff underneath it. Handoffs no longer live
# under `.bon/`, so the shape is gone. `bon doctor`'s sync-hazard advisory
# still covers the artefacts that DO remain there — understanding.md, the
# bottle, and a JSONL board.)

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

# === PERSONAL HALF (bon-hedatu) ===
# Emitted only when the operator's accent file exists — an absent accent is
# a complete rite, not a gap (docs/ACCENT.md, law 1). The close skill reads
# its ## close section at the tap slot.
if [ -f "$HOME/.claude/mit-accent.md" ]; then
    echo "ACCENT=$HOME/.claude/mit-accent.md"
fi
