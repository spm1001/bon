# Agent Instructions

**Arc** — Lightweight work tracker for agent-human collaboration. JSONL-based, Git-tracked.

## Quick Commands

```bash
arc list                     # See all items
arc list --ready             # See unblocked work
arc show <id>                # View item details
arc new outcome "Title"      # Create desired outcome
arc new action -p OUT "Title"  # Create action under outcome
arc done <id>                # Mark complete
arc --help                   # Full CLI help
```

## GTD Vocabulary

Arc uses GTD terms:

| Arc Term | Meaning |
|----------|---------|
| Outcome | Desired result (has children) |
| Action | Concrete step (has parent, waiting_for) |
| Brief | Required context: why, what, done criteria |

## Data Model

Items live in `.arc/items.jsonl`. Two types:

- **Outcome**: Goal to achieve (can have child actions)
- **Action**: Concrete next step (can wait on another item)

Both require `brief: {why, what, done}` — all three non-empty.

## Development

```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_X.py    # Run specific test file
uv run arc list                  # Test CLI locally
```

## Project Structure

```
src/arc/
├── cli.py        # All commands, argparse, entry point
├── storage.py    # JSONL I/O, validation, prefix management
├── ids.py        # ID generation (pronounceable 3-syllable)
├── display.py    # Output formatting
└── queries.py    # Filtering (ready, waiting)

tests/            # pytest suite
fixtures/         # JSONL snapshots
skill/SKILL.md    # Claude Code integration
```

## Key Behaviors

1. **Unblock on Done**: Marking an item done unblocks items waiting for it
2. **Prefix-Tolerant IDs**: `gaBdur` and `arc-gaBdur` both work
3. **Atomic Writes**: All saves go through `save_items()` (temp file + rename)

## Spec-Driven

`SPEC.md` is authoritative. When behavior is unclear, check the spec. Tests derive from spec examples.
