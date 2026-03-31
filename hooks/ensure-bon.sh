#!/bin/bash
# SessionStart hook: ensure bon CLI + instruction shard are in place.
# Silent when everything is fine; helpful when it's not.

# Ensure ~/.local/bin is in PATH (where uv tool install puts binaries)
export PATH="$HOME/.local/bin:$PATH"

# --- Instruction shard ---
# Symlink into ~/.claude/rules/ so always-on rules load every session.
# Idempotent — ln -sf overwrites stale symlinks from old plugin versions.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "$HOOK_DIR")"
if [ -f "$PLUGIN_ROOT/instructions.md" ]; then
    mkdir -p "$HOME/.claude/rules"
    ln -sf "$PLUGIN_ROOT/instructions.md" "$HOME/.claude/rules/bon.md"
fi

# --- CLI check ---
if command -v bon &>/dev/null; then
    exit 0
fi

# bon not found — check if we can install it from the plugin
if [ -n "$PLUGIN_ROOT" ] && [ -f "$PLUGIN_ROOT/pyproject.toml" ]; then
    INSTALL_HINT="uv tool install \"$PLUGIN_ROOT[dolt]\""
else
    INSTALL_HINT="uv tool install 'bon[dolt]'"
fi

cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "bon CLI not found. Install it:\n\n  $INSTALL_HINT\n\nThen ensure ~/.local/bin is in your PATH."}}
EOF
