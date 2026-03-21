# Changelog

## [0.8.0] - 2026-03-21

### Added
- Optional Dolt backend — MySQL-compatible storage with git semantics for multi-machine workflows
- `bon migrate --to {jsonl|dolt}` command to switch between backends
- `bon init --backend {jsonl|dolt}` flag
- `src/bon/dolt.py` — all Dolt code, lazily imported (zero overhead for JSONL users)
- `pymysql` as optional dependency (`pip install bon[dolt]`)
- `get_session_identity()` — hostname-prefixed sessions in Dolt mode
- Dolt-aware `bon doctor` health checks
- `bon-read.sh` backend detection (falls back to CLI in Dolt mode)
- 28 new tests (mocked unit tests, integration tests, migration tests)

### Changed
- `storage.py` dispatches six functions based on `.bon/backend` file
- Session identity uses `get_session_identity()` throughout (backward compatible)
- SPEC.md updated with Storage Backends section

### Removed
- `AGENTS.md` — redundant with CLAUDE.md
- `docs/understanding.md` — superseded by `.bon/understanding.md`

## [0.7.0] - 2026-03-20

Maturity realignment across the batterie.

### Changed
- Version reflects honest maturity level (0.6.2 → 0.7.0) — bon is the most battle-tested tool in the suite, closest to 1.0
- `plugin.json` confirmed as single source of truth; pyproject.toml reads version dynamically via hatchling

## [0.4.0] - 2026-03-18

Batterie-wide consistency pass: docs consolidation, CI, versioning.

### Added
- Session lifecycle scripts and hooks (bon is now self-contained)
- Open, close, audit skills migrated from trousse
- `setup.sh` and `update-all.sh` for install orchestration
- `manifest.json` for plugin install coordination
- SessionStart hook for CLI discovery and PATH setup
- Handoff contract and test coverage from trousse
- Understanding document wired into session lifecycle

### Changed
- Migrated bon-tactical hook from jq to python3
- Scripts find themselves in plugin cache, not `~/.claude/scripts/`

### Fixed
- Bon-tactical hook: suppress non-zero exit on empty/malformed input
- 3 bon-read.sh bugs: malformed JSON, numbering, trailing newlines
- Close skill gracefully optional when garde-manger absent

## 2026-03-02 — Claude Ergonomics & Doctor

### Added
- `bon doctor` command for items.jsonl health checks
- `--note` flag for `bon done`
- `--no-complete` flag for deliberate-open actions
- `--parent` aliased to `--outcome` in `bon new`
- Claude ergonomics analysis across 2,542 commands and 2,914 sessions

### Changed
- Stats display, `done_note` documentation, `_matches_session` helper extraction

## 2026-02-27 — Plugin System

### Added
- Plugin manifest for Claude Code plugin system
- Skill directory moved from `bon/` to `skills/tracker/` for plugin discovery

## 2026-02-18 — Step Workflow Improvements

### Added
- `--skip` and `--no-complete` flags for `bon step`
- `updated_by` field to distinguish mutation types in log

## 2026-02-15 — Arc-to-Bon Migration

### Changed
- Renamed `.arc/` to `.bon/`, all arc references to bon
- Added `updated_at` to all mutations, dedup on save, removed migrate command, fixed CWD coupling

## 2026-02-14 — Codebase Maturation

### Changed
- Removed 8 historical docs, added schema stability to SPEC.md
- Structural improvements: Gemini skill trimmed, argparse fixes, multi-agent safety

## 2026-02-09 — Major Feature Batch (v0.3.0)

### Added
- `bon reopen` command for completed/archived items
- `bon log` command for recent activity feed
- `bon archive` command to move done items to archive.jsonl
- Ready view shows completed actions for context
- Warn on activity-language outcome titles at creation time

### Changed
- Unified `--for`/`--parent` as `--outcome` across all commands
- Deterministic save order + union merge for multi-Claude safety

### Fixed
- Step parser handles multiline `--what` and version numbers
- `bon done` clears tactical steps so next `bon work` succeeds
- Titans review: 4 critical path fixes

## 2026-02-05 — Tactical Steps (v0.2.0)

### Added
- Tactical step tracking (`bon work`, `bon step`)
- `bon convert` command
- Ruff linter, migration orphan fixtures, parametrized tests
- All-lowercase identifiers

## 2026-01-25 — Initial Release

### Added
- Core CLI: `bon new`, `bon show`, `bon status`, `bon edit`, `bon done`
- Two-phase migration with manifest pattern
- Spec v2.3, implementation guide, skill integration
- Session start protocol for `/open` integration
