# CLAUDE.md

Guidance for working on bon (the codebase, not with bon).

## What This Is

Bon is a lightweight work tracker for Claude-human collaboration. JSONL-based, no daemon, Git-tracked. 17 commands, ~1800 LOC core, 253 tests.

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
├── storage.py    # JSONL I/O, validation, prefix management, dedup
├── ids.py        # ID generation (pronounceable 3-syllable)
├── display.py    # Output formatting (hierarchical, JSON, JSONL)
└── queries.py    # Filtering (ready, waiting)

tests/            # pytest suite, one file per command
fixtures/         # JSONL snapshots for parametrized tests
bon/SKILL.md      # Claude Code integration patterns
```

## Data Model

Items live in `.bon/items.jsonl`. Two types:

- **Outcome**: Desired result (has children)
- **Action**: Concrete step (has parent, waiting_for)

Both require `brief: {why, what, done}` — all three non-empty.

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

## Gotchas

| Gotcha | Fix |
|--------|-----|
| Forgetting `check_initialized()` | Add at command start |
| Direct file writes | Use `save_items()` for atomicity |
| Reading JSONL by line position | Items are sorted by ID, not insertion order. Find by type/ID, not `lines[N]` |
| Case-sensitive ID lookup | Use `find_by_id()` with prefix |
| Breaking unblock-on-done | Test with `waiting_dependency` fixture |
| Standalone actions forgotten | Check items where `parent` is None |
| Interactive mode untested | Test with `input=` parameter |
| Mixed-case IDs (bon-huHida) | Pre-lowercase legacy. IDs are immutable — don't try to rename |
| Changing schema fields | trousse reads items.jsonl directly with jq (see FIELD_REPORT_jq_consumers.md) |
| Tactical lookup ignoring session | Always pass `session=os.getcwd()` to `find_active_tactical()`. Omitting it returns only unscoped (legacy) tacticals. |

## Key Files

| Need to... | Read... |
|------------|---------|
| Understand exact behavior | `SPEC.md` (canonical) |
| See expected outputs | `fixtures/*.jsonl` |
| Add/modify command | `cli.py` |
| Change storage format | `storage.py` |
| Update Claude integration | `bon/SKILL.md` |

## Spec-Driven Development

`SPEC.md` is authoritative (~55k). When behavior is unclear, check the spec. Tests are often derived from spec examples.


