#!/bin/bash
# setup.sh — Create all symlinks from the manifest
#
# Reads manifest.json and creates symlinks in ~/.claude/ for skills, hooks, and scripts.
# Resolves repo paths using group membership: batterie repos live in batterie_dir,
# everything else in repos_dir.
#
# Usage: ~/Repos/batterie/bon/scripts/setup.sh [--verify]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$SCRIPT_DIR/../manifest.json"
CLAUDE_DIR="$HOME/.claude"

if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: manifest.json not found at $MANIFEST"
    exit 1
fi

VERIFY_ONLY=false
[ "${1:-}" = "--verify" ] && VERIFY_ONLY=true

# ── Parse manifest with python3 (no jq dependency) ──────────
resolve() {
    local query="${1:-}"
    python3 - "$MANIFEST" "$query" << 'PYEOF'
import json, sys, os

manifest_path = sys.argv[1]
query = sys.argv[2] if len(sys.argv) > 2 else ""

with open(manifest_path) as f:
    m = json.load(f)

repos_dir = os.path.expanduser(m.get("repos_dir", "~/Repos"))
batterie_dir = os.path.expanduser(m.get("batterie_dir", repos_dir))

def repo_base(repo_name):
    """Return the filesystem base directory for a repo."""
    repo = m["repos"].get(repo_name, {})
    if repo.get("group") == "batterie":
        return batterie_dir
    return repos_dir

def resolve_target(target):
    """Resolve a manifest target like 'bon/skills/tracker' to full path."""
    # The first path component is the repo name
    parts = target.split("/", 1)
    repo_name = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    base = repo_base(repo_name)
    if rest:
        return os.path.join(base, repo_name, rest)
    return os.path.join(base, repo_name)

if query == "skills":
    for name, info in m.get("skills", {}).items():
        target = info["target"]
        print(f"{name}\t{resolve_target(target)}")
elif query == "hooks":
    for name, info in m.get("hooks", {}).items():
        target = info["target"]
        print(f"{name}\t{resolve_target(target)}")
elif query == "scripts":
    for name, info in m.get("scripts", {}).items():
        target = info["target"]
        print(f"{name}\t{resolve_target(target)}")
elif query == "tools":
    for name, info in m.get("tools", {}).items():
        repo_name = info["repo"]
        base = repo_base(repo_name)
        print(f"{name}\t{os.path.join(base, repo_name)}")
PYEOF
}

# ── Create symlinks ──────────────────────────────────────────
link() {
    local link_path="$1"
    local target="$2"
    local name="$3"

    if [ "$VERIFY_ONLY" = true ]; then
        if [ -L "$link_path" ] && [ -e "$link_path" ]; then
            echo "  ✓ $name"
        elif [ -L "$link_path" ]; then
            echo "  ✗ $name → $(readlink "$link_path") (BROKEN)"
        else
            echo "  ✗ $name (MISSING)"
        fi
        return
    fi

    if [ ! -e "$target" ] && [ ! -d "$target" ]; then
        echo "  ⚠ $name: target not found ($target)"
        return
    fi

    rm -f "$link_path"
    ln -s "$target" "$link_path"
    echo "  ✓ $name"
}

# Ensure directories exist
mkdir -p "$CLAUDE_DIR/skills" "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/scripts"

echo "=== Skills ==="
while IFS=$'\t' read -r name target; do
    link "$CLAUDE_DIR/skills/$name" "$target" "$name"
done < <(resolve skills)

echo ""
echo "=== Hooks ==="
while IFS=$'\t' read -r name target; do
    link "$CLAUDE_DIR/hooks/$name" "$target" "$name"
done < <(resolve hooks)

echo ""
echo "=== Scripts ==="
while IFS=$'\t' read -r name target; do
    link "$CLAUDE_DIR/scripts/$name" "$target" "$name"
done < <(resolve scripts)

if [ "$VERIFY_ONLY" = true ]; then
    echo ""
    echo "Verify complete."
else
    echo ""
    echo "Setup complete. Restart Claude Code to pick up hook changes."
fi
