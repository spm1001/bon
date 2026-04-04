#!/bin/bash
# SessionStart hook: ensure bon CLI is available and version-aligned.
# Auto-fixes drift; reports what it did. Silent when everything is fine.

export PATH="$HOME/.local/bin:$PATH"
FIXED=""
ISSUES=""

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
    INSTALL_SRC="bon[dolt]"
fi

# Check 1: CLI missing → auto-install
if ! command -v bon &>/dev/null; then
    if uv tool install "$INSTALL_SRC" --force --reinstall >/dev/null 2>&1; then
        FIXED="${FIXED}• bon CLI installed\n"
    else
        ISSUES="${ISSUES}• bon CLI not found and auto-install failed. Run manually:\n\n  uv tool install \"$INSTALL_SRC\"\n"
    fi
fi

# Check 2: version drift → auto-update
if [ -z "$ISSUES" ] && command -v bon &>/dev/null; then
    if [ -n "$PLUGIN_ROOT" ] && [ -f "$PLUGIN_ROOT/.claude-plugin/plugin.json" ]; then
        INSTALLED=$(bon --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
        EXPECTED=$(python3 -c "import json; print(json.load(open('$PLUGIN_ROOT/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || true)
        if [ -n "$INSTALLED" ] && [ -n "$EXPECTED" ] && [ "$INSTALLED" != "$EXPECTED" ]; then
            CLI_BEHIND=$(python3 -c "print(tuple(int(x) for x in '$INSTALLED'.split('.')) < tuple(int(x) for x in '$EXPECTED'.split('.')))" 2>/dev/null || true)
            if [ "$CLI_BEHIND" = "True" ]; then
                if uv tool install "$INSTALL_SRC" --force --reinstall >/dev/null 2>&1; then
                    FIXED="${FIXED}• bon CLI updated: v${INSTALLED} → v${EXPECTED}\n"
                else
                    ISSUES="${ISSUES}• bon CLI is v${INSTALLED} but plugin is v${EXPECTED}. Auto-update failed.\n"
                fi
            fi
        fi
    fi
fi

# Silent exit if nothing happened
[ -z "$FIXED" ] && [ -z "$ISSUES" ] && exit 0

# Report
MSG=""
[ -n "$FIXED" ] && MSG="${MSG}✓ bon auto-fixed:\n\n${FIXED}"
[ -n "$ISSUES" ] && MSG="${MSG}⚠️ bon needs attention:\n\n${ISSUES}"

cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "${MSG}"}}
EOF
