#!/bin/bash
# SessionEnd hook: archive the closing Claude Code session into notes.
#
# The go-forward capture path replacing the retiring garde-manger plugin
# (garde decommission, gm-kenave). On session end this runs the notes-owned
# converter, which applies the gm-firaso capture predicate (/close OR
# substantial, minus subagents + tmux-labeler) and writes spec-compliant
# markdown to notes/raw/claude/code/ — see that converter + ARCHIVE-FORMAT.md.
#
# NO fork-bomb guard needed: the converter runs `deglacer` (pure JSONL parse)
# and writes a file — it never calls `claude -p`, so there is no hook→claude→
# hook recursion. (Contrast garde's session-end.sh, whose LLM extraction did
# call claude -p and so required GARDE_SUBAGENT guards.)
#
# Writes only — does not commit. notes is Hezza-canonical git / Mac-Syncthing;
# a periodic Hezza-side commit (or the digester) sweeps raw/ additions.

export PATH="$HOME/.local/bin:$PATH"

CONVERTER="$HOME/notes/raw/claude/_converters/convert-claude-code.py"
OUTDIR="$HOME/notes/raw/claude/code"
LOGFILE="$HOME/.claude/logs/notes-capture.log"
mkdir -p "$(dirname "$LOGFILE")"
stamp() { date -u '+%Y-%m-%d %H:%M:%S'; }

command -v uv &>/dev/null      || { echo "[$(stamp)] uv not found — skip" >> "$LOGFILE"; exit 0; }
command -v python3 &>/dev/null || { echo "[$(stamp)] python3 not found — skip" >> "$LOGFILE"; exit 0; }
[ -f "$CONVERTER" ]            || { echo "[$(stamp)] converter missing ($CONVERTER) — skip" >> "$LOGFILE"; exit 0; }
[ -d "$HOME/notes/raw/claude" ] || { echo "[$(stamp)] notes not present — skip" >> "$LOGFILE"; exit 0; }

HOOK_INPUT=$(cat)
SID=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('session_id',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)
CWD=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('cwd',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)

if [ -z "$SID" ]; then
    echo "[$(stamp)] no session_id in hook input — skip" >> "$LOGFILE"
    exit 0
fi

STATUS=$("$CONVERTER" --session "$SID" --cwd "$CWD" "$OUTDIR" 2>>"$LOGFILE" || echo "error:converter-failed")
echo "[$(stamp)] $SID: $STATUS" >> "$LOGFILE"
exit 0
