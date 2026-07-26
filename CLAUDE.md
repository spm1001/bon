# CLAUDE.md

Guidance for working on bon (the codebase, not with bon).

## What This Is

Bon is a lightweight work tracker for Claude-human collaboration. JSONL default, optional Dolt backend, Git-tracked. 21 commands (incl. cross-repo `bon move` and Dolt `bon register`), ~3100 LOC core (+700 optional Dolt module), 563 tests (13 are opt-in Dolt integration via BON_DOLT_TEST=1).

## Versioning & releasing (suite-managed)

bon ships as part of the **Batterie de Savoir** suite, which carries **one suite-wide version**. So:

- **Do NOT hand-bump `.claude-plugin/plugin.json` to release.** This repo's own `plugin.json` version is **local-dev-only** — the assembler stamps every published plugin to the suite version, overwriting it.
- **Release via `/batterie:publish`** from this working tree — it bumps the suite version centrally and ships the change (a 2-repo push: this repo + the central suite bump). Never hand-run the assemble.
- **A `CLAUDE.md` / `instructions.md` / `skills/` / `hooks/` edit here is vendored content** — it must ride a suite bump (a publish) to actually ship, or the assembler quarantines the plugin. `docs/` / `.bon/` edits are free.
- **`bon --version` is separate** — it reads *the suite release that last changed bon* (publish.py lazy-stamps only the repo it publishes), so a CLI number **below** the current suite number is expected, not drift.

Full picture: `spm1001/batterie-de-savoir` → `CLAUDE.md` "Versioning convention" + `.bon/understanding.md`.

## Quick Commands

```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_X.py    # Run specific test file
uv run bon list                  # See current bon state
uv run bon --help                # CLI help
```

## Project Structure

```
src/bon/
├── cli.py        # All commands, argparse setup, main entry point
├── storage.py    # JSONL I/O, validation, prefix management, dedup, backend dispatch
├── dolt.py       # Optional Dolt backend (lazily imported, requires pymysql)
├── ids.py        # ID generation (pronounceable 3-syllable)
├── display.py    # Output formatting (hierarchical, JSON, JSONL)
└── queries.py    # Filtering (ready, waiting)

tests/            # pytest suite, one file per command
fixtures/         # JSONL snapshots for parametrized tests
skills/open/SKILL.md     # Claude Code integration (session ritual + draw-down discipline)
```

## Module Dependencies

Verified against imports (2026-06-20). Intra-package edges only:

```
cli      ──▶ display, storage, ids, queries     (+ dolt, lazy/function-local)
storage  ──▶ ids                                (+ dolt, lazy)   ── dolt ⇄ storage (mutual, lazy)
display  ──▶ ids, queries
dolt     ──▶ storage
ids, queries ── leaves (no intra-package imports)
```

- **`ids` and `queries` are leaves** — nothing in-package depends *up* from them; safe to read first.
- **A change to `ids`** (ID generation, ordering) is the most load-bearing leaf — it ripples into `storage`, `display`, and `cli`.
- **`dolt` ⇄ `storage` are mutually dependent, but lazily**: `storage` imports `dolt` functions only inside backend branches; `dolt` imports `storage` helpers. Edit either, check the other.
- Dolt imports are function-local throughout, so the optional backend never loads unless a repo uses it.

## Data Model

Items live in `.bon/items.jsonl` (or a Dolt database when using the optional backend). Two types:

- **Outcome**: Desired result (has children)
- **Action**: Concrete step (has parent, waiting_for)

Both require `brief: {why, what, done}` — all three non-empty. Optional `how` field captures approach/strategy.

## Adding a Command

1. Add handler in `cli.py`:
   ```python
   def cmd_mycommand(args):
       check_initialized()
       items = load_items()
       # ... implementation
       save_items(items)
   ```

2. Register subparser in `main()`:
   ```python
   mycommand_parser = subparsers.add_parser("mycommand", help="...")
   mycommand_parser.set_defaults(func=cmd_mycommand)
   ```

3. Create `tests/test_mycommand.py` using `run_bon()` helper

