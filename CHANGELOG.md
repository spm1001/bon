# Changelog

## [0.26.4] - 2026-06-17

### Fixed
- `ensure-bon.sh` auto-update is now diagnosable **and** actually applies plugin.json-only bumps (bon-babuse). Three changes: (1) installs use `--no-cache` — without it, a bump touching only `plugin.json`/CLAUDE.md leaves `src/` byte-identical (bon's version is dynamic from plugin.json), so uv silently reuses the cached build and the version never moves; `uv cache clean bon` does **not** clear that build. (2) install stderr is captured to `~/.cache/bon/auto-update.log`. (3) both failure branches now point to that log and print the manual `--no-cache` recovery command. CLAUDE.md's stale-install gotcha recipe corrected to match. The lock-resilience half of babuse's brief was deliberately deferred — its premise was unverified, and the captured log now makes a genuine lock failure self-revealing.
- `bon list --json` / `bon show --json` / `--jsonl` now return a non-null `updated_at` for never-edited items, defaulted to `created_at` (bon-jejuge). bon only stamps `updated_at` on first edit; the default is computed at the JSON output boundary (`_normalize_brief`), so every item — new and existing — is covered with no stored-data backfill and no change to human `bon show` output. Consumers can recency-sort / date-slice without a None guard. (Raw `items.jsonl` readers that bypass the CLI are unaffected and should guard or use the CLI.)

## [0.26.3] - 2026-06-17

### Changed
- CLAUDE.md Key Files table now points at `docs/CONTRACT.md` (the docket/rite boundary). This one-line edit rode in with the 0.26.2 work but without its own version bump, so it tripped the batterie assembler's content ratchet and blocked the **entire marketplace publish** from ~06-13 until this bump cleared it. (The Cowork web-service docs added under `docs/` in the same window — GUI mock + research note — are **not** vendored by the assembler's copy-list, so despite appearances they were never the drift.)

## [0.26.2] - 2026-06-11

### Fixed
- `bon move` to a JSONL-backed target board now warns when the move leaves the target repo's board uncommitted. Documentation counts trued up.

## [0.26.1] - 2026-06-11

### Added
- `/close` gains an empty-outcome check and a CLAUDE.md-drift question; fond-v1 handoff spec tightened (bon-capibo, bon-hofati, bon-solifa).

## [0.26.0] - 2026-06-11

### Added
- `bon move` verb — relocate an item to another repo's board (cross-repo re-homing).

### Fixed
- Three field reports: cwd-echo error messages, `edit --parent` documentation, and dashboard window inference.

## [0.25.1] - 2026-06-11

### Fixed
- Packaging: top-level `scripts/` (close-context.sh, open-context.sh, bon-read.sh) now ships in the marketplace package again. The batterie assembler's lean copy-list dropped it at the 2026-06-10 cutover, so `/close` couldn't find close-context.sh and the session-start hook silently skipped open-context.sh (fail-open `[ -x ]` + `|| true`). Fix is in batterie's assemble.sh; this bump propagates it.

## [0.23.1] - 2026-06-09

### Fixed
- Session-start hook no longer deletes handoffs on resume. The rm was added for auto-handoffs (retired 2026-04-05), then widened on 2026-04-06 to match dated `/close` handoffs too — so any resume of a closed session (including harness bridge-syncs, which fire SessionStart with source=resume) silently deleted the committed handoff from the working tree. Four handoffs in itv-slides-formatter were lost this way (all git-recoverable).

## [0.21.0] - 2026-04-16

### Changed
- Replaced `context-budget.sh` with `session-dashboard.sh` — a per-turn dashboard that reports context as % free (abundance framing), detects session gaps, compaction, permission mode changes, and branch changes. Uses `transcript_path` from hook stdin instead of globbing the project dir for the newest `.jsonl` (which misattributed a stale transcript's usage to the current session at startup).
- Low-context nudge uses identical language at 20% free and 1% free — no escalation curve. The numbers carry the signal; escalating urgency amplifies the vectors that degrade output quality exactly when calm matters most.

### Removed
- `hooks/context-budget.sh` — replaced by the dashboard.

## [0.8.1] - 2026-03-21

### Added
- Dolt server systemd service docs in README (setup, config, user service file)
- Session-start hook detects `.bon/backend` — Dolt projects use CLI instead of stale file reads
- Connection failures surface in briefing with recovery command (`systemctl --user start dolt-bon.service`)
- `manifest.json` supports `extras` field for CLI tool install (e.g. `"extras": "dolt"`)
- `ensure-bon.sh` install hint includes `[dolt]` extras

### Changed
- `bon migrate --to dolt` renames `items.jsonl` → `items.jsonl.pre-dolt` (prevents stale reads by hooks)
- `setup.sh` and `update-all.sh` pass extras to `uv tool install` when declared in manifest

### Security
- Dolt server docs use scoped `bon` user instead of `root` (localhost-only, db-scoped grants)

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
