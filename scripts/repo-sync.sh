#!/bin/bash
# repo-sync.sh — Pull ff-only on repos that are behind remote
#
# Fetches all repos in ~/Repos/ in parallel, then pulls those that are
# cleanly behind (no local changes, no divergence). Conflicts are reported
# to the NEWS_FILE so they surface in the next session briefing.
#
# Called from update-all.sh QUICK tier. Runs in background — no stdout.
# Logs to update.log.

set -euo pipefail

REPOS_DIR="${REPOS_DIR:-$HOME/Repos}"
LOG_FILE="${LOG_FILE:-$HOME/.claude/scripts/update.log}"
NEWS_FILE="${NEWS_FILE:-$HOME/.claude/.update-news}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [repo-sync] $1" >> "$LOG_FILE"; }

# Parallel fetch: one background job per repo
for dir in "$REPOS_DIR"/*/; do
    [ -d "$dir/.git" ] || continue
    git -C "$dir" fetch --quiet 2>/dev/null &
done
wait  # Wait for all fetches before checking behind/ahead

PULLED=0
SKIPPED=0
CONFLICT_LINES=""
PUSH_LINES=""

for dir in "$REPOS_DIR"/*/; do
    [ -d "$dir/.git" ] || continue
    name=$(basename "$dir")

    # @{u} fails if no tracking branch — that's fine, skip it
    behind=$(git -C "$dir" rev-list HEAD..@{u} 2>/dev/null | wc -l | tr -d ' ')
    [ "$behind" -eq 0 ] && continue

    ahead=$(git -C "$dir" rev-list @{u}..HEAD 2>/dev/null | wc -l | tr -d ' ')
    dirty=$(git -C "$dir" status --porcelain 2>/dev/null | wc -l | tr -d ' ')

    if [ "$dirty" -gt 0 ]; then
        CONFLICT_LINES="${CONFLICT_LINES}\n- **${name}**: ${behind} behind, ${dirty} local change(s) — pull manually"
        log "⚠ $name: behind=$behind dirty=$dirty"
    elif [ "$ahead" -gt 0 ]; then
        CONFLICT_LINES="${CONFLICT_LINES}\n- **${name}**: diverged (↑${ahead} ↓${behind}) — needs manual rebase"
        log "⚠ $name: diverged ↑$ahead ↓$behind"
    else
        if git -C "$dir" pull --ff-only --quiet 2>/dev/null; then
            PULLED=$((PULLED + 1))
            log "✓ $name: ↓$behind"
        else
            CONFLICT_LINES="${CONFLICT_LINES}\n- **${name}**: ${behind} behind, ff-only failed"
            log "⚠ $name: pull failed (not ff-only?)"
            SKIPPED=$((SKIPPED + 1))
        fi
    fi
done

# Check for repos that are ahead (need pushing) — separate loop, no fetch needed
for dir in "$REPOS_DIR"/*/; do
    [ -d "$dir/.git" ] || continue
    name=$(basename "$dir")
    ahead=$(git -C "$dir" rev-list @{u}..HEAD 2>/dev/null | wc -l | tr -d ' ')
    [ "$ahead" -gt 0 ] && PUSH_LINES="${PUSH_LINES}\n- **${name}**: ↑${ahead} unpushed commit(s)"
done

log "Repo sync complete: $PULLED pulled, $SKIPPED skipped"

# Append to news file if anything needs attention
if [ -n "$CONFLICT_LINES" ] || [ -n "$PUSH_LINES" ]; then
    TODAY=$(date '+%Y-%m-%d')
    {
        if [ -n "$CONFLICT_LINES" ]; then
            echo ""
            echo "## Repos needing manual sync ($TODAY)"
            printf "%b" "$CONFLICT_LINES"
            echo ""
            echo "Run: cd ~/Repos/<name> && git status"
        fi
        if [ -n "$PUSH_LINES" ]; then
            echo ""
            echo "## Repos with unpushed commits ($TODAY)"
            printf "%b" "$PUSH_LINES"
            echo ""
        fi
    } >> "$NEWS_FILE"
    log "Sync summary appended to $NEWS_FILE"
fi