4. Update README.md command table

## Critical Behaviors

### Unblock on Done

When marking done, items waiting for it are automatically unblocked:
```python
for other in items:
    if other.get("waiting_for") == item["id"]:
        other["waiting_for"] = None
```
This is the dependency mechanism. Don't break it.

### Prefix-Tolerant ID Matching

Users can type `gabdur` instead of `bon-gabdur`. The `find_by_id()` function handles this — always use it for lookups.

### Atomic Writes

`save_items()` writes to `.tmp` then renames. Don't bypass this.

### The Bottle (.bon/README.md)

`bon init` writes `.bon/README.md` — the "message in a bottle" telling a stranger
Claude (no CLI, any vendor) how to read the board and route writes as handoff
candidates — and prints a CLAUDE.md/AGENTS.md discovery stanza. The canonical text
is `BOARD_README` in `storage.py`. Every `save_items()`/`save_items_at()` refreshes
a missing or stale copy on the back of the write (same parasitic pattern as Dolt
repos-table registration), and `bon doctor` reports staleness / `bon doctor --fix`
repairs it without touching items. So a wording change to `BOARD_README` converges
the estate's static copies as boards get written; dormant boards take the doctor
route.

### Merge-Friendly Storage

`save_items()` sorts by ID before writing, producing deterministic line order.
`.gitattributes` uses `merge=union` for `.bon/*.jsonl` so concurrent branches
that touch different items merge cleanly. `load_items()` deduplicates by ID
(last occurrence wins) to handle union merge artifacts where both old and new
versions of an edited line survive.

**What merges cleanly:** Two branches adding different items. Two branches
editing different items (when 3+ unchanged lines separate them).

**What still conflicts:** Two branches editing the same item, or editing
adjacent items. This is acceptable — it means two sessions touched the same
work, which needs human resolution anyway.

## Testing Patterns

**Fixtures** (`fixtures/*.jsonl`): Snapshot data for parametrized tests
**Runner** (`conftest.py`): `run_bon(*args, cwd=...)` subprocess helper

```python
def test_something(bon_dir):
    result = run_bon("list", cwd=bon_dir)
    assert result.returncode == 0
    assert "Expected output" in result.stdout
```

Parametrized fixture loading:
```python
@pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
def test_with_data(bon_dir_with_fixture):
    result = run_bon("list", cwd=bon_dir_with_fixture)
```

## Common Patterns in cli.py

```python
check_initialized()              # Always first — errors if no .bon/
items = load_items()             # Load current state
prefix = load_prefix()           # Get ID prefix
item = find_by_id(items, id, prefix)  # Lookup (handles prefix tolerance)
error("Message")                 # Print to stderr, exit 1
save_items(items)                # Atomic write back
```

### `bon new` Input Modes

`bon new` accepts items via three paths, auto-detected:

1. **JSON stdin (default for piped input)**: No title arg + stdin is piped → reads JSON from stdin. No `--json` flag needed.
2. **Flags**: Title as positional arg + `--why`/`--what`/`--done` flags. For quick stubs.
3. **Interactive**: TTY + no flags → prompts for brief fields.
4. **Explicit `--json`**: Forces JSON stdin regardless of other args. Backward-compatible.

```bash
cat <<'EOF' | bon new -q          # JSON stdin (auto-detected)
{"title":"...","brief":{"why":"...","what":"...","done":"..."}}
EOF
bon new "Quick fix" --why w --what x --done d -q   # Flags (stubs only)
```

## Gotchas

