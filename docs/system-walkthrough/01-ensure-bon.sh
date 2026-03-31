#!/bin/bash
# SessionStart hook: ensure bon CLI is available
# Silent when everything is fine; helpful when it's not.

# Ensure ~/.local/bin is in PATH (where uv tool install puts binaries)
export PATH="$HOME/.local/bin:$PATH"

# Check if bon CLI is available
if command -v bon &>/dev/null; then
    exit 0
fi

# bon not found — check if we can install it from the plugin
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
if [ -n "$PLUGIN_ROOT" ] && [ -f "$PLUGIN_ROOT/pyproject.toml" ]; then
    INSTALL_HINT="uv tool install \"$PLUGIN_ROOT[dolt]\""
else
    INSTALL_HINT="uv tool install 'bon[dolt]'"
fi

cat <<EOF
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "⚠️ bon CLI not found. Install it:\n\n  $INSTALL_HINT\n\nThen ensure ~/.local/bin is in your PATH."}}
EOF
