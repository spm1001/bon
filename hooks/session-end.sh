#!/bin/bash
# SessionEnd hook: archive the closing Claude Code session into notes.
#
# The go-forward capture path replacing the retiring garde-manger plugin
# (garde decommission, gm-kenave). On session end this runs glaneur's
# `glean-code` CLI — the consolidated converter (glan-kohadu; formerly the
# notes-owned convert-claude-code.py) — which applies the gm-firaso capture
# predicate (/close OR substantial, minus subagents + tmux-labeler) and
# writes spec-compliant markdown to notes/raw/claude/code/ — see glaneur's
# code_convert.py + notes ARCHIVE-FORMAT.md.
#
# glean-code is a self-contained uv tool (no uv needed at hook time):
#   tube: uv tool install 'glaneur[transcripts,chats] @ git+https://github.com/spm1001/glaneur'
#   Mac:  uv tool install ~/repos/spm1001/glaneur   (base extras-free install;
#         the private git+ deps are unresolvable over the Mac's
#         credential-less headless ssh — ship the tree by git bundle)
#
# NO fork-bomb guard needed: glean-code runs `deglacer` (pure JSONL parse)
# and writes a file — it never calls `claude -p`, so there is no hook→claude→
# hook recursion. (Contrast garde's session-end.sh, whose LLM extraction did
# call claude -p and so required GARDE_SUBAGENT guards.)
#
# Writes only — does not commit. notes-sync owns every git write in ~/notes
# (tube-side robot; the Mac working tree rides the same loop via Syncthing).

export PATH="$HOME/.local/bin:$PATH"

OUTDIR="$HOME/notes/raw/claude/code"
LOGFILE="$HOME/.claude/logs/notes-capture.log"
mkdir -p "$(dirname "$LOGFILE")"
stamp() { date -u '+%Y-%m-%d %H:%M:%S'; }

command -v glean-code &>/dev/null || { echo "[$(stamp)] glean-code not found (uv tool install glaneur) — skip" >> "$LOGFILE"; exit 0; }
command -v python3 &>/dev/null    || { echo "[$(stamp)] python3 not found — skip" >> "$LOGFILE"; exit 0; }
[ -d "$HOME/notes/raw/claude" ]   || { echo "[$(stamp)] notes not present — skip" >> "$LOGFILE"; exit 0; }

HOOK_INPUT=$(cat)
SID=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('session_id',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)
CWD=$(python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('cwd',''))" <<< "$HOOK_INPUT" 2>/dev/null || true)

if [ -z "$SID" ]; then
    echo "[$(stamp)] no session_id in hook input — skip" >> "$LOGFILE"
    exit 0
fi

STATUS=$(glean-code --session "$SID" --cwd "$CWD" "$OUTDIR" 2>>"$LOGFILE" || echo "error:converter-failed")
echo "[$(stamp)] $SID: $STATUS" >> "$LOGFILE"
exit 0