| Gotcha | Fix |
|--------|-----|
| Forgetting `check_initialized()` | Add at command start |
| Direct file writes | Use `save_items()` for atomicity |
| Reading JSONL by line position | Items are sorted by ID, not insertion order. Find by type/ID, not `lines[N]` |
| Case-sensitive ID lookup | Use `find_by_id()` with prefix |
| Breaking unblock-on-done | Test with `waiting_dependency` fixture |
| Standalone actions forgotten | Check items where `parent` is None. Create with `type: "action"` in JSON stdin |
| Interactive mode untested | Test with `input=` parameter |
| Mixed-case IDs (bon-huHida) | Pre-lowercase legacy. IDs are immutable — don't try to rename |
| Changing schema fields | bon-read.sh reads items.jsonl directly with jq |
| Tactical lookup ignoring session | Always pass `session=os.getcwd()` to `find_active_tactical()`. Omitting it returns only unscoped (legacy) tacticals. |
| Stale global install after code changes | `uv tool install` reuses a cached *build* of the local source, and `uv cache clean bon` does **not** clear it. Since bon's version is dynamic from `plugin.json` (hatchling regex-read), a bump touching only `plugin.json`/CLAUDE.md leaves `src/` byte-identical, so the old wheel is reused and the version never moves (verified 2026-06-17). Force a real rebuild with `--no-cache`: `uv tool install ~/repos/spm1001/bon --force --reinstall --no-cache --with pymysql` |
| Calling `items_path()` in Dolt mode | Raises `BonError`. Check `_get_backend()` first, or use `load_items()`/`save_items()` which dispatch automatically. |
| Dolt backend without pymysql | `BonError` with install instructions. Install: `pip install bon[dolt]` |
| Session identity differs per backend | Use `get_session_identity()` not `os.path.realpath(os.getcwd())`. Dolt mode prefixes with hostname. |
| `_get_backend()` caching | Follows same pattern as `_data_dir()`. One file read per process. Reset with `_reset_backend()` in tests. |

## Storage Backends

Bon supports two backends: **JSONL** (default) and **Dolt** (optional).

- JSONL: `.bon/items.jsonl`, git-tracked, zero dependencies
- Dolt: MySQL-compatible DB with git semantics, requires `pymysql` (`pip install bon[dolt]`)

Backend is set per-project in `.bon/backend` (absent = jsonl). All Dolt code lives in `src/bon/dolt.py`, lazily imported. Dispatch happens at the function boundary in `storage.py` — cli.py doesn't change.

**The Dolt database carries a `repos` mapping table** (prefix → repo_name, origin_url) so estate-wide consumers (the /review survey) can label prefixes without a local clone. Boards self-register: every Dolt write upserts the row inside the existing transaction (SELECT-compare first, so unchanged identity writes nothing), `init --backend dolt` and `migrate --to dolt` register explicitly, and `bon register` is the manual/backfill path. Unmapped prefixes are surfaced as such — never guessed.

**Dolt write strategy is truncate-and-reinsert** (DELETE prefix rows + INSERT all, in one transaction). This deliberately mirrors JSONL semantics (rewrite the whole file). Do not "optimize" to per-item UPSERT/DELETE — that changes the concurrency model and breaks the parallel between backends.

```bash
bon init --prefix myproj --backend dolt   # New project with Dolt
bon migrate --to dolt                      # Existing project to Dolt
bon migrate --to jsonl                     # Back to JSONL
```

## Key Files

| Need to... | Read... |
|------------|---------|
| Understand architecture & invariants | `.bon/understanding.md` |
| See expected outputs | `fixtures/*.jsonl` |
| Add/modify command | `cli.py` |
| Change storage format | `storage.py` |
| Dolt backend logic | `dolt.py` |
| Update Claude integration | `skills/open/SKILL.md` |
| Docket/rite boundary (probe, query surface, ownership) | `docs/CONTRACT.md` |
| Handoff format spec | `docs/HANDOFF-CONTRACT.md` |
| Where handoffs/understanding.md resolve (READ+WRITE share this) | `scripts/lib-handoff.sh` |
| Test bon-read.sh | `tests/test_bon_read.py` |



## README skill table is generated

The Skills table in README.md (between `GENERATED:SKILLS` markers) is rendered from
`skills/*/SKILL.md` frontmatter — never hand-edit it. After adding, removing or renaming
a skill: `uv run --script ../batterie-de-savoir/scripts/render-skills.py .` from the repo
root. CI re-checks it on every push (fetching the canonical script from batterie-de-savoir
raw main), so a stale table fails the build. If a table one-liner reads badly, fix the
SKILL.md description (skill-forge), not the table.
