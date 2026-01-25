# Arc

Lightweight work tracker for Claude-human collaboration using GTD vocabulary.

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points — just ordering and a clear answer to "what can I work on now?"

## Install

```bash
# Clone and install with uv
git clone https://github.com/spm1001/arc.git
cd arc
uv sync

# Run
uv run arc --help
```

## Quick Start

```bash
# Initialize in your project
uv run arc init

# Create an outcome (desired result)
uv run arc new "Users can export data" \
  --why "Users requesting CSV exports" \
  --what "Export button, CSV generation, download" \
  --done "Can export any table to CSV"

# Add actions to that outcome
uv run arc new "Add export button to toolbar" \
  --for arc-abcdef \
  --why "Entry point for export flow" \
  --what "Button in toolbar, opens format picker" \
  --done "Button visible, click opens modal"

# See what's ready
uv run arc list --ready

# Mark done when complete
uv run arc done arc-ghijkl
```

## Commands

| Command | Description |
|---------|-------------|
| `init [--prefix P]` | Initialize `.arc/` directory |
| `new TITLE [--for PARENT] --why W --what X --done D` | Create outcome or action |
| `list [--ready\|--waiting\|--all]` | Show items hierarchically |
| `show ID` | View item details and brief |
| `done ID` | Mark item complete |
| `wait ID REASON` | Mark as waiting for something |
| `unwait ID` | Clear waiting status |
| `edit ID` | Edit item in $EDITOR |
| `status` | Show counts overview |
| `help [CMD]` | Show help |

### Output Flags

- `--json` — Nested JSON (for `list`, `show`)
- `--jsonl` — Flat JSONL, one item per line (for `list`)
- `--quiet` / `-q` — Minimal output, just the ID (for `new`)

### List Filters

```bash
arc list              # Open outcomes + their actions
arc list --ready      # Only items ready to work on (no waiting)
arc list --waiting    # Only items blocked/waiting
arc list --all        # Include done items
```

## Data Model

Arc stores work in `.arc/items.jsonl` as two item types:

**Outcomes** — Desired results that matter. Have child actions.
```json
{
  "id": "arc-abcdef",
  "type": "outcome",
  "title": "Users can export data",
  "brief": { "why": "...", "what": "...", "done": "..." },
  "status": "open"
}
```

**Actions** — Concrete next steps. Belong to outcomes.
```json
{
  "id": "arc-ghijkl",
  "type": "action",
  "title": "Add export button",
  "parent": "arc-abcdef",
  "waiting_for": null,
  "brief": { "why": "...", "what": "...", "done": "..." },
  "status": "open"
}
```

### Brief Field

Every item requires a brief with three fields:

| Field | Question |
|-------|----------|
| `why` | Why are we doing this? |
| `what` | What will we produce? |
| `done` | How do we know it's complete? |

Interactive mode prompts for these. Non-interactive requires all three flags.

## Claude Code Integration

Arc includes a skill for Claude Code at `skill/SKILL.md`. Symlink to use:

```bash
ln -s /path/to/arc/skill ~/.claude/skills/arc
```

The skill teaches Claude:
- **Draw-down pattern**: Read arc item → create TodoWrite checkpoints → work with pauses
- **Draw-up pattern**: File work with complete briefs for future sessions
- **When to use arc vs TodoWrite**: Multi-session = arc, single-session = TodoWrite

## Why Arc?

Arc was built after discovering that Claude working without checkpoints leads to drift. Complex work needs:

1. **Clear scope** — Brief fields force "why/what/done" clarity
2. **Checkpoints** — Draw-down to TodoWrite creates pause points
3. **Handoff** — Briefs written for zero-context readers survive session boundaries

See `ORCHESTRATION.md` for patterns used to build arc with Claude.

## Development

```bash
# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_done.py -k "test_done"
```

## License

MIT
