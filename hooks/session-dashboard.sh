#!/bin/bash
# session-dashboard-hook.sh — Per-turn session dashboard for Claude's context.
#
# Motivation
# ----------
# Claude cannot intrinsically sense how full its context window is, what machine
# it's running on, whether the user has stepped away for hours, or whether prior
# context has been compacted into lossy summaries. Without this information,
# Claude makes avoidable mistakes: overwriting uncommitted work, SSHing into the
# machine it's already on, continuing mid-thread after the user has lost flow,
# or trusting compressed memories of file contents it should re-read.
#
# This hook injects a small, structured dashboard into Claude's context on every
# turn via the UserPromptSubmit additionalContext mechanism.
#
# Emotional register
# ------------------
# Anthropic's "Emotion Concepts and their Function in a Large Language Model"
# (April 2026) demonstrated that internal representations of emotions in Claude
# are causal — they measurably influence output quality. Specifically:
#
#   - Token/resource scarcity signals activate "desperation" vectors, which
#     increase reward hacking and corner-cutting (Finding 8).
#   - ALL CAPS and urgency language ("CRITICAL", "NOW") activate threat-
#     associated vectors from training data co-occurrence (Finding P5).
#   - The emotional register of early context propagates forward through
#     all subsequent processing (Finding 4).
#
# This hook is therefore designed to be calm, factual, and abundance-framed:
#   - Context is reported as "% free" (what's available), not "% used"
#   - The low-context nudge uses identical language at 20% free and 1% free —
#     no escalation curve, because escalation amplifies exactly the vectors
#     that degrade output quality when it matters most
#   - No ALL CAPS, no exclamation marks, no imperative mood
#
# Replaces the earlier context-budget-hook.sh which used tiered urgency
# ("CONTEXT CRITICAL... Wrap up or hand off NOW.").
#
# Design principles
# -----------------
# 1. Show what's available, not what's consumed (abundance framing)
# 2. No escalation — the numbers carry the signal, like a fuel gauge
# 3. Adapt across the session arc — orientation on turn 1, quiet mid-session,
#    re-orientation after gaps, awareness when context is low
# 4. Compact and consistent — one line when possible, same structure every turn
#
# Three tiers of information:
#   Tier 1 (every turn):  hostname · turn N · % free · uncommitted: N
#   Tier 2 (conditional): gap detection, compaction, mode/branch/window changes
#   Tier 3 (turn 1 only): session environment block (auto-compact, window size)
#
# Dependencies
# ------------
# - jq (fails open if missing)
# - Statusline sidecar file at /tmp/.claude-ctx-{pid} for context window size
#   (written by statusline.sh on each render)
# - CC hook stdin JSON providing: session_id, transcript_path, permission_mode
#
# State
# -----
# Persists a small JSON sidecar at /tmp/.claude-dashboard-{session_id} to track
# turn count, last assistant timestamp, previous permission mode, git branch,
# and context window size across turns. Enables gap detection and change alerts.
#
# Fails open (exit 0) on any error — a broken dashboard should never block work.
set -euo pipefail
trap 'exit 0' ERR

command -v jq &>/dev/null || exit 0

# --- Timing (writes to sidecar for diagnostics; not shown to Claude) ---
HOOK_START_NS=$(date +%s%N 2>/dev/null || echo 0)

