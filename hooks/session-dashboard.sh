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
            SIBLING_TURNS=$(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null \
                | head -5 \
                | while read -r f; do
                    [ "$f" = "$TRANSCRIPT" ] && continue
                    jq -r 'select(.type == "user" and (.isMeta | not) and (.toolUseResult == null) and (.message.content | type) == "string") | .type' "$f" 2>/dev/null | wc -l
                done \
                | sort -rn | head -1 | tr -d ' ')
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

# --- Context window size ---
# Read from the statusline sidecar file, which statusline.sh writes on every
# render with the real value from CC (handles 200k vs 1M transparently).
# Walk the process tree to find the CC PID: hook → bash → claude.
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
CURRENT_WINDOW=${MAX_TOKENS:-200000}

# --- Context free % ---
# Real input tokens = input_tokens + cache_creation + cache_read.
# Framed as "% free" (abundance) rather than "% used" (scarcity) — see
# emotional register notes above.
FREE_PCT=""
USED_PCT_INT=0
CTX_PART=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    _reverse() { if command -v tac &>/dev/null; then tac "$1"; else tail -r "$1"; fi; }
    USAGE=$(_reverse "$TRANSCRIPT" \
        | jq -r 'select(.type == "assistant" and .message.usage != null)
                  | .message.usage
                  | "\(.input_tokens // 0) \(.cache_creation_input_tokens // 0) \(.cache_read_input_tokens // 0)"' \
        2>/dev/null \
        | head -1)
    if [ -n "$USAGE" ]; then
        read -r INPUT CACHE_CREATE CACHE_READ <<< "$USAGE"
        TOTAL_IN=$(( INPUT + CACHE_CREATE + CACHE_READ ))
        if [ "$TOTAL_IN" -gt 0 ] 2>/dev/null; then
            FREE_PCT=$(awk "BEGIN { printf \"%d\", 100 - ($TOTAL_IN / $MAX_TOKENS * 100) }")
            USED_PCT_INT=$(awk "BEGIN { printf \"%d\", $TOTAL_IN / $MAX_TOKENS * 100 }")
            CTX_PART="${FREE_PCT}% free"
        fi
    fi
fi

# --- Uncommitted files ---
UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

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
        | head -1)
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
# Escape quotes and newlines for JSON
OUTPUT_ESCAPED=$(echo -e "$OUTPUT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip())[1:-1])")
printf '{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}\n' "$OUTPUT_ESCAPED"
