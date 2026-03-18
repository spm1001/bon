#!/bin/bash
# Tiered auto-updater for dev tools
#
# Scaffolded from trousse. Customize for your machine.
# This file lives in ~/.claude/scripts/ (not symlinked — it's yours).
#
# Two tiers:
# - QUICK: Runs every session start (<10s) - health checks, submodules
# - HEAVY: Runs once per day max - package managers, CLI updates
#
# Triggered by session-start.sh (background, no stdout).
# Logs to ~/.claude/scripts/update.log

set -euo pipefail

LOG_FILE="$HOME/.claude/scripts/update.log"
LOCK_FILE="$HOME/.claude/scripts/update.lock"
HEAVY_TIMESTAMP="$HOME/.claude/scripts/.last-heavy-update"
HEAVY_INTERVAL=$((24 * 60 * 60))  # 24 hours in seconds
NEWS_FILE="$HOME/.claude/.update-news"

# ── Concurrency guard ──────────────────────────────────────
if [ -f "$LOCK_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') SKIP: Update already running" >> "$LOG_FILE"
    exit 0
fi

touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

# ── Logging ────────────────────────────────────────────────
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

log_section() {
    echo "" >> "$LOG_FILE"
    log "=== $1 ==="
}

# ── Throttle ───────────────────────────────────────────────
should_run_heavy() {
    if [ ! -f "$HEAVY_TIMESTAMP" ]; then
        return 0  # Never run, should run
    fi
    last_run=$(cat "$HEAVY_TIMESTAMP")
    now=$(date +%s)
    elapsed=$((now - last_run))
    if [ $elapsed -gt $HEAVY_INTERVAL ]; then
        return 0
    else
        hours_ago=$((elapsed / 3600))
        log "THROTTLE: Heavy updates ran ${hours_ago}h ago (next in $((24 - hours_ago))h)"
        return 1
    fi
}

mark_heavy_complete() {
    date +%s > "$HEAVY_TIMESTAMP"
}

#######################################
# QUICK TIER - Every session (<10s)
#######################################

log_section "QUICK UPDATES"

# 1. Critical symlink health check
log "Checking critical symlinks..."
if [ -x "$HOME/.claude/scripts/check-symlinks.sh" ]; then
    if ! "$HOME/.claude/scripts/check-symlinks.sh" >> "$LOG_FILE" 2>&1; then
        log "❌ BROKEN SYMLINKS DETECTED - /open and /close will fail!"
        echo "❌ BROKEN SYMLINKS - run check-symlinks.sh for details" >> "$NEWS_FILE"
    fi
else
    log "⚠ check-symlinks.sh not found"
fi

# 2. Git submodules (e.g. skills/anthropic)
log "Updating git submodules..."
cd "$HOME/.claude" || exit
if git submodule update --remote --merge >> "$LOG_FILE" 2>&1; then
    log "✓ Submodules updated"
else
    log "⚠ Submodule update failed"
fi

# 3. New skills detection (from submodules)
log "Checking for new skills in submodules..."
NEW_SKILLS=""
SKILLS_DIR="$HOME/.claude/skills"
KNOWN_FILE="$SKILLS_DIR/.known-unlinked"
NOTIFY_FILE="$HOME/.claude/.new-skills-notification"

is_known_unlinked() {
    local skill_id="$1"
    [ -f "$KNOWN_FILE" ] && grep -q "^$skill_id$" "$KNOWN_FILE" 2>/dev/null
}

# Check anthropic submodule
if [ -d "$SKILLS_DIR/anthropic/skills" ]; then
    for skill in "$SKILLS_DIR/anthropic/skills"/*/; do
        skill_name=$(basename "$skill")
        skill_id="anthropic:$skill_name"
        if [ ! -L "$SKILLS_DIR/$skill_name" ] && [ -f "$skill/SKILL.md" ]; then
            if ! is_known_unlinked "$skill_id"; then
                NEW_SKILLS="$NEW_SKILLS $skill_id"
            fi
        fi
    done
fi

# Check superpowers submodule
if [ -d "$HOME/.claude/submodules/superpowers/skills" ]; then
    for skill in "$HOME/.claude/submodules/superpowers/skills"/*/; do
        skill_name=$(basename "$skill")
        skill_id="superpowers:$skill_name"
        if [ ! -L "$SKILLS_DIR/$skill_name" ] && [ -f "$skill/SKILL.md" ]; then
            if ! is_known_unlinked "$skill_id"; then
                NEW_SKILLS="$NEW_SKILLS $skill_id"
            fi
        fi
    done
fi

if [ -n "$NEW_SKILLS" ]; then
    log "⚠ NEW SKILLS AVAILABLE:$NEW_SKILLS"
    echo "$NEW_SKILLS" > "$NOTIFY_FILE"
else
    log "✓ All submodule skills accounted for"
    rm -f "$NOTIFY_FILE"
fi

# 4. Repo sync (pull ff-only on repos that are behind remote)
REPO_SYNC="$HOME/.claude/scripts/repo-sync.sh"
if [ -x "$REPO_SYNC" ]; then
    log "Syncing repos..."
    if "$REPO_SYNC"; then
        log "✓ Repo sync complete"
    else
        log "⚠ Repo sync had issues (check log)"
    fi
else
    log "⚠ repo-sync.sh not found — run setup-from-manifest.sh"
fi

# ── CUSTOMIZE: Add your quick checks below ────────────────
# Examples:
#   - bon list (check work tracker): bon list --quiet >> "$LOG_FILE" 2>&1
#   - Config backup: cmp -s "$SOURCE" "$BACKUP" || cp "$SOURCE" "$BACKUP"
#   - Stale artifact cleanup: [ -d "$HOME/.claude/old-thing" ] && rm -rf ...


#######################################
# HEAVY TIER - Once per day max
#######################################

if should_run_heavy; then
    log_section "HEAVY UPDATES (daily)"

    # Capture Claude CLI version before updates
    OLD_CLI_VERSION=$(claude --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo 'unknown')

    HEAVY_FAILED=false

    # 1. Package manager (uncomment the section for your platform)
    # Runs in background — won't block your session, but uses bandwidth.
    # Disable if on metered connection or slow machine.

    # log "Updating Homebrew packages..."
    # if command -v brew &>/dev/null; then
    #     if brew update >> "$LOG_FILE" 2>&1 && \
    #        brew upgrade >> "$LOG_FILE" 2>&1 && \
    #        brew cleanup >> "$LOG_FILE" 2>&1; then
    #         log "✓ Homebrew updated"
    #     else
    #         log "⚠ Homebrew update had issues"
    #         HEAVY_FAILED=true
    #     fi
    # fi

    # log "Updating apt packages..."
    # if command -v apt-get &>/dev/null; then
    #     sudo apt-get update >> "$LOG_FILE" 2>&1 && \
    #       sudo apt-get upgrade -y >> "$LOG_FILE" 2>&1
    # fi

    # 2. npm globals (uncomment if you use global npm packages)
    # log "Updating npm globals..."
    # if command -v npm &>/dev/null; then
    #     npm update -g >> "$LOG_FILE" 2>&1 && log "✓ npm globals updated" || log "⚠ npm update failed"
    # fi

    # 3. Claude Code CLI
    log "Updating Claude Code CLI..."
    if command -v claude &>/dev/null; then
        if claude update >> "$LOG_FILE" 2>&1; then
            log "✓ Claude Code CLI updated"
        else
            log "⚠ Claude Code CLI update failed"
            HEAVY_FAILED=true
        fi
    fi

    # ── CUSTOMIZE: Add your heavy updates below ───────────
    # Examples:
    #   - MCP deps: uv sync --directory "$HOME/Repos/my-mcp" >> "$LOG_FILE" 2>&1
    #   - Plugin updates: claude plugin update NAME >> "$LOG_FILE" 2>&1
    #   - Vendor drift: compare vendored files against upstream

    # Mark complete (even if some failed, to avoid retry spam)
    mark_heavy_complete

    # ── News generation ────────────────────────────────────
    # session-start.sh reads ~/.claude/.update-news if it exists.
    # Format: markdown with "# Update News (date)" title and ## sections.
    NEW_CLI_VERSION=$(claude --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo 'unknown')
    news=""
    today=$(date '+%Y-%m-%d')

    if [ "$OLD_CLI_VERSION" != "$NEW_CLI_VERSION" ] && [ "$NEW_CLI_VERSION" != "unknown" ]; then
        news="${news}## Claude Code CLI updated: v${OLD_CLI_VERSION} → v${NEW_CLI_VERSION}\n"
        news="${news}Check release notes at: https://github.com/anthropics/claude-code/releases\n\n"
    fi

    # Include new skills notification if exists
    if [ -f "$NOTIFY_FILE" ] && [ -s "$NOTIFY_FILE" ]; then
        new_skills=$(cat "$NOTIFY_FILE")
        news="${news}## New skills available\n"
        for skill in $new_skills; do
            news="${news}- **${skill}**\n"
        done
        news="${news}\n"
    fi

    if [ -n "$news" ]; then
        echo -e "# Update News ($today)\n\n$news" > "$NEWS_FILE"
        log "✓ Update news written"
    else
        rm -f "$NEWS_FILE"
    fi

    if [ "$HEAVY_FAILED" = true ]; then
        log "⚠ Some heavy updates failed - check log for details"
    else
        log "✓ All heavy updates completed successfully"
    fi
else
    log "SKIP: Heavy updates throttled"
fi

#######################################
# HEALTH SUMMARY
#######################################

log_section "SESSION INFO"

if command -v claude &>/dev/null; then
    CLI_VERSION=$(claude --version 2>/dev/null | head -1 || echo "unknown")
    log "Claude Code CLI: $CLI_VERSION"
fi

log "Update cycle complete"

# Trim log to last 500 lines (prevent unbounded growth)
tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