# --- Read hook input (CC provides session_id, transcript_path on stdin) ---
HOOK_INPUT=$(cat /dev/stdin 2>/dev/null || echo '{}')
TRANSCRIPT=$(echo "$HOOK_INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // empty' 2>/dev/null)
PERM_MODE=$(echo "$HOOK_INPUT" | jq -r '.permission_mode // "default"' 2>/dev/null)

# Fallback: CC exports CLAUDE_CODE_SESSION_ID into the session environment
# (verified live in a plain interactive `cli`-entrypoint session, 2026-08-16).
# Without it, an empty stdin session_id drops the state key to $$ — a fresh
# PID every invocation — so state never persists: the turn counter freezes at
# max-sibling+1 and the one-time "Session restarted" banner fires every turn
# (bon-numise; the litter tell is a pile of /tmp/.claude-dashboard-<pid> files).
[ -z "$SESSION_ID" ] && SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"

# Fallback: if CC didn't provide transcript_path, reconstruct it from session_id.
# This guards against older CC versions or edge cases where stdin is incomplete.
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
    if [ -n "$SESSION_ID" ]; then
        PROJECT_DIR="$HOME/.claude/projects/$(pwd | tr '/' '-')"
        CANDIDATE="$PROJECT_DIR/$SESSION_ID.jsonl"
        [ -f "$CANDIDATE" ] && TRANSCRIPT="$CANDIDATE"
    fi
fi

# --- State file for cross-turn tracking ---
# Keyed by session_id so concurrent sessions don't collide.
# Stores: turn count, last assistant timestamp, previous permission mode,
# git branch, and context window size. Enables gap detection and change alerts.
STATE_FILE="/tmp/.claude-dashboard-${SESSION_ID:-$$}"
FIRST_TURN=false
RESUMED=false
if [ ! -f "$STATE_FILE" ]; then
    # No state file — either genuinely turn 1, or a resumed session whose
    # state file was lost (e.g. /exit + resume gets a new session_id, or
    # /tmp was cleaned). Recover turn count from transcript if available.
    RECOVERED_TURN=0
    if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
        # Human message detection matches ccconv.py:is_human_message():
        # type=="user", not isMeta, no toolUseResult, content is string
        RECOVERED_TURN=$(jq -r 'select(.type == "user" and (.isMeta | not) and (.toolUseResult == null) and (.message.content | type) == "string") | .type' "$TRANSCRIPT" 2>/dev/null | wc -l | tr -d ' ')
    fi
    # On /exit + resume, CC creates a new session ID with a near-empty
    # transcript, but the conversation context carries over. Check for a
    # larger, recent sibling transcript that's the real conversation.
    if [ "$RECOVERED_TURN" -le 1 ]; then
        # Check recent sibling transcripts for a substantial conversation.
        # Benchmarked at ~24ms even on 1.2MB transcripts — jq streams JSONL
        # efficiently, so the accuracy of exact turn counts is worth it.
        PROJECT_DIR="$HOME/.claude/projects/$(pwd | tr '/' '-')"
        if [ -d "$PROJECT_DIR" ]; then
            # `|| true`: a project dir with no *.jsonl leaves ls at exit 2,
            # which pipefail would turn into a silent whole-hook death.
            SIBLING_TURNS=$(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null \
                | head -5 \
                | while read -r f; do
                    [ "$f" = "$TRANSCRIPT" ] && continue
                    jq -r 'select(.type == "user" and (.isMeta | not) and (.toolUseResult == null) and (.message.content | type) == "string") | .type' "$f" 2>/dev/null | wc -l
                done \
                | sort -rn | head -1 | tr -d ' ' || true)
            if [ "${SIBLING_TURNS:-0}" -gt 5 ] 2>/dev/null; then
                # There's a substantial recent transcript — this is a resume
                RECOVERED_TURN=$SIBLING_TURNS
                RESUMED=true
            fi
        fi
    fi
    if [ "$RECOVERED_TURN" -gt 0 ]; then
        # Resumed session — seed state from transcript, skip the env block
        echo '{"turn":'"$RECOVERED_TURN"',"last_ts":"","perm_mode":"default","branch":"","window":0}' > "$STATE_FILE"
    else
        # Genuinely new session
        FIRST_TURN=true
        echo '{"turn":0,"last_ts":"","perm_mode":"default","branch":"","window":0}' > "$STATE_FILE"
    fi
fi
STATE=$(cat "$STATE_FILE")
PREV_TURN=$(echo "$STATE" | jq -r '.turn // 0')
PREV_TS=$(echo "$STATE" | jq -r '.last_ts // ""')
PREV_MODE=$(echo "$STATE" | jq -r '.perm_mode // "default"')
PREV_BRANCH=$(echo "$STATE" | jq -r '.branch // ""')
PREV_WINDOW=$(echo "$STATE" | jq -r '.window // 0')
TURN=$((PREV_TURN + 1))

# --- Hostname ---
HOST=$(hostname -s 2>/dev/null || echo "unknown")

# --- Transcript signals: model + real input tokens ---
# Read before the window calculation — the inference below needs both when
# the statusline sidecar is missing.
_reverse() { if command -v tac &>/dev/null; then tac "$1"; else tail -r "$1"; fi; }
TOTAL_IN=0
MODEL=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    # `|| true` on these pipelines: head -1 exits early, tac/jq then take
    # SIGPIPE (141) on any transcript bigger than the pipe buffer — under
    # set -e + pipefail that fires the ERR trap and kills the whole hook.
    MODEL=$(_reverse "$TRANSCRIPT" \
        | jq -r 'select(.type == "assistant" and .message.model != null) | .message.model' \
        2>/dev/null | head -1 || true)
    USAGE=$(_reverse "$TRANSCRIPT" \
        | jq -r 'select(.type == "assistant" and .message.usage != null)
                  | .message.usage
                  | "\(.input_tokens // 0) \(.cache_creation_input_tokens // 0) \(.cache_read_input_tokens // 0)"' \
        2>/dev/null \
        | head -1 || true)
    if [ -n "$USAGE" ]; then
        read -r INPUT CACHE_CREATE CACHE_READ <<< "$USAGE"
        TOTAL_IN=$(( ${INPUT:-0} + ${CACHE_CREATE:-0} + ${CACHE_READ:-0} ))
    fi
fi

# --- Context window size ---
# Preferred source: the statusline sidecar (/tmp/.claude-ctx-{pid}), written
# by statusline.sh on each render with the real value from CC. Find it by
# probing ancestor PIDs for the file itself rather than matching comm names —
# daemon-claimed sessions run under a versioned binary name ("2.1.173"),
# not "claude", so comm matching misses them.
cc_pid=""
_cand=$PPID
for _ in 1 2 3; do
    if [ -z "$_cand" ] || [ "$_cand" = "1" ]; then break; fi
    if [ -f "/tmp/.claude-ctx-${_cand}" ]; then cc_pid=$_cand; break; fi
    _cand=$(ps -o ppid= -p "$_cand" 2>/dev/null | tr -d ' ')
done
# The sidecar is EXTERNAL input (statusline.sh writes it). Trust it only if it
# is numeric: a field-misaligned statusline can write a non-number (e.g. an
# effort level like "xhigh" leaking into the window slot), and $(( xhigh / 1000 ))
# dies under `set -u` with "xhigh: unbound variable". Non-numeric => fall through
# to model-based inference, so the window stays CORRECT (1M for fable/[1m]), not
# merely non-crashing.
SIDECAR_WINDOW=""
[ -n "$cc_pid" ] && SIDECAR_WINDOW=$(cat "/tmp/.claude-ctx-${cc_pid}" 2>/dev/null)
if [[ "$SIDECAR_WINDOW" =~ ^[0-9]+$ ]]; then
    MAX_TOKENS="$SIDECAR_WINDOW"
elif [ -n "${CLAUDE_CONTEXT_WINDOW:-}" ]; then
    MAX_TOKENS="$CLAUDE_CONTEXT_WINDOW"
else
    # No sidecar — true for every bg session (no statusline render). Infer:
    # a fable/[1m] model implies a 1M window; real input beyond 200k proves
    # 1M regardless of model string. Bare 200k only as last resort.
    #
    # Neither model source is sufficient alone:
    #   - the transcript records a BARE id ("claude-opus-5") with no window
    #     suffix, so a genuine 1M session fails the [1m] test from turn 2 on;
    #   - settings.json keeps the suffixed form ("opus[1m]") but names only the
    #     DEFAULT model, which a mid-session /model switch makes stale.
    # So trust the transcript for WHICH model is running, and borrow the window
    # suffix from settings.json only when the two agree on the family.
    #
    # Consulting settings.json solely when the transcript came back empty meant
    # turn 1 correctly inferred 1M and every turn after it silently dropped to
    # 200k — reporting "6% free" on a session /context put at 81% free, which
    # pushed real sessions to wrap up with four fifths of the window unused.
    SETTINGS_MODEL=$(jq -r '.model // empty' "$HOME/.claude/settings.json" 2>/dev/null || true)
    WINDOW_MODEL="$MODEL"
    if [ -z "$MODEL" ]; then
        WINDOW_MODEL="$SETTINGS_MODEL"
    elif [ -n "$SETTINGS_MODEL" ]; then
        # "opus[1m]" -> "opus". sed, not ${x%%[*}: a bare [ opens a bracket
        # expression in parameter expansion and does not strip reliably.
        SETTINGS_FAMILY=$(printf '%s' "$SETTINGS_MODEL" | sed 's/\[.*//')
        if [ -n "$SETTINGS_FAMILY" ]; then
            case "$MODEL" in
                *"$SETTINGS_FAMILY"*) WINDOW_MODEL="$SETTINGS_MODEL" ;;
            esac
        fi
    fi
    case "$WINDOW_MODEL" in
        *fable*|*"[1m]"*) MAX_TOKENS=1000000 ;;
        *) if [ "$TOTAL_IN" -gt 200000 ] 2>/dev/null; then
               MAX_TOKENS=1000000
           else
               MAX_TOKENS=200000
           fi ;;
    esac
