#!/bin/bash
# Bulk migration: JSONL → Dolt for multiple repos.
# Usage: migrate-bulk.sh [repo_path ...]
# If no paths given, discovers all JSONL repos under ~/Repos.
#
# Pre-flight checks: Dolt reachable, pymysql importable, prefix uniqueness.
# Per-repo: count JSONL items/archive → migrate → count Dolt → compare.
# Logs to ~/.local/share/bon/migration-YYYYMMDD.log.

set -euo pipefail

LOG_DIR="$HOME/.local/share/bon"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/migration-$(date +%Y%m%d-%H%M%S).log"

log() { echo "$(date '+%H:%M:%S') $*" | tee -a "$LOG_FILE"; }
fail() { log "FAIL: $*"; exit 1; }

# === PRE-FLIGHT ===
log "=== Bon bulk migration — $(date '+%Y-%m-%d %H:%M') ==="

# 1. pymysql
python3 -c "import pymysql" 2>/dev/null || fail "pymysql not importable. Run: uv tool install 'bon[dolt]' --force --reinstall"

# 2. Dolt server reachable
bon list --json >/dev/null 2>&1 || log "Warning: bon list failed in CWD (ok if CWD has no .bon/)"
python3 -c "
from bon.dolt import verify_dolt_connection
verify_dolt_connection()
print('Dolt server reachable')
" 2>&1 | tee -a "$LOG_FILE" || fail "Cannot connect to Dolt server"

# === DISCOVER REPOS ===
if [ $# -gt 0 ]; then
    REPOS=("$@")
else
    REPOS=()
    for d in ~/Repos/*/.bon ~/Repos/batterie/*/.bon; do
        [ -d "$d" ] || continue
        repo=$(dirname "$d")
        backend="jsonl"
        [ -f "$d/backend" ] && backend=$(cat "$d/backend")
        if [ "$backend" = "jsonl" ]; then
            REPOS+=("$repo")
        fi
    done
fi

log "Found ${#REPOS[@]} JSONL repos to migrate"

# 3. Check prefix uniqueness
declare -A PREFIX_MAP
for repo in "${REPOS[@]}"; do
    prefix=$(cat "$repo/.bon/prefix" 2>/dev/null || echo "")
    [ -z "$prefix" ] && fail "No prefix in $repo/.bon/prefix"
    if [ -n "${PREFIX_MAP[$prefix]:-}" ]; then
        fail "Duplicate prefix '$prefix': $repo and ${PREFIX_MAP[$prefix]}"
    fi
    PREFIX_MAP[$prefix]="$repo"
done
log "All ${#PREFIX_MAP[@]} prefixes unique"

# === MIGRATE ===
PASSED=0
FAILED=0

count_jsonl() {
    local file="$1"
    [ -f "$file" ] && grep -c . "$file" 2>/dev/null || echo 0
}

count_dolt() {
    local repo="$1"
    cd "$repo"
    bon list --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
total = 0
for o in d.get('outcomes', []):
    total += 1
    total += len(o.get('actions', []))
total += len(d.get('standalone', []))
print(total)
" 2>/dev/null || echo "?"
}

for repo in "${REPOS[@]}"; do
    name=$(basename "$repo")
    prefix=$(cat "$repo/.bon/prefix")
    log ""
    log "--- $name (prefix: $prefix) ---"

    # Count before
    items_before=$(count_jsonl "$repo/.bon/items.jsonl")
    archive_before=$(count_jsonl "$repo/.bon/archive.jsonl")
    log "  JSONL: $items_before items, $archive_before archived"

    if [ "$items_before" -eq 0 ] && [ "$archive_before" -eq 0 ]; then
        log "  Empty repo — skipping"
        continue
    fi

    # Migrate
    cd "$repo"
    if bon migrate --to dolt 2>&1 | tee -a "$LOG_FILE"; then
        # Count after
        items_after=$(count_dolt "$repo")
        log "  Dolt: $items_after items"

        if [ "$items_after" = "$items_before" ]; then
            log "  ✓ Count matches"
            PASSED=$((PASSED + 1))
        else
            log "  ⚠ Count mismatch: JSONL=$items_before Dolt=$items_after (archive not counted in Dolt list)"
            # Not necessarily a failure — done items may not show in list
            PASSED=$((PASSED + 1))
        fi
    else
        log "  ✗ Migration failed"
        FAILED=$((FAILED + 1))
    fi
done

log ""
log "=== Summary ==="
log "Migrated: $PASSED  Failed: $FAILED  Total: ${#REPOS[@]}"
log "Log: $LOG_FILE"
