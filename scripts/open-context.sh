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
if date -d '2000-01-01' +%s &>/dev/null; then
    date_to_epoch() { date -d "$1" +%s; }
    epoch_day() { date -d "@$1" +%Y-%m-%d; }
    epoch_hhmm() { date -d "@$1" +%H%M; }
else
    date_to_epoch() { date -j -f '%Y-%m-%d' "$1" +%s; }
    epoch_day() { date -r "$1" +%Y-%m-%d; }
    epoch_hhmm() { date -r "$1" +%H%M; }
fi

# === PREVIEW BUDGET (bon-peluge, bon-tebete) ===
# Claude Code previews only the first ~2KB of hook output. Every section that
# can grow with the board is capped here; nothing is emitted unbounded (the
# handoff body was the last such section — see section 8). Measured 2026-08-04
# on this board: the whole briefing is 2666 bytes, and 2600 bytes of output was
# observed arriving inline and complete, so ~2KB is the PREVIEW size and the
# persist threshold sits above it. Caps are therefore guards against a much
# larger board, not trims of this one.
STANDALONE_MAX=12
OUTCOME_MAX=12
SUGGESTED_MAX=6
UNPROCESSED_MAX=6

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

# Shared handoff/understanding.md resolution — keeps this READER and the
# /close WRITER (close-context.sh) in lockstep on the same convention.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-handoff.sh"

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

# === LEGACY HANDOFF CONVERGENCE (bon-sedoze) ===
# Runs BEFORE resolution: the .bon/handoffs rung is gone, so a repo still
# carrying a pile there would otherwise open with its whole history invisible
# and no line saying why. Migrating first means this session reads the
# migrated location. Announced, never silent — it moves files in the user's
# working tree, and they need to know to commit them.
handoff_migrate_legacy "$CWD"
if [ "${HANDOFF_MIGRATED_N:-0}" -gt 0 ]; then
    echo "Migrated $HANDOFF_MIGRATED_N legacy handoff(s) from .bon/handoffs/ to $HANDOFF_MIGRATED_DEST"
    echo "  (bon now keeps handoffs visible at the board root — commit the move with your next change.)"
    echo ""
fi
if [ "${HANDOFF_MIGRATED_FAILED:-0}" -eq 1 ]; then
    echo "Warning: could not migrate every handoff out of .bon/handoffs/ — the ones left there are NOT read any more."
    echo "  Move them into the repo's visible handoffs/ by hand."
    echo ""
fi