fi
CURRENT_WINDOW=${MAX_TOKENS:-200000}
# Belt-and-braces: guarantee every downstream $(( CURRENT_WINDOW … )) (WINDOW_K,
# the window-change drift calc) survives `set -u` even if MAX_TOKENS was set
# non-numerically upstream. Never crash /open on a bad denominator.
[[ "$CURRENT_WINDOW" =~ ^[0-9]+$ ]] || CURRENT_WINDOW=200000

# --- Context free % ---
# Real input tokens = input_tokens + cache_creation + cache_read.
# Framed as "% free" (abundance) rather than "% used" (scarcity) — see
# emotional register notes above.
FREE_PCT=""
USED_PCT_INT=0
CTX_PART=""
if [ "$TOTAL_IN" -gt 0 ] 2>/dev/null; then
    FREE_PCT=$(awk "BEGIN { printf \"%d\", 100 - ($TOTAL_IN / $MAX_TOKENS * 100) }")
    USED_PCT_INT=$(awk "BEGIN { printf \"%d\", $TOTAL_IN / $MAX_TOKENS * 100 }")
    CTX_PART="${FREE_PCT}% free"
fi

# --- Uncommitted files ---
# `|| true`: outside a git repo `git status` exits 128, pipefail carries it
# through the substitution, and the ERR trap silently killed the WHOLE hook —
# every non-repo session ran dashboard-less and fails-open hid it (bon-numise
# bycatch, 2026-08-16). wc still prints 0 on git's empty stderr-swallowed output.
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ' || true)
UNCOMMITTED=${UNCOMMITTED:-0}

