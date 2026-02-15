# Arc → Bon Rename Plan

**Bon** = kitchen ticket/order slip in a French brigade kitchen.
Joins the suite: **Guéridon** (mobile service), **Aboyeur** (orchestrator), **Mise en Space** (workspace prep), **Bon** (the ticket).

## Phases

### Phase 1: Core Package Rename (this repo) ✅ DONE

Completed 2026-02-14. All 270 tests pass. `bon` installed as uv tool.

- `src/arc/` → `src/bon/` (cli.py, storage.py, ids.py, display.py, queries.py, migrate.py, __init__.py)
- `pyproject.toml` — name `bon`, script `bon = "bon.cli:main"`, wheel `src/bon`
- All imports in `tests/` — `from arc.` → `from bon.`, fixtures create `.bon/`
- CLI strings — prog `bon`, all help text, all error messages
- `ArcError` → `BonError`, `BON_USER` env var (falls back to `ARC_USER`)
- `_data_dir()` helper in storage.py — checks `.bon/` first, falls back to `.arc/`
- `check_initialized()` accepts either `.bon/` or `.arc/`
- `cmd_init` creates `.bon/`, default prefix `"bon"`
- `load_prefix()` default `"bon"`, `generate_id()` default prefix `"bon"`
- Bundled skill — `arc/` → `bon/` (SKILL.md, field-reports, references)
- Gemini — `gemini/commands/bon.toml`, `gemini/skills/bon/`, extension name `bon-work-tracker`
- Hooks — `hooks/bon-tactical.sh` (symlink, target doesn't exist yet — created in Phase 3)
- Docs — SPEC.md, AGENTS.md, CLAUDE.md, README.md all updated
- `uv lock` regenerated, `src/arc/` deleted
- `uv tool install .` done — `bon` available in PATH

**Learnings:**
- Test fixtures keep `prefix` file as `"arc"` because fixture JSONL data contains `arc-` prefixed IDs. The prefix file controls ID generation and prefix-tolerant lookup — it must match the data, not the tool name.
- `_data_dir()` is used by load_items, save_items, load_prefix, load_archive, append_archive, remove_from_archive. `check_initialized()` does its own dual-path check.
- `migrate_from_draft` creates `.bon/` (not using `_data_dir()` — it's a fresh init).
- The `hooks/bon-tactical.sh` symlink points to trousse's not-yet-renamed file. It's a broken symlink on this machine — will resolve after Phase 3.

### Phase 2: `bon migrate-repo` Command ✅ DONE

Completed 2026-02-14. All 289 tests pass.

Add a CLI command that automates consumer repo migration:
```bash
bon migrate-repo          # in any repo with .arc/
# Renames .arc/ → .bon/
# Updates .gitattributes (.arc/*.jsonl → .bon/*.jsonl)
# Commits with standard message
```

**Notes from Phase 1:**
- Should also update the `prefix` file content if it reads `"arc"` (the default). Repos with custom prefixes (e.g., `mise`, `garde`) keep theirs.
- Consider a `--dry-run` flag to preview changes.
- The `.arc/` fallback in `_data_dir()` means un-migrated repos still work — no urgency.

### Phase 3: Trousse ✅ DONE

Completed 2026-02-14. 127 tests pass (2 pre-existing skill-forge failures unrelated).

- `hooks/arc-tactical.sh` → `hooks/bon-tactical.sh` (checks .bon/ first, .arc/ fallback)
- `scripts/arc-read.sh` → `scripts/bon-read.sh` (dual-path detection)
- `tests/test_arc_read.py` → `tests/test_bon_read.py` (all references updated)
- `scripts/open-context.sh` — all ARC_ vars → BON_, `arc.txt` → `bon.txt`, dual-dir checks
- `scripts/auto-handoff.sh` — ARC_ vars → BON_, dual-path items detection
- `scripts/close-context.sh` — ARC_ vars → BON_, checks .bon/ or .arc/
- `scripts/claude-doctor.sh` — skill list `arc` → `bon`, hook list updated
- `hooks/session-end.sh` — comment updated
- `install.sh` — hook registration `bon-tactical.sh`, optional tools text
- `skills/open/SKILL.md` — ~25 arc→bon references updated
- `skills/close/SKILL.md` — 5 arc→bon references updated
- `skills/sprite/references/setup.md` — arc→bon in setup steps
- `CLAUDE.md`, `README.md`, `.gitattributes` — all updated
- **Beads scrub**: Deferred (separate task)

**Learnings:**
- All scripts use dual-path detection (.bon/ first, .arc/ fallback) matching bon's `_data_dir()` pattern
- The `~/.claude/hooks/bon-tactical.sh` symlink (created in Phase 5) now resolves correctly

### Phase 4: Garde-Manger ✅ DONE

Completed 2026-02-15. All 108 tests pass.

- `src/garde/adapters/arc.py` → `bon.py`, class `ArcSource` → `BonSource`, `discover_arc` → `discover_bon`
- `src/garde/cli.py` — `--source bon` (removed `arc` and `beads`), all scan variables renamed
- `config.yaml.template` — `sources.arc` → `sources.bon`, paths `.arc/` → `.bon/`
- `skill/SKILL.md` — `bd create` bug templates → `bon new` templates (narrative "arc" refs left as-is)
- `skill/references/WORKFLOWS.md` — `arc ready/show` → `bon ready/show`, section title updated
- `skill/references/TROUBLESHOOTING.md` — filing template updated
- `README.md`, `CLAUDE.md`, `AGENTS.md` — all arc→bon, GitHub URL updated
- New scans index as `source_type='bon'`; existing `source_type='arc'` entries remain in DB
- **Beads scrub (garde-manger)**: Deleted `adapters/beads.py`, `tests/test_beads_adapter.py`, removed `--source beads` from CLI, removed beads scan loop, removed beads from summary output

### Phase 5: ~/.claude Config ✅ DONE

Completed 2026-02-14.

- `skills/arc` symlink → `skills/bon` → `~/Repos/arc/bon`
- `hooks/arc-tactical.sh` → `hooks/bon-tactical.sh` → trousse (broken until Phase 3)
- `settings.json` — `Skill(arc)` → `Skill(bon)`, hook path updated
- `CLAUDE.md` — all arc/Arc references → bon/Bon (CLI commands, data dirs, skill refs, memory table)
- `README.md` — deferred (beads scrub)
- `rules/repos.md` — no arc-specific references, skipped
- `memory/glossary.yaml` — `arc` entity → `bon` with `arc` as alias
- `uv tool uninstall arc` — deferred to Phase 6 cleanup

### Phase 6: Consumer Repos (15 repos) ✅ DONE

Completed 2026-02-14. All 15 repos migrated with `bon migrate-repo`.

- All 15 repos: .arc/ → .bon/, .gitattributes updated where present, committed
- Prefix updated to 'bon' in: claude-mem, garde-manger, arc (had default 'arc' prefix)
- Repos with custom prefixes kept theirs (todoist, mise, garde, etc.)
- Required `uv tool install --reinstall` to pick up Phase 2's migrate-repo command

### Phase 7: GitHub ✅ DONE

Completed 2026-02-15.

- Updated git remote: `origin` → `https://github.com/spm1001/bon.git`
- Updated `README.md` clone URL and paths (`arc` → `bon`)
- Updated `trousse/README.md` kitchen table link
- Updated `trousse/skills/sprite/references/setup.md` install URL
- garde-manger URLs updated as part of Phase 4
- **Remaining manual step**: Rename repo `spm1001/arc` → `spm1001/bon` on GitHub (Settings → General → Repository name)

## Recommended Execution Order

The original phase numbering implies strict sequence, but some phases have dependencies that suggest reordering:

1. **Phase 1** ✅ (done)
2. **Phase 5** ✅ (done — symlinks, settings, CLAUDE.md, glossary)
3. **Phase 2** ✅ (done — `bon migrate-repo` command)
4. **Phase 3** ✅ (done — trousse hooks, scripts, skills, docs)
5. **Phase 6** ✅ (done — all 15 consumer repos migrated)
6. **Phase 4** ✅ (done — garde-manger adapter, beads scrub, docs)
7. **Phase 7** ✅ (done — URLs updated, GitHub rename pending)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Transition window — `bon` looks for `.bon/`, repo still has `.arc/` | ✅ `_data_dir()` fallback shipped in Phase 1 |
| `~/.claude/skills/arc` symlink broken (old target deleted) | Fix in Phase 5 — repoint to `~/Repos/arc/bon` |
| settings.json hook path breaks | Atomic update — same commit as hook rename (Phase 5) |
| garde-manger DB has `source_type='arc'` | SQL migration, or accept dual types |
| Existing `arc-` prefixed item IDs | ✅ Prefix-tolerant IDs work; fixture prefix stays `"arc"` |
| `uv tool install` on all machines | `uv tool uninstall arc && uv tool install ~/Repos/arc` |
| Stale `arc.txt` session context files | open-context.sh regenerates; old files harmless |
| Test fixtures use `"arc"` prefix | ✅ By design — data has `arc-` IDs, prefix must match |

## Beads Scrub ✅ DONE

Completed 2026-02-15.

- `~/.claude/CLAUDE.md` — removed beads migration reference
- `~/.claude/README.md` — removed beads sections and beads-tracking repo link
- `trousse/skills/open/SKILL.md` — removed `.beads/` fallback rows
- `trousse/skills/close/SKILL.md` — removed beads references (5 locations)
- `trousse/skills/setup/SKILL.md` — removed beads install check and verification
- `trousse/skills/filing/SKILL.md` — updated skill list (beads → bon)
- `trousse/skills/skill-forge/` — removed beads CLI pattern, updated scan.py exclude
- `trousse/skills/picture/ & diagram/` — already clean (no beads refs)
- `trousse/skills/github-cleanup/` — updated .beads/ → .bon/ in structure
- `trousse/scripts/open-context.sh` — removed beads deprecation block
- `trousse/hooks/session-end.sh` — `--source beads` → `--source bon`
- `garde-manger/src/garde/adapters/beads.py` — deleted (Phase 4)
- `infra-workstation/` — updated update-dev-tools.sh, ADDITIONAL_TOOLS.md, plans
- Handoffs are archival — not touched
