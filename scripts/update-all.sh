#!/bin/bash
# update-all.sh — Tiered auto-updater for Batterie de Savoir
#
# Two tiers:
# - QUICK: Every session start (<10s) — repo sync, symlink health
# - HEAVY: Once per day max — CLI updates, Claude Code update
#
# Personal additions: source update-local.sh from same directory.
# Triggered by session-start.sh (background, no stdout).
# Logs to ~/.claude/logs/update.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.claude/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/update.log"
LOCK_FILE="$LOG_DIR/update.lock"
HEAVY_TIMESTAMP="$LOG_DIR/.last-heavy-update"
HEAVY_INTERVAL=$((24 * 60 * 60))
NEWS_FILE="$HOME/.claude/.update-news"

# ── Concurrency guard ──────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') SKIP: Update already running" >> "$LOG_FILE"
    exit 0
fi
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"; }
log_section() { echo "" >> "$LOG_FILE"; log "=== $1 ==="; }

should_run_heavy() {
    [ ! -f "$HEAVY_TIMESTAMP" ] && return 0
    local last_run=$(cat "$HEAVY_TIMESTAMP")
    local now=$(date +%s)
    local elapsed=$((now - last_run))
    if [ $elapsed -gt $HEAVY_INTERVAL ]; then return 0; fi
    log "THROTTLE: Heavy ran $((elapsed / 3600))h ago"
    return 1
}

mark_heavy_complete() { date +%s > "$HEAVY_TIMESTAMP"; }

#######################################
# QUICK TIER — Every session (<10s)
#######################################

log_section "QUICK UPDATES"

# 1. Repo sync (parallel fetch + ff-only pull)
REPO_SYNC="$SCRIPT_DIR/repo-sync.sh"
if [ -x "$REPO_SYNC" ]; then
    log "Syncing repos..."
    if "$REPO_SYNC" 2>/dev/null; then
        log "✓ Repo sync complete"
    else
        log "⚠ Repo sync had issues"
    fi
fi

# 2. Symlink health check via setup --verify
SETUP="$SCRIPT_DIR/setup.sh"
if [ -x "$SETUP" ]; then
    broken=$("$SETUP" --verify 2>/dev/null | grep -c "✗" || echo 0)
    if [ "$broken" -gt 0 ]; then
        log "❌ $broken broken symlinks — run setup.sh to fix"
        echo "❌ $broken BROKEN SYMLINKS — run ~/Repos/batterie/bon/scripts/setup.sh" >> "$NEWS_FILE"
    else
        log "✓ All symlinks healthy"
    fi
fi

# 3. New skills detection (from skill-sources-anthropic)
SKILLS_DIR="$HOME/.claude/skills"
KNOWN_FILE="$SKILLS_DIR/.known-unlinked"
ANTHROPIC_DIR="$HOME/Repos/skill-sources-anthropic/skills"
NEW_SKILLS=""
if [ -d "$ANTHROPIC_DIR" ]; then
    for skill in "$ANTHROPIC_DIR"/*/; do
        skill_name=$(basename "$skill")
        skill_id="anthropic:$skill_name"
        if [ ! -L "$SKILLS_DIR/$skill_name" ] && [ -f "$skill/SKILL.md" ]; then
            if ! grep -q "^$skill_id$" "$KNOWN_FILE" 2>/dev/null; then
                NEW_SKILLS="$NEW_SKILLS $skill_id"
            fi
        fi
    done
fi
if [ -n "$NEW_SKILLS" ]; then
    log "⚠ NEW SKILLS AVAILABLE:$NEW_SKILLS"
else
    log "✓ All skills accounted for"
fi

#######################################
# HEAVY TIER — Once per day max
#######################################

if should_run_heavy; then
    log_section "HEAVY UPDATES (daily)"
    HEAVY_FAILED=false

    # 1. Claude Code CLI
    if command -v claude &>/dev/null; then
        log "Updating Claude Code CLI..."
        if claude update >> "$LOG_FILE" 2>&1; then
            log "✓ Claude Code CLI updated"
        else
            log "⚠ Claude Code CLI update failed"
            HEAVY_FAILED=true
        fi
    fi

    # 2. Reinstall batterie CLI tools (picks up code changes)
    if command -v uv &>/dev/null; then
        for tool_dir in "$HOME/Repos/batterie/bon" "$HOME/Repos/batterie/passe" "$HOME/Repos/batterie/garde-manger"; do
            if [ -d "$tool_dir" ]; then
                name=$(basename "$tool_dir")
                if uv tool install "$tool_dir" --force --quiet 2>/dev/null; then
                    log "✓ $name CLI updated"
                else
                    log "⚠ $name CLI update failed"
                fi
            fi
        done
    fi

    mark_heavy_complete

    if [ "$HEAVY_FAILED" = true ]; then
        log "⚠ Some heavy updates failed"
    else
        log "✓ All heavy updates complete"
    fi
fi

#######################################
# LOCAL ADDITIONS
#######################################

LOCAL_UPDATE="$SCRIPT_DIR/update-local.sh"
if [ -x "$LOCAL_UPDATE" ]; then
    log_section "LOCAL UPDATES"
    source "$LOCAL_UPDATE"
fi

#######################################
# HEALTH SUMMARY
#######################################

log_section "SESSION INFO"
if command -v claude &>/dev/null; then
    log "Claude Code: $(claude --version 2>/dev/null | head -1 || echo unknown)"
fi
log "Update cycle complete"

# Trim log
tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