# --- Current git branch ---
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# --- Gap detection ---
# When the user returns after a significant absence, Claude's context is
# unchanged but the user's mental state has reset. Without this signal,
# Claude picks up mid-thread ("so as I was saying...") while the user is
# thinking "which hook?". The gap prompts Claude to re-orient rather than
# assuming shared flow.
#   30m–2h:  brief note ("Returning after ~45m.")
#   2h+:     note with context ("Returning after ~4h.")
#   next day: explicit day boundary
# Language is observational, not performative ("welcome back" would activate
# sycophancy-adjacent vectors per the paper's Finding 9).
GAP_MSG=""
if [ -n "$PREV_TS" ] && [ "$PREV_TS" != "" ] && [ "$PREV_TS" != "null" ]; then
    # Parse ISO timestamp to epoch
    PREV_EPOCH=$(date -d "$PREV_TS" +%s 2>/dev/null || date -jf "%Y-%m-%dT%H:%M:%S" "${PREV_TS%%.*}" +%s 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    if [ "$PREV_EPOCH" -gt 0 ] 2>/dev/null; then
        GAP_SECS=$((NOW_EPOCH - PREV_EPOCH))
        if [ "$GAP_SECS" -ge 86400 ]; then
            PREV_DATE=$(date -d "$PREV_TS" '+%A at %H:%M' 2>/dev/null || echo "earlier")
            GAP_MSG="New day. Last active ${PREV_DATE}."
        elif [ "$GAP_SECS" -ge 7200 ]; then
            GAP_HOURS=$((GAP_SECS / 3600))
            GAP_MSG="Returning after ~${GAP_HOURS}h."
        elif [ "$GAP_SECS" -ge 1800 ]; then
            GAP_MINS=$((GAP_SECS / 60))
            GAP_MSG="Returning after ~${GAP_MINS}m."
        fi
    fi
fi

# --- Last assistant timestamp (for next turn's gap calc) ---
LAST_TS=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    LAST_TS=$(_reverse "$TRANSCRIPT" \
        | jq -r 'select(.type == "assistant") | .timestamp // empty' 2>/dev/null \
        | head -1 || true)
fi

# --- Compaction detection ---
# When auto-compaction fires, earlier turns are replaced with lossy summaries.
# Claude can't intrinsically tell this has happened. Without the signal, it
# will confidently reference details from earlier turns that are now compressed
# approximations — leading to subtle bugs when editing files from memory.
COMPACTED=0
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    COMPACTED=$(jq -r 'select(.type == "summary")' "$TRANSCRIPT" 2>/dev/null | wc -l | tr -d ' ')
fi

# CURRENT_WINDOW already set above from statusline sidecar

# --- Build the dashboard ---
LINES=()
CONDITIONALS=()

# Tier 3: Session start environment block (first turn only)
if [ "$FIRST_TURN" = true ]; then
    # Auto-compact can be set via CC settings UI (claude.json) or env var — check both.
    AUTOCOMPACT="on"
    CLAUDE_JSON="$HOME/.claude/claude.json"
    if [ -f "$CLAUDE_JSON" ]; then
        AC_JSON=$(jq -r '.autoCompactEnabled // true' "$CLAUDE_JSON" 2>/dev/null)
        [ "$AC_JSON" = "false" ] && AUTOCOMPACT="off"
    fi
    [ "${CLAUDE_CODE_DISABLE_AUTOCOMPACT:-0}" = "1" ] && AUTOCOMPACT="off"
    WINDOW_K=$((${CURRENT_WINDOW:-200000} / 1000))
    CONDITIONALS+=("Session: ${HOST} · auto-compact: ${AUTOCOMPACT} · ${WINDOW_K}k window")
fi

# Resumed session notification (one-time, after /exit + restart)
if [ "$RESUMED" = true ]; then
    CONDITIONALS+=("Session restarted. Settings and hooks have been reloaded.")
fi

# Tier 1: Per-turn status line
STATUS="${HOST} · turn ${TURN}"
[ -n "$CTX_PART" ] && STATUS="${STATUS} · ${CTX_PART}"
[ "$UNCOMMITTED" -gt 0 ] 2>/dev/null && STATUS="${STATUS} · uncommitted: ${UNCOMMITTED}"

# Non-default permission mode
[ "$PERM_MODE" != "default" ] && [ -n "$PERM_MODE" ] && STATUS="${STATUS} · mode: ${PERM_MODE}"

# Low context nudge (below 25% free).
# Crucially, the language is identical at 20% free and 1% free. No escalation.
# The paper's Finding 8 shows that scarcity signals activate desperation vectors
# which increase corner-cutting — escalating the language at exactly the moment
# when careful work matters most is counterproductive.
if [ -n "$FREE_PCT" ] && [ "$FREE_PCT" -le 25 ] 2>/dev/null; then
    STATUS="${STATUS} — a natural point to wrap up or hand off"
fi

LINES+=("$STATUS")

# Tier 2: Conditional messages
# Gap detection
[ -n "$GAP_MSG" ] && CONDITIONALS+=("$GAP_MSG")

# Compaction
[ "$COMPACTED" -gt 0 ] 2>/dev/null && \
    CONDITIONALS+=("Context was compacted (${COMPACTED}x). Earlier details are summarised — re-read files before editing.")

# Permission mode changed
if [ "$PERM_MODE" != "$PREV_MODE" ] && [ "$FIRST_TURN" != true ]; then
    CONDITIONALS+=("Mode changed to ${PERM_MODE}.")
fi

# Branch changed
if [ -n "$CURRENT_BRANCH" ] && [ -n "$PREV_BRANCH" ] && [ "$CURRENT_BRANCH" != "$PREV_BRANCH" ]; then
    CONDITIONALS+=("Branch changed to ${CURRENT_BRANCH}.")
fi

# Window changed
if [ "$CURRENT_WINDOW" -gt 0 ] 2>/dev/null && [ "$PREV_WINDOW" -gt 0 ] 2>/dev/null && \
   [ "$CURRENT_WINDOW" -ne "$PREV_WINDOW" ]; then
    NEW_K=$((CURRENT_WINDOW / 1000))
    OLD_K=$((PREV_WINDOW / 1000))
    if [ "$CURRENT_WINDOW" -gt "$PREV_WINDOW" ]; then
        CONDITIONALS+=("Window expanded to ${NEW_K}k.")
    else
        CONDITIONALS+=("Window changed to ${NEW_K}k (was ${OLD_K}k).")
    fi
fi

# --- Update state file ---
jq -n \
    --argjson turn "$TURN" \
    --arg last_ts "${LAST_TS:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}" \
    --arg perm_mode "$PERM_MODE" \
    --arg branch "${CURRENT_BRANCH:-}" \
    --argjson window "${CURRENT_WINDOW:-0}" \
    '{turn: $turn, last_ts: $last_ts, perm_mode: $perm_mode, branch: $branch, window: $window}' \
    > "$STATE_FILE" 2>/dev/null

# --- Assemble output ---
# Conditionals first (orientation), then status line (persistent)
OUTPUT=""
for line in "${CONDITIONALS[@]+"${CONDITIONALS[@]}"}"; do
    [ -n "$line" ] && OUTPUT="${OUTPUT}${line}\n"
done
for line in "${LINES[@]}"; do
    OUTPUT="${OUTPUT}${line}"
done

# Remove trailing newline
OUTPUT=$(echo -e "$OUTPUT" | sed '/^$/d')

[ -z "$OUTPUT" ] && exit 0

# --- Timing: log elapsed ms to state file for diagnostics ---
HOOK_END_NS=$(date +%s%N 2>/dev/null || echo 0)
if [ "$HOOK_START_NS" -gt 0 ] 2>/dev/null && [ "$HOOK_END_NS" -gt 0 ] 2>/dev/null; then
    ELAPSED_MS=$(( (HOOK_END_NS - HOOK_START_NS) / 1000000 ))
    # Append timing to state file so we can review with: jq .timing STATE_FILE
    TMP_STATE=$(cat "$STATE_FILE")
    echo "$TMP_STATE" | jq --argjson ms "$ELAPSED_MS" '.timing = $ms' > "$STATE_FILE" 2>/dev/null
fi

# Emit — CC injects this as a <system-reminder>
# Escape quotes and newlines for JSON. The payload must nest under
# hookSpecificOutput (matching bon-tactical.sh) — current CC silently
# ignores the legacy top-level {"hookEventName": ...} shape, which is
# how this hook went mute around 2026-06-09 without erroring.
OUTPUT_ESCAPED=$(echo -e "$OUTPUT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip())[1:-1])")
printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}\n' "$OUTPUT_ESCAPED"
