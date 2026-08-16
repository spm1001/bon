#!/bin/bash
# Shared handoff / understanding.md resolution — sourced by open-context.sh
# (READ) and close-context.sh (WRITE). ONE source of truth so the reader and
# the writer cannot drift: you must read a handoff from where you would write
# the next one.
#
# The "legible substrate" convention (see bon-gopewu): PROSE (handoffs/,
# understanding.md) lives VISIBLE at the room where work happens; the BOARD
# (.bon/items.jsonl) stays hidden + repo-global. Resolution is a nearest-room
# walk, visible-first, with .bon/ as the legacy fallback. Runtime-agnostic:
# relies on NO harness autoload (Cowork loads only the root CLAUDE.md; CC's
# upward walk loads CLAUDE.md only, never understanding.md/handoffs).
#
# A repo/room "adopts" the visible convention simply by having a visible
# handoffs/ (or understanding.md) — zero config. Repos with only .bon/handoffs/
# are untouched.
#
# Functions are written with explicit if-blocks (no `[ x ] && cmd` idiom) so
# they are safe to source into a script running `set -euo pipefail`.

# board_root START_DIR -> echoes the dir holding the repo's .bon board.
# Mirrors the CLI's discovery: at START any .bon counts; above it only one
# carrying a prefix file (skips bare handoff stashes like ~/.bon); a .git
# boundary stops the walk so a nested repo never adopts an outer board.
# Returns 1 (no output) when no board is found.
board_root() {
    local walk="$1" start="$1"
    while [ "$walk" != "/" ]; do
        if [ -d "$walk/.bon" ]; then
            if [ "$walk" = "$start" ] || [ -f "$walk/.bon/prefix" ]; then
                printf '%s\n' "$walk"
                return 0
            fi
        fi
        if [ -e "$walk/.git" ]; then break; fi
        walk=$(dirname "$walk")
    done
    return 1
}

# handoff_write_dir START_DIR -> the single dir to WRITE a new handoff to.
# Nearest visible handoffs/ walking up from START (a room adopts by having
# one); else the board root's visible handoffs/ if present; else the board
# root's .bon/handoffs (legacy default); else global ~/.bon/handoffs.
handoff_write_dir() {
    local start="$1" root walk
    root=$(board_root "$start") || root=""
    walk="$start"
    while [ "$walk" != "/" ]; do
        if [ -d "$walk/handoffs" ]; then printf '%s\n' "$walk/handoffs"; return 0; fi
        if [ -n "$root" ] && [ "$walk" = "$root" ]; then break; fi
        if [ -e "$walk/.git" ]; then break; fi
        walk=$(dirname "$walk")
    done
    if [ -n "$root" ]; then
        if [ -d "$root/handoffs" ]; then printf '%s\n' "$root/handoffs"; return 0; fi
        printf '%s\n' "$root/.bon/handoffs"
        return 0
    fi
    printf '%s\n' "$HOME/.bon/handoffs"
}

# handoff_read_dirs START_DIR -> newline-separated dirs to SEARCH for the
# latest handoff (caller ranks across them by header date). Every visible
# handoffs/ up the tree (migration-in-progress repos have both), then the
# board root's .bon/handoffs, then global ~/.bon/handoffs.
handoff_read_dirs() {
    local start="$1" root walk
    root=$(board_root "$start") || root=""
    walk="$start"
    while [ "$walk" != "/" ]; do
        if [ -d "$walk/handoffs" ]; then printf '%s\n' "$walk/handoffs"; fi
        if [ -n "$root" ] && [ "$walk" = "$root" ]; then break; fi
        if [ -e "$walk/.git" ]; then break; fi
        walk=$(dirname "$walk")
    done
    if [ -n "$root" ]; then printf '%s\n' "$root/.bon/handoffs"; fi
    printf '%s\n' "$HOME/.bon/handoffs"
}

# scan_down_candidates START_DIR -> newline list of child repos holding a
# .bon board (the repo dir, not the .bon), pruned of vendored
# plugin/marketplace clones and non-git dirs, most-recent-commit FIRST.
# The CALLER decides what more than one candidate means: recency here is
# ordering context, never a choice — the estate's most recent commit is
# estate noise, not session identity (bon-gojeni: /close from an owner
# bucket routed the handoff at whichever sibling the last publish touched).
scan_down_candidates() {
    local start="$1" bon_dir repo_dir latest rows=""
    while IFS= read -r bon_dir; do
        # A vendored plugin/marketplace clone carries its own .bon. Routing a
        # handoff there buries it in gitignored cache that marketplace sync
        # then clobbers (bon-suvise). Never a legitimate target.
        case "$bon_dir" in
            */.claude/plugins/*|*/plugins/marketplaces/*|*/node_modules/*|*/.git/*)
                continue ;;
        esac
        repo_dir=$(dirname "$bon_dir")
        # Skip non-git dirs (e.g. pytest temp dirs)
        if ! git -C "$repo_dir" rev-parse --git-dir >/dev/null 2>&1; then
            continue
        fi
        latest=$(git -C "$repo_dir" log -1 --format=%ct 2>/dev/null || echo "0")
        latest=${latest:-0}
        rows+="${latest}"$'\t'"${repo_dir}"$'\n'
    done < <(find "$start" -maxdepth 4 -name ".bon" -type d 2>/dev/null)
    if [ -n "$rows" ]; then
        printf '%s' "$rows" | sort -rn | cut -f2-
    fi
}

# understanding_path START_DIR -> the understanding.md to read: nearest visible
# (room or root) walking up, else the board root's .bon/understanding.md.
# Returns 1 (no output) when none exists.
understanding_path() {
    local start="$1" root walk
    root=$(board_root "$start") || root=""
    walk="$start"
    while [ "$walk" != "/" ]; do
        if [ -f "$walk/understanding.md" ]; then printf '%s\n' "$walk/understanding.md"; return 0; fi
        if [ -n "$root" ] && [ "$walk" = "$root" ]; then break; fi
        if [ -e "$walk/.git" ]; then break; fi
        walk=$(dirname "$walk")
    done
    if [ -n "$root" ]; then
        if [ -f "$root/understanding.md" ]; then printf '%s\n' "$root/understanding.md"; return 0; fi
        if [ -f "$root/.bon/understanding.md" ]; then printf '%s\n' "$root/.bon/understanding.md"; return 0; fi
    fi
    return 1
}
