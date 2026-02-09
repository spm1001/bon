# Arc

Lightweight work tracker for Claude-human collaboration using GTD vocabulary.

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points — just ordering and a clear answer to "what can I work on now?"

## Install

```bash
# Clone and install with uv
git clone https://github.com/spm1001/arc.git
cd arc
uv sync

# Run from project
uv run arc --help
```

### Add to PATH (optional)

To use `arc` from anywhere:

```bash
# Option 1: Symlink to ~/.local/bin (recommended)
mkdir -p ~/.local/bin
ln -s /path/to/arc/.venv/bin/arc ~/.local/bin/arc

# Option 2: Shell alias
echo 'alias arc="/path/to/arc/.venv/bin/arc"' >> ~/.zshrc
```

Then just `arc list` from any project with `.arc/`.

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
| `show ID [--current]` | View item details and brief |
| `done ID` | Mark item complete |
| `wait ID REASON` | Mark as waiting for something |
| `unwait ID` | Clear waiting status |
| `edit ID --flag VALUE` | Edit item fields (title, brief, parent, order) |
| `work ID [STEPS...] [--status\|--clear\|--force]` | Manage tactical steps for an action |
| `step` | Complete current step, advance to next |
| `convert ID [--parent P] [--force]` | Convert outcome↔action |
| `status` | Show counts overview |
| `help [CMD]` | Show help |

### Output Flags

- `--json` — Structured JSON (for `list`, `show`)
- `--jsonl` — Flat JSONL, one item per line (for `list`)
- `--quiet` / `-q` — Minimal output, just the ID (for `new`)

**JSON shapes differ by command:**

| Command | Shape | Example `jq` |
|---------|-------|--------------|
| `arc list --json` | `{"outcomes": [...], "standalone": [...]}` | `.outcomes[0].title` |
| `arc show ID --json` | Single object (action or outcome) | `.title`, `.brief.why` |
| `arc show OUTCOME --json` | Object with nested `"actions"` array | `.actions[0].title` |

`arc show` returns an **object**, not an array. Use `.field` not `.[0].field`.

### List Filters

```bash
arc list              # Open outcomes + their actions (default)
arc list --ready      # Only items ready to work on
arc list --waiting    # Only items that are waiting
arc list --all        # Include done items
```

**What `--ready` shows:**
- All open outcomes (always visible for context)
- Actions where `status=open` AND `waiting_for` is empty
- If some actions are hidden, shows "+N waiting" count

**Example:**
```
○ API Improvements (arc-abc)
  1. ○ Add rate limiting (arc-def)      # ready - shown
  2. ○ Add logging (arc-ghi)            # ready - shown
  (+1 waiting)                          # arc-jkl waiting for review - hidden
```

Use `--ready` to answer "what can I work on right now?" without clutter from blocked items.

### Tactical Steps

Track progress through an action's steps:

```bash
# Initialize steps (parses from --what if numbered)
arc work arc-def

# Or provide explicit steps
arc work arc-def "Add scope" "Create module" "Test"

# Advance to next step (auto-completes on final)
arc step

# Check current status
arc work --status

# Clear steps (e.g., to restructure)
arc work --clear
```

**Output:**
```
✓ 1. Add scope
→ 2. Create module [current]
  3. Test
```

**Constraints:**
- Only one action may have active steps at a time (serial execution)
- `arc wait` clears tactical steps (long blocks warrant re-planning)
- Final `arc step` auto-completes the action

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

Arc includes a skill for Claude Code at `arc/SKILL.md`. Symlink to use:

```bash
ln -s /path/to/arc/arc ~/.claude/skills/arc
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
