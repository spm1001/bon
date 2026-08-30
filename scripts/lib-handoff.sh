#!/bin/bash
# Shared handoff / understanding.md resolution — sourced by open-context.sh
# (READ) and close-context.sh (WRITE). ONE source of truth so the reader and
# the writer cannot drift: you must read a handoff from where you would write
# the next one.
#
# The "legible substrate" convention (see bon-gopewu): PROSE (handoffs/,
# understanding.md) lives VISIBLE at the room where work happens; the BOARD
# (.bon/items.jsonl) stays hidden + repo-global. Resolution is a nearest-room
# walk. Runtime-agnostic: relies on NO harness autoload (Cowork loads only the
# root CLAUDE.md; CC's upward walk loads CLAUDE.md only, never
# understanding.md/handoffs).
#
# A ROOM adopts the convention simply by having a visible handoffs/ (or
# understanding.md) — zero config. The BOARD ROOT gets one either way: it is
# the default a fresh board writes to, and where handoff_migrate_legacy puts
# a legacy pile (bon-sedoze). understanding.md still resolves through .bon/ as
# a fallback — only handoffs left.
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
# one); else the board root's visible handoffs/ — created on write, and the
# DEFAULT for a fresh board since bon-sedoze; else global ~/.bon/handoffs.
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
        printf '%s\n' "$root/handoffs"
        return 0
    fi
    printf '%s\n' "$HOME/.bon/handoffs"
}

# handoff_read_dirs START_DIR -> newline-separated dirs to SEARCH for the
# latest handoff (caller ranks across them by header date). Every visible
# handoffs/ up the tree, then global ~/.bon/handoffs.
#
# The board root's .bon/handoffs is NO LONGER a rung (bon-sedoze). Legacy
# piles are converged onto the visible dir by handoff_migrate_legacy below,
# which BOTH callers run before resolving — so a repo arriving with residue
# has been migrated by the time this function is asked anything.
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
    printf '%s\n' "$HOME/.bon/handoffs"
}

# --- Legacy convergence (bon-sedoze) -----------------------------------------
# The board root's .bon/handoffs was a resolution rung until bon-sedoze retired
# it. Retiring a READ rung is a breaking change for anyone whose pile still
# lives there: their handoffs stop appearing in /open's ranking, and nothing
# says so — the briefing simply omits the "Last session" line. bon ships
# publicly, so "the estate is migrated" is not the same claim as "every
# consumer is migrated".
#
# So the change that drops the rung carries the migration. This converges a
# legacy pile onto the visible convention on the back of ordinary use — the
# parasitic pattern storage.py already uses to refresh the bottle
# (BOARD_README) on every save. BOTH callers run it BEFORE resolving, so the
# first /open or /close after an upgrade migrates and then reads the migrated
# location; there is no session in which the handoffs are missing.
#
# Sets HANDOFF_MIGRATED_N, HANDOFF_MIGRATED_DEST and HANDOFF_MIGRATED_FAILED.
# Prints nothing — the reader and the writer frame their output differently.
# Best-effort by construction: it always returns 0, and any file it cannot
# move is left exactly where it is rather than lost.
handoff_migrate_legacy() {
    HANDOFF_MIGRATED_N=0
    HANDOFF_MIGRATED_DEST=""
    HANDOFF_MIGRATED_FAILED=0
    local start="$1" root legacy dest f base target n

    root=$(board_root "$start") || return 0
    legacy="$root/.bon/handoffs"
    if [ ! -d "$legacy" ]; then return 0; fi

    # A BARE STASH IS NOT A BOARD. board_root accepts any .bon at the start
    # dir, so a session with cwd=$HOME adopts ~/.bon — the global catch-all,
    # which close-context still actively WRITES to. Migrating that would hoover
    # live global history into ~/handoffs, where any session behind a .git
    # boundary can no longer see it, and the stash would re-form and re-migrate
    # forever. Only a real board (prefix marker) has legacy residue to converge.
    if [ ! -f "$root/.bon/prefix" ]; then return 0; fi

    # The legacy pile is board-root-level, so it converges to the board root's
    # visible handoffs/ — never the nearest room's, which would relocate
    # root-level history into whichever room this session happened to start in.
    dest="$root/handoffs"

    # PHYSICAL IDENTITY, NOT NAME EQUALITY. A consumer who wanted the visible
    # convention without rewriting git history plausibly linked the two names
    # at one directory (`ln -s .bon/handoffs handoffs`, or the reverse shim
    # after a hand-migration). Then every file below would compare identical to
    # ITSELF, take the "already migrated" branch, and be unlinked — deleting
    # the only copy of every handoff, silently. There is nothing to converge
    # when both names already reach the same place.
    if [ -L "$legacy" ]; then return 0; fi
    if [ -d "$dest" ] && [ "$legacy" -ef "$dest" ]; then return 0; fi

    for f in "$legacy"/*.md; do
        if [ ! -e "$f" ]; then continue; fi
        if [ ! -d "$dest" ]; then
            if ! mkdir -p "$dest" 2>/dev/null; then
                HANDOFF_MIGRATED_FAILED=1
                return 0
            fi
        fi
        base=$(basename "$f")
        target="$dest/$base"
        if [ -e "$target" ]; then
            # Belt to the -ef brace above: a hardlink, or any route by which
            # source and target are one inode, must never reach the rm below.
            if [ "$f" -ef "$target" ]; then continue; fi
            if cmp -s "$f" "$target"; then
                # Already migrated (an interrupted run, or a hand-copy): drop
                # the duplicate rather than mint a second visible copy.
                if ! rm -f "$f" 2>/dev/null; then HANDOFF_MIGRATED_FAILED=1; fi
                continue
            fi
            # Same name, different content — keep both. Never clobber a
            # handoff: it is the only record of a session.
            n=2
            while [ "$n" -lt 100 ] && [ -e "$dest/${base%.md}-legacy${n}.md" ]; do
                n=$((n + 1))
            done
            target="$dest/${base%.md}-legacy${n}.md"
            if [ -e "$target" ]; then
                # 98 same-named variants already parked — the search ran out.
                # Refuse rather than clobber the hundredth: leaving the file
                # where it is loses nothing, and the caller reports it.
                HANDOFF_MIGRATED_FAILED=1
                continue
            fi
        fi
        if _handoff_move_one "$f" "$target" "$root"; then
            HANDOFF_MIGRATED_N=$((HANDOFF_MIGRATED_N + 1))
        else
            HANDOFF_MIGRATED_FAILED=1
        fi
    done

    if [ "$HANDOFF_MIGRATED_N" -gt 0 ]; then HANDOFF_MIGRATED_DEST="$dest"; fi
    # Leave no empty husk to be re-probed every session. A dir still holding
    # something (a file we could not move, or a non-.md file we never claimed)
    # is left alone — rmdir refuses it, which is the behaviour we want.
    rmdir "$legacy" 2>/dev/null || true
    return 0
}

# _handoff_move_one SRC DST REPO -> move one file, preserving git's view where
# git has one. `git mv` stages the rename, so a TRACKED handoff cannot end up
# half-committed (deletion staged, addition forgotten, file gone on the next
# clone). An untracked or ignored one — the wholesale-`.bon/`-ignore case — is
# moved plainly, because git mv refuses a path it does not track.
_handoff_move_one() {
    local src="$1" dst="$2" repo="$3"
    if git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
        && git -C "$repo" ls-files --error-unmatch -- "$src" >/dev/null 2>&1; then
        if git -C "$repo" mv -- "$src" "$dst" 2>/dev/null; then return 0; fi
    fi
    mv -- "$src" "$dst" 2>/dev/null
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
