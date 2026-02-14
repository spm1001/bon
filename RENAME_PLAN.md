# Arc → Bon Rename Plan

**Bon** = kitchen ticket/order slip in a French brigade kitchen.
Joins the suite: **Guéridon** (mobile service), **Aboyeur** (orchestrator), **Mise en Space** (workspace prep), **Bon** (the ticket).

## Phases

### Phase 1: Core Package Rename (this repo)

- `src/arc/` → `src/bon/` (cli.py, storage.py, ids.py, display.py, queries.py, __init__.py)
- `pyproject.toml` — name, scripts entry, wheel packages path
- All imports in `tests/` — `from arc.` → `from bon.`
- CLI strings — prog name, help text, user-facing messages
- Storage directory constant — `.arc/` → `.bon/` (but with `.arc/` fallback for transition)
- Bundled skill — `arc/SKILL.md` → `bon/SKILL.md`, field-reports, references
- Gemini — `gemini/commands/arc.toml` → `bon.toml`, `gemini/skills/arc/` → `bon/`
- Hooks — `hooks/arc-tactical.sh` → `hooks/bon-tactical.sh`
- Docs — SPEC.md, AGENTS.md, CLAUDE.md, README.md, GUIDE.md, NOTES.md, DESIGN_*.md, FIELD_REPORT_*.md, ORCHESTRATION.md
- `uv lock` to regenerate lockfile
- All tests must pass: `uv run pytest`

**Transition rule:** storage.py looks for `.bon/` first, falls back to `.arc/`. Existing IDs with `arc-` prefix remain valid.

### Phase 2: `bon migrate-repo` Command

Add a CLI command that automates consumer repo migration:
```bash
bon migrate-repo          # in any repo with .arc/
# Renames .arc/ → .bon/
# Updates .gitattributes (.arc/*.jsonl → .bon/*.jsonl)
# Commits with standard message
```

### Phase 3: Trousse

- `hooks/arc-tactical.sh` → `hooks/bon-tactical.sh` (references `.bon/items.jsonl`)
- `scripts/arc-read.sh` → `scripts/bon-read.sh`
- `tests/test_arc_read.py` → `tests/test_bon_read.py`
- `skills/open/SKILL.md` — ~25 arc→bon references, `.arc/`→`.bon/` checks
- `skills/close/SKILL.md` — `arc new` → `bon new` etc
- `install.sh` — hook registration, install instructions
- Other skills with scattered references (filing, setup, titans, skill-forge, sprite)
- `README.md`
- **Beads scrub**: Remove `.beads/` fallback logic, stale beads references, dead gitattributes

### Phase 4: Garde-Manger

- `src/garde/adapters/arc.py` → `bon.py`, class `ArcSource` → `BonSource`
- `src/garde/cli.py` — `--source arc` → `--source bon`, scan variables
- `config.yaml.template` — `sources.arc` → `sources.bon`, glob paths
- `skill/SKILL.md`, `README.md`, `CLAUDE.md`
- DB: keep `source_type='arc'` entries, add SQL migration to update to `'bon'`
- **Beads scrub**: Delete `adapters/beads.py`, remove `--source beads` from CLI choices, remove scan loop (data persists in DB)

### Phase 5: ~/.claude Config

- `settings.json` — `"Skill(arc)"` → `"Skill(bon)"`, hook path `arc-tactical.sh` → `bon-tactical.sh`
- `CLAUDE.md` — all arc references → bon
- `README.md` — remove stale beads sections, update arc→bon
- `rules/repos.md` — update skill listing
- `skills/arc/` symlink → `skills/bon/`
- `memory/glossary.yaml` — update arc entry
- **Must be atomic** — settings.json and hook file rename in same commit

### Phase 6: Consumer Repos (15 repos)

Run `bon migrate-repo` in each:
todoist-gtd, skill-sandbox, gueridon, claude-mem, skill-chrome-log, freeview-coverage,
infra-workstation, itv-linkedin-analytics, garde-manger, passe, trousse, infra-mac-setup,
_sandbox, mise-en-space, arc/bon itself.

### Phase 7: GitHub

- Rename `spm1001/arc` → `spm1001/bon` (GitHub auto-redirects old URLs)
- Update git remote in local clone

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Transition window — `bon` looks for `.bon/`, repo still has `.arc/` | Phase 1 ships with `.arc/` fallback in storage.py |
| settings.json hook path breaks | Atomic update — same commit as hook rename |
| garde-manger DB has `source_type='arc'` | SQL migration, or accept dual types |
| Existing `arc-` prefixed item IDs | Prefix-tolerant IDs already work; just update prefix file |
| `uv tool install` on all machines | Document in plan; uninstall old, install new |
| Stale `arc.txt` session context files | open-context.sh regenerates; old files harmless |

## Beads Scrub (parallel with any phase)

- `~/.claude/CLAUDE.md` — remove beads migration reference
- `~/.claude/README.md` — remove stale beads sections
- `trousse/skills/open/SKILL.md` — remove `.beads/` fallback
- `trousse/skills/close/SKILL.md` — remove beads references
- `trousse/skills/setup/SKILL.md` — remove beads install check
- `trousse/skills/filing/SKILL.md` — fix stale beads in skill list
- `trousse/skills/skill-forge/` — remove beads from CLI pattern reference
- `trousse/skills/picture/ & diagram/` — delete `.beads` gitattributes
- `trousse/skills/github-cleanup/` — remove `.beads/` from structure
- `trousse/scripts/open-context.sh` — remove beads deprecation block
- `trousse/hooks/session-end.sh` — remove `--source beads` from garde scan
- `garde-manger/src/garde/adapters/beads.py` — delete (data already in DB)
- Handoffs are archival — don't touch
