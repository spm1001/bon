#!/bin/bash
# SessionStart hook: ensure bon CLI is available. Install-if-MISSING only —
# no version-drift check here. Post single-version cutover the vendored
# plugin.json carries the stamped SUITE version, not bon's own, so any
# version comparison at session start is structurally false (bds-japoca).
# Freshness is /batterie:update's job (commit-based). Silent when fine.

export PATH="$HOME/.local/bin:$PATH"
FIXED=""
ISSUES=""

# Capture auto-update output so failures are diagnosable, not silent (bon-babuse).
UPDATE_LOG="$HOME/.cache/bon/auto-update.log"
mkdir -p "$(dirname "$UPDATE_LOG")" 2>/dev/null

# --- Instruction shard ---
# Symlink into ~/.claude/rules/ so always-on rules load every session.
# Idempotent — ln -sf overwrites stale symlinks from old plugin versions.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$HOOK_DIR")"
if [ -f "$PLUGIN_ROOT/instructions.md" ]; then
    mkdir -p "$HOME/.claude/rules"
    ln -sf "$PLUGIN_ROOT/instructions.md" "$HOME/.claude/rules/bon.md"
fi

# Resolve install source (bon needs [dolt] extra)
if [ -n "$PLUGIN_ROOT" ] && [ -f "$PLUGIN_ROOT/pyproject.toml" ]; then
    INSTALL_SRC="$PLUGIN_ROOT[dolt]"
else
    # Vendored marketplace plugin ships no pyproject.toml (post-2026-06-10 cutover),
    # so install from the source repo over git — the bare name is not published on PyPI.
    INSTALL_SRC="bon[dolt] @ git+https://github.com/spm1001/bon"
fi

# Check 1: CLI missing → auto-install.
# Report the version that ACTUALLY landed (re-read post-install), never an
# expected number — the old hook claimed the plugin.json version without
# checking, and misreported every session (bds-zelowe).
if ! command -v bon &>/dev/null; then
    if uv tool install "$INSTALL_SRC" --force --reinstall --no-cache >"$UPDATE_LOG" 2>&1; then
        LANDED=$(bon --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        FIXED="${FIXED}• bon CLI installed (v${LANDED})\n"
    else
        ISSUES="${ISSUES}• bon CLI not found and auto-install failed (full error: ${UPDATE_LOG}). Run manually:\n\n  uv tool install \"$INSTALL_SRC\" --force --reinstall --no-cache\n"
    fi
fi

# Check 3: pymysql available (needed for any Dolt-backed repo)
# Use bon's own venv Python, not system Python — pymysql lives in the uv tool venv
if command -v bon &>/dev/null; then
    BON_PYTHON=$(head -1 "$(command -v bon)" | sed 's/^#!//')
    if [ -x "$BON_PYTHON" ] && ! "$BON_PYTHON" -c "import pymysql" 2>/dev/null; then
        # Only warn if there are Dolt repos — check common locations
        HAS_DOLT=$(find ~/repos -maxdepth 4 -name backend -path '*/.bon/*' -exec grep -l dolt {} + 2>/dev/null | head -1 || true)
        if [ -n "$HAS_DOLT" ]; then
            ISSUES="${ISSUES}• pymysql not found but Dolt-backed repos exist. Reinstall with extras:\n  uv tool install \"$INSTALL_SRC\"\n"
        fi
    fi
fi

# Silent exit if nothing happened
[ -z "$FIXED" ] && [ -z "$ISSUES" ] && exit 0

# Report
MSG=""
[ -n "$FIXED" ] && MSG="${MSG}✓ bon auto-fixed:\n\n${FIXED}"
[ -n "$ISSUES" ] && MSG="${MSG}⚠️ bon needs attention:\n\n${ISSUES}"

python3 -c "import json; print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': '''${MSG}'''}}))"
