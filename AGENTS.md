# Agent Instructions

**Bon** — Lightweight work tracker for agent-human collaboration. JSONL-based, Git-tracked.

## Quick Commands

```bash
bon list                     # See all items
bon list --ready             # See unblocked work
bon show <id>                # View item details
bon new "Title"              # Create desired outcome
bon new "Title" --outcome OUT --why "..." --what "..." --done "..."
                             # Create action under outcome
bon done <id>                # Mark complete
bon work <id>                # Start tactical steps
bon step                     # Advance to next step
bon --help                   # Full CLI help
```

## GTD Vocabulary

Bon uses GTD terms:

| Bon Term | Meaning |
|----------|---------|
| Outcome | Desired result (has children) |
| Action | Concrete step (has parent, waiting_for) |
| Brief | Required context: why, what, done criteria |

## Data Model

Items live in `.bon/items.jsonl`. Two types:

- **Outcome**: Goal to achieve (can have child actions)
- **Action**: Concrete next step (can wait on another item)

Both require `brief: {why, what, done}` — all three non-empty.

## Development

```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_X.py    # Run specific test file
uv run bon list                  # Test CLI locally
```

## Project Structure

```
src/bon/
├── cli.py        # All commands, argparse, entry point
├── storage.py    # JSONL I/O, validation, prefix management
├── ids.py        # ID generation (pronounceable 3-syllable)
├── display.py    # Output formatting
└── queries.py    # Filtering (ready, waiting)

tests/            # pytest suite
fixtures/         # JSONL snapshots
bon/SKILL.md    # Claude Code integration
```

## Key Behaviors

1. **Unblock on Done**: Marking an item done unblocks items waiting for it
2. **Prefix-Tolerant IDs**: `gabdur` and `bon-gabdur` both work
3. **Atomic Writes**: All saves go through `save_items()` (temp file + rename)

## Spec-Driven

`SPEC.md` is authoritative. When behavior is unclear, check the spec. Tests derive from spec examples.
