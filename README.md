# Bon

Lightweight work tracker for Claude-human collaboration using GTD vocabulary.

Bon organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points — just ordering and a clear answer to "what can I work on now?"

## Install

```bash
git clone https://github.com/spm1001/bon.git
cd bon
uv tool install .
```

This installs `bon` globally — available from any directory. To develop bon itself, also run `uv sync` for the dev dependencies (pytest, ruff).

### Updating

`uv tool install` copies the package — edits to source aren't reflected until you re-install:

```bash
bon update          # re-installs from source
```

Or manually: `uv tool install ~/Repos/bon`.

> **Note:** `uv tool install` doesn't support editable mode (`-e`) yet. When uv adds this, the update step goes away.

## Quick Start

```bash
# Initialize in your project
bon init

# Create an outcome (desired result)
bon new "Users can export data" \
  --why "Users requesting CSV exports" \
  --what "Export button, CSV generation, download" \
  --done "Can export any table to CSV"

# Add actions to that outcome
bon new "Add export button to toolbar" \
  --outcome bon-abcdef \
  --why "Entry point for export flow" \
  --what "Button in toolbar, opens format picker" \
  --done "Button visible, click opens modal"

# See what's ready
bon list --ready

# Mark done when complete
bon done bon-ghijkl
```

## Commands

| Command | Description |
|---------|-------------|
| `init [--prefix P]` | Initialize `.bon/` directory |
| `new TITLE [--outcome PARENT] --why W --what X --done D` | Create outcome or action |
| `list [--ready\|--waiting\|--all]` | Show items hierarchically |
| `show ID [--current]` | View item details and brief |
| `done ID` | Mark item complete |
| `wait ID REASON` | Mark as waiting for something |
| `unwait ID` | Clear waiting status |
| `edit ID --flag VALUE` | Edit item fields (title, brief, parent, order) |
| `work ID [STEPS...] [--status\|--clear\|--force]` | Manage tactical steps for an action |
| `step` | Complete current step, advance to next |
| `convert ID [--outcome P] [--force]` | Convert outcome↔action |
| `archive [IDs...] [--all]` | Move done items to archive.jsonl |
| `log [-n N]` | Show recent activity (creations, completions, archives) |
| `reopen ID` | Reopen a completed or archived item |
| `migrate-repo [--dry-run]` | Migrate `.arc/` → `.bon/` in current repo |
| `update` | Re-install bon from source |
| `status` | Show counts overview |
| `help [CMD]` | Show help |

### Output Flags

- `--json` — Structured JSON (for `list`, `show`)
- `--jsonl` — Flat JSONL, one item per line (for `list`)
- `--quiet` / `-q` — Minimal output, just the ID (for `new`)

**JSON shapes differ by command:**

| Command | Shape | Example `jq` |
|---------|-------|--------------|
| `bon list --json` | `{"outcomes": [...], "standalone": [...]}` | `.outcomes[0].title` |
| `bon show ID --json` | Single object (action or outcome) | `.title`, `.brief.why` |
| `bon show OUTCOME --json` | Object with nested `"actions"` array | `.actions[0].title` |

`bon show` returns an **object**, not an array. Use `.field` not `.[0].field`.

### List Filters

```bash
bon list              # Open outcomes + their actions (default)
bon list --ready      # Only items ready to work on
bon list --waiting    # Only items that are waiting
bon list --all        # Include done items
```

**What `--ready` shows:**
- All open outcomes (always visible for context)
- Actions where `status=open` AND `waiting_for` is empty
- If some actions are hidden, shows "+N waiting" count

**Example:**
```
○ API Improvements (bon-abc)
  1. ○ Add rate limiting (bon-def)      # ready - shown
  2. ○ Add logging (bon-ghi)            # ready - shown
  (+1 waiting)                          # bon-jkl waiting for review - hidden
```

Use `--ready` to answer "what can I work on right now?" without clutter from blocked items.

### Tactical Steps

Track progress through an action's steps:

```bash
# Initialize steps (parses from --what if numbered)
bon work bon-def

# Or provide explicit steps
bon work bon-def "Add scope" "Create module" "Test"

# Advance to next step (auto-completes on final)
bon step

# Check current status
bon work --status

# Clear steps (e.g., to restructure)
bon work --clear
```

**Output:**
```
✓ 1. Add scope
→ 2. Create module [current]
  3. Test
```

**Constraints:**
- Only one action may have active steps at a time (serial execution)
- `bon wait` clears tactical steps (long blocks warrant re-planning)
- Final `bon step` auto-completes the action

## Data Model

Bon stores work in `.bon/items.jsonl` as two item types:

**Outcomes** — Desired results that matter. Have child actions.
```json
{
  "id": "bon-abcdef",
  "type": "outcome",
  "title": "Users can export data",
  "brief": { "why": "...", "what": "...", "done": "..." },
  "status": "open"
}
```

**Actions** — Concrete next steps. Belong to outcomes.
```json
{
  "id": "bon-ghijkl",
  "type": "action",
  "title": "Add export button",
  "parent": "bon-abcdef",
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

Bon includes a skill for Claude Code at `bon/SKILL.md`. After installing bon, symlink the skill directory:

```bash
ln -s ~/Repos/bon/bon ~/.claude/skills/bon
```

This gives Claude access to the draw-down workflow (read item → activate tactical steps → work with pauses) and draw-up patterns (file work with complete briefs for future sessions).

## Why Bon?

Bon was built after discovering that Claude working without checkpoints leads to drift. Complex work needs:

1. **Clear scope** — Brief fields force "why/what/done" clarity
2. **Checkpoints** — Draw-down to TodoWrite creates pause points
3. **Handoff** — Briefs written for zero-context readers survive session boundaries

See `ORCHESTRATION.md` for patterns used to build bon with Claude.

## Development

```bash
# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_done.py -k "test_done"
```

## License

MIT