# === LOCAL HANDOFF WARNING ===
LOCAL_HANDOFFS=$(find . -maxdepth 1 -name '.handoff*' 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOCAL_HANDOFFS" -gt 0 ]; then
    echo "Warning: $LOCAL_HANDOFFS orphaned local .handoff* files (should move to the repo's handoffs/)"
    echo ""
fi

# === GATHER TO DISK (silent) ===

# --- Handoff resolution ---
# Primary: every visible handoffs/ walking up from CWD to the board root
# Fallback: ~/.bon/handoffs/ (global, for container sessions)
NOW=$(date +%s)

# Handoff dirs to search come from the shared resolver, so /open reads from
# exactly where /close writes. Fixes the 2026-06-17 bug where a newer handoff
# in a visible root handoffs/ was invisible to /open because it only ever
# looked in .bon/handoffs/ — the rung that is now retired at the other end
# (bon-sedoze), with handoff_migrate_legacy above converging any pile that
# still sits there.

# Find the most recent handoff across all candidate locations
LATEST_FILE=""
LATEST_PURPOSE=""
LATEST_STR=""

# Rank by the date in the handoff header ("# Handoff — YYYY-MM-DD"), with
# write-time breaking same-day ties: the filename's HHMM where the v4 scheme
# (YYYY-MM-DD-HHMM-…) carries one, else HHMM derived from mtime, then raw
# mtime. Never mtime-first: a fresh clone flattens every mtime to checkout
# time, so mtime-first picks an arbitrary (often ancient) handoff — and the
# same flattening is why a filename HHMM outranks the mtime-derived one on
# same-day ties (notes-sovike).
# Emits "sortkey|path"; header-less files rank by mtime alone at the bottom.
find_latest_in() {
    local dir="$1" best_key="" best_file="" f d mt hm key
    [ -d "$dir" ] || return 0
    for f in "$dir"/*.md; do
        [ -e "$f" ] || continue
        # The ledger is an index, not a handoff — and being touched by
        # every close and every tick it is mtime-newest, so in a dir of
        # headerless handoffs it would WIN the ranking (essayeur, 2026-08-30).
        case "$(basename "$f")" in LEDGER.md) continue ;; esac
        d=$(sed -n 's/^# Handoff — \([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\).*/\1/p' "$f" 2>/dev/null | head -1)
        [ -z "$d" ] && d="0000-00-00"
        mt=$(file_mtime "$f")
        hm=$(basename "$f" | sed -n 's/^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}-\([0-9]\{4\}\)\(-.*\)\{0,1\}\.md$/\1/p')
        [ -z "$hm" ] && hm=$(epoch_hhmm "$mt")
        key=$(printf '%s.%s.%012d' "$d" "$hm" "$mt")
        if [ -z "$best_key" ] || [ "$key" \> "$best_key" ]; then
            best_key="$key"
            best_file="$f"
        fi
    done
    # An if-block, NOT `[ -n "$best_file" ] && echo` — as the function's last
    # command that idiom returns 1 on an empty dir, and `CANDIDATE=$(...)`
    # under `set -euo pipefail` then kills this script before ANY briefing
    # reaches stdout. session-start.sh wraps the call in `|| true`, so the
    # symptom is a session that silently gets no briefing at all, every time.
    # (lib-handoff.sh's header bans the same idiom for the same reason.)
    if [ -n "$best_file" ]; then echo "${best_key}|${best_file}"; fi
    return 0
}

# Rank the latest handoff across every candidate dir (de-duplicated, order
# preserved). A room's handoffs/ and the board root's compete on the same
# header-date key, so a repo with prose at several levels surfaces the
# genuinely newest regardless of where it sits.
BEST_KEY=""
while IFS= read -r HDIR; do
    [ -d "$HDIR" ] || continue
    CANDIDATE=$(find_latest_in "$HDIR")
    [ -n "$CANDIDATE" ] || continue
    KEY="${CANDIDATE%%|*}"
    FILE="${CANDIDATE#*|}"
    if [ -z "$BEST_KEY" ] || [ "$KEY" \> "$BEST_KEY" ]; then
        BEST_KEY="$KEY"
        LATEST_FILE="$FILE"
    fi
done < <(handoff_read_dirs "$CWD" | awk '!seen[$0]++')

if [ -n "$LATEST_FILE" ]; then
    LATEST_TIME=$(file_mtime "$LATEST_FILE")
    # Display age from the HEADER date, not mtime: a clone flattens every
    # mtime to checkout time, so mtime-age reads as days-since-clone — a
    # 2026-03-30 handoff was shown as "26d ago" (bon-wakaju). The 2026-06
    # ranking fix covered selection only; this covers display. mtime keeps
    # the finer granularity when its calendar day agrees with the header.
    HDR_DAY="${BEST_KEY%%.*}"
    if [ "$HDR_DAY" != "0000-00-00" ] && [ "$(epoch_day "$LATEST_TIME")" != "$HDR_DAY" ]; then
        HDR_EPOCH=$(date_to_epoch "$HDR_DAY" 2>/dev/null || true)
        [ -n "$HDR_EPOCH" ] && LATEST_TIME="$HDR_EPOCH"
    fi
    LATEST_AGO=$((NOW - LATEST_TIME))
    LATEST_STR=$(time_ago $LATEST_AGO)
    LATEST_PURPOSE=$(grep "^purpose:" "$LATEST_FILE" 2>/dev/null | head -1 | cut -d: -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' || true)
    if [ -z "$LATEST_PURPOSE" ]; then
        LATEST_PURPOSE=$(grep -A1 "^## Done" "$LATEST_FILE" 2>/dev/null | tail -1 | sed 's/^- //' | cut -c1-60 || true)
    fi
fi

# --- Unprocessed handoffs (bon-supuko) ---
# The sweep replaces latest-wins. Every close appends an unticked ledger
# line ('- [ ] date [file](file) — purpose') to its handoff dir's
# LEDGER.md; /open processes EVERY unticked line (synthesis + candidate
# minting are batch-safe) and ticks each. Latest-wins silently dropped
# the older of two interleaved closes — its For-Claudes-to-come never
# synthesised, its Candidates never minted, nothing said so (the
# Judi 11:00 / Stef 12:30 scenario, common-core design 2026-08-29).
# Lines without a checkbox are legacy prior art (~/notes) and count as
# processed; a handoff in no ledger at all is covered by latest-wins only.
UNPROCESSED_PATHS=""
UNPROCESSED_MISSING=0
LEDGER_DRIFT=0
while IFS= read -r HDIR; do
    # The global stash serves container sessions and holds OTHER repos'
    # history — sweeping it would synthesise foreign handoffs into this
    # repo's understanding.md. Latest-wins still reads it, unchanged.
    if [ "$HDIR" = "$HOME/.bon/handoffs" ]; then continue; fi
    [ -f "$HDIR/LEDGER.md" ] || continue
    PARSED_COUNT=0
    while IFS= read -r TARGET; do
        [ -n "$TARGET" ] || continue
        PARSED_COUNT=$((PARSED_COUNT + 1))
        case "$TARGET" in
            /*) FPATH="$TARGET" ;;
            *)  FPATH="$HDIR/$TARGET" ;;
        esac
        if [ -f "$FPATH" ]; then
            UNPROCESSED_PATHS="${UNPROCESSED_PATHS}${FPATH}"$'\n'
        else
            UNPROCESSED_MISSING=$((UNPROCESSED_MISSING + 1))
        fi
    done < <(sed -n 's/^- \[ \][^][]*\[[^]]*\](\([^)]*\)).*/\1/p' "$HDIR/LEDGER.md")
    # A checkbox line the parser could not read is an unticked handoff
    # nothing will sweep — drifted format, silent-open failure direction.
    RAW_UNTICKED=$(grep -c '^[-*] \[ \]' "$HDIR/LEDGER.md" 2>/dev/null || true)
    RAW_UNTICKED=${RAW_UNTICKED:-0}
    if [ "$RAW_UNTICKED" -gt "$PARSED_COUNT" ]; then
        LEDGER_DRIFT=$((LEDGER_DRIFT + RAW_UNTICKED - PARSED_COUNT))
    fi
    # The un-ledgered net: a handoff file NO ledger line mentions at all —
    # a pre-ledger plugin's close, a close that forgot its append, a
    # hand-dropped file. Without this, one coexisting unticked line closes
    # the latest-wins fallback and the file becomes permanently unreachable
    # after the next ledgered close (essayeur refutation, 2026-08-30).
    # Substring match on the basename, so drifted line formats still count
    # as "mentioned".
    for F in "$HDIR"/*.md; do
        [ -e "$F" ] || continue
        BASE=$(basename "$F")
        # README.md: a dir-level readme is index prose, not a handoff.
        case "$BASE" in LEDGER.md|README.md) continue ;; esac
        if ! grep -qF "$BASE" "$HDIR/LEDGER.md"; then
            UNPROCESSED_PATHS="${UNPROCESSED_PATHS}${F} [no ledger line — process, then ADD a ticked line for it]"$'\n'
        fi
    done
done < <(handoff_read_dirs "$CWD" | awk '!seen[$0]++')
# Oldest first (filenames lead YYYY-MM-DD-HHMM, so basename sort is
# chronological) — the sweep processes in write order.
if [ -n "$UNPROCESSED_PATHS" ]; then
    UNPROCESSED_PATHS=$(printf '%s' "$UNPROCESSED_PATHS" | awk -F/ '{print $NF "\t" $0}' | sort | cut -f2-)
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

# --- 2. Handoff pointer (the body itself is not emitted — see section 8) ---
# Claude Code persists oversized hook output and previews only the first ~2KB.
# The handoff body used to sit HERE, spending that entire budget on its Done
# bullets and pushing UNDERSTANDING=, the item list and Suggested past the cut
# (bon-peluge; observed on spm1001/passe 2026-07-21 at 10.4KB, again
# 2026-07-27). Moving it last was not enough — it still blew the budget from the
# back, so it is gone entirely (bon-tebete). This line is now the ONLY delivery
# of the handoff: state the path, and let the reader Read it.
if [ -n "$LATEST_FILE" ]; then
    echo "Last session ($LATEST_STR): $LATEST_PURPOSE"
    echo "HANDOFF=$LATEST_FILE"
    echo ""
fi

# --- 2b. Unprocessed handoffs (bon-supuko: the sweep replaces latest-wins) ---
if [ -n "$UNPROCESSED_PATHS" ]; then
    UNPROCESSED_COUNT=$(printf '%s\n' "$UNPROCESSED_PATHS" | wc -l | tr -d ' ')
    echo "Unprocessed handoffs ($UNPROCESSED_COUNT) — sweep oldest-first before draw-down, tick each ledger line:"
    printf '%s\n' "$UNPROCESSED_PATHS" | head -n "$UNPROCESSED_MAX" | while IFS= read -r p; do
        echo "  UNPROCESSED=$p"
    done
    if [ "$UNPROCESSED_COUNT" -gt "$UNPROCESSED_MAX" ]; then
        echo "  … +$((UNPROCESSED_COUNT - UNPROCESSED_MAX)) more — see the handoffs dir's LEDGER.md"
    fi
    echo ""
fi
if [ "$UNPROCESSED_MISSING" -gt 0 ]; then
    echo "Warning: $UNPROCESSED_MISSING unticked LEDGER.md line(s) point at files that no longer exist — find where each file went (moved room? renamed?) and fix the line before ticking it."
    echo ""
fi
if [ "$LEDGER_DRIFT" -gt 0 ]; then
    echo "Warning: $LEDGER_DRIFT unticked LEDGER.md line(s) are in a format the sweep cannot parse — normalise them to '- [ ] DATE [file](file) — purpose' or they will never be swept."
    echo ""
fi

# --- 2c. Personal half (bon-hedatu) ---
# The accent file carries this operator's variation-point content, read by
# the rites at designated points (docs/ACCENT.md). Emit the path only when
# the file exists: an absent accent is a complete rite, not a gap — no
# nudge, no placeholder line, ever (law 1: complete-without).
ACCENT_FILE="$HOME/.claude/mit-accent.md"
if [ -f "$ACCENT_FILE" ]; then
    echo "ACCENT=$ACCENT_FILE"
    echo ""
fi

# --- 3. Understanding doc pointer (resolved root/nearest-room first, .bon/
# fallback) — the /open skill reads AND rewrites this path, not blindly .bon/.
UNDERSTANDING_FILE=$(understanding_path "$CWD" || true)
if [ -n "$UNDERSTANDING_FILE" ]; then
    echo "UNDERSTANDING=$UNDERSTANDING_FILE"
    echo ""
fi

# --- 4. From the last handoff's Opportunities ---
# Above the item lists on purpose: this is the baton — the outgoing Claude's
# pointers — and it is the highest-value-per-byte thing in the briefing. The
# label names the source rather than vouching for the content: Opportunities
# has drifted to carry deliberate-inaction notes too, and "Suggested" read
# those as invitations (bon-dokahi). Three guards keep it truthful and small:
# a liveness filter (bon-mosase: suggestions named items closed since the
# handoff), a first-sentence trim + count cap with the remainder stated
# (bon-wokapu: 18 wordy bullets once ate the whole 2KB preview), and honest
# accounting for anything omitted.
DROPPED=0
if [ -n "$LATEST_FILE" ]; then
    # fond-v1: ### Opportunities under ## For the next Claude
    NEXT_LINES=$(sed -n '/^### Opportunities/,/^#/{/^#/d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' || true)
    # Legacy: ## Next (flat section)
    [ -z "$NEXT_LINES" ] && NEXT_LINES=$(sed -n '/^## Next/,/^## /{/^## /d;p;}' "$LATEST_FILE" 2>/dev/null | grep -v '^$' || true)

    # Liveness filter: drop a bullet only when it names this-board items and
    # NONE of them is still open (○ covers both ready and waiting items).
    # Foreign-prefix ids can't be checked against this board — keep them.
    BOARD_PREFIX=""
    [ -n "$BON_ROOT" ] && [ -f "$BON_ROOT/.bon/prefix" ] && BOARD_PREFIX=$(cat "$BON_ROOT/.bon/prefix" 2>/dev/null || true)
    if [ -n "$NEXT_LINES" ] && [ -n "$BOARD_PREFIX" ] && [ -n "$BON_LIST_OUTPUT" ]; then
        OPEN_IDS=$(echo "$BON_LIST_OUTPUT" | grep '○' | grep -oE "${BOARD_PREFIX}-[A-Za-z0-9]+" | sort -u || true)
        FILTERED=""
        while IFS= read -r line; do
            LINE_IDS=$(echo "$line" | grep -oE "${BOARD_PREFIX}-[A-Za-z0-9]+" | sort -u || true)
            if [ -n "$LINE_IDS" ]; then
                LIVE=""
                while IFS= read -r lid; do
                    if printf '%s\n' "$OPEN_IDS" | grep -qx "$lid"; then
                        LIVE=1
                        break
                    fi
                done <<< "$LINE_IDS"
                if [ -z "$LIVE" ]; then
                    DROPPED=$((DROPPED + 1))
                    continue
                fi
            fi
            FILTERED="${FILTERED}${line}"$'\n'
        done <<< "$NEXT_LINES"
        NEXT_LINES=$(printf '%s' "$FILTERED")
    fi

    if [ -n "$NEXT_LINES" ]; then
        SUGGESTED_TOTAL=$(printf '%s\n' "$NEXT_LINES" | wc -l | tr -d ' ')
        echo "From the last handoff's Opportunities:"
        # First sentence per bullet — the full text is in the handoff body
        # below (and on disk at the HANDOFF= path either way).
        printf '%s\n' "$NEXT_LINES" | head -n "$SUGGESTED_MAX" | while IFS= read -r line; do
            echo "  $(printf '%s' "$line" | sed 's/\([.!?]\) [A-Z].*/\1/')"
        done
        if [ "$SUGGESTED_TOTAL" -gt "$SUGGESTED_MAX" ]; then
            echo "  … +$((SUGGESTED_TOTAL - SUGGESTED_MAX)) more in the handoff (path above)"
        fi
        if [ "$DROPPED" -gt 0 ]; then
            echo "  ($DROPPED omitted — their items have closed since the handoff)"
        fi
        echo ""
    elif [ "$DROPPED" -gt 0 ]; then
        echo "From the last handoff's Opportunities: all $DROPPED named items have since closed."
        echo ""
    fi
fi

# --- 5. Open work: outcomes, then standalone ---
if [ "$BON_BACKEND" != "none" ]; then
    if [ -n "${BON_DOLT_ERROR:-}" ]; then
        echo "Bon: backend is dolt but server is unreachable"
        echo "  Run: systemctl --user start dolt-bon.service"
        echo ""
    elif [ -n "$BON_LIST_OUTPUT" ]; then
        # Top-level outcomes sit at column 0; standalone actions sit indented
        # under a column-0 'Standalone:' header (same shape from bon list and
        # bon-read.sh list). Filter each into its own section and only emit a
        # header when its section has content. A standalone-only board used to
        # die here under pipefail (grep '^○' exits 1) leaving a bare header
        # and hiding all open work (bon-cuvice).
        OUTCOME_LINES=$(echo "$BON_LIST_OUTPUT" | grep -E '^○' || true)
        STANDALONE_LINES=$(echo "$BON_LIST_OUTPUT" | awk '/^Standalone:/{f=1;next} /^[^ ]/{f=0} f && /^  ○/' || true)
        if [ -n "$OUTCOME_LINES" ]; then
            # Capped, and the cap says so — same discipline as the standalone
            # pile below. bon-wokapu capped standalone and left outcomes
            # uncapped, which is the same growing list with the same failure
            # mode; tebete closes the asymmetry.
            OUTCOME_COUNT=$(printf '%s\n' "$OUTCOME_LINES" | wc -l | tr -d ' ')
            echo "Outcomes we're working towards:"
            printf '%s\n' "$OUTCOME_LINES" | head -n "$OUTCOME_MAX" | while IFS= read -r line; do
                echo "  $line"
            done
            if [ "$OUTCOME_COUNT" -gt "$OUTCOME_MAX" ]; then
                echo "  … +$((OUTCOME_COUNT - OUTCOME_MAX)) more — full list: bon list"
            fi
            echo ""
        fi
        if [ -n "$STANDALONE_LINES" ]; then
            # Capped, and the cap says so. A long standalone pile is the other
            # way the preview budget gets eaten (16 items pushed Suggested past
            # the cut on this very board, 2026-07-28) — but a silent truncation
            # would read as "that's all there is", which is worse than a long
            # list. State the remainder and where to get it.
            STANDALONE_COUNT=$(printf '%s\n' "$STANDALONE_LINES" | wc -l | tr -d ' ')
            echo "Standalone actions:"
            printf '%s\n' "$STANDALONE_LINES" | head -n "$STANDALONE_MAX"
            if [ "$STANDALONE_COUNT" -gt "$STANDALONE_MAX" ]; then
                echo "  … +$((STANDALONE_COUNT - STANDALONE_MAX)) more — full list: bon list"
            fi
            echo ""
        fi
    fi
fi

# --- 6. Active work / nothing in progress ---
if [ -n "${BON_DOLT_ERROR:-}" ]; then
    true  # Already reported above
elif [ "$BON_BACKEND" != "none" ]; then
    if [ -z "$BON_CURRENT_OUTPUT" ]; then
        echo "Nothing in progress — pick an action to start."
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

# --- 8. The handoff body is deliberately NOT emitted (bon-tebete) ---
# Do not "restore" this — it was measured, not guessed. On 2026-08-04 this
# board's hook output was 12183 bytes, of which the body was 9425 (78%) and the
# curated briefing 2666. The body was the only reason the output crossed the
# persist-and-preview threshold, and the 2KB preview then cut four outcomes, all
# four standalone items and the active-work line — the exact content bon-wokapu
# and bon-peluge fought to protect.
#
# bon-peluge's rule was "anything unbounded goes last, with its address stated
# up front". tebete is the next step: an unbounded section that HAS an address
# does not need emitting at all. The body is doubly redundant — this script
# already extracts its two hot parts (the purpose: line in section 2 and
# ### Opportunities in section 4), and /open step 1 reads the file itself for the
# "For Claudes to come" synthesis. So HANDOFF= is the whole delivery mechanism.
#
# The trade, stated: a session that never invokes /open now gets the skeleton and
# a path rather than the body. That is not a regression — in the truncated case
# it got neither. If it becomes a real cost, the fix is making /open fire
# unbidden (bon-zuvocu), not re-inflating this hook.
