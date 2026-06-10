# Bon

Lightweight work tracker for Claude-human collaboration using GTD vocabulary.

Bon organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points — just ordering and a clear answer to "what can I work on now?"

## Status

**Robustness:** Stable — used daily
**Works with:** Any agent, standalone CLI
**Install:** `uv tool install .`
**Requires:** Python 3.11+

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

# Create an outcome (desired result) — pipe JSON to stdin
cat <<'EOF' | bon new -q
{
  "title": "Users can export data",
  "brief": {
    "why": "Users requesting CSV exports",
    "what": "1. Export button in toolbar 2. CSV generation 3. Download endpoint",
    "done": "Can export any table to CSV"
  }
}
EOF

# Add an action under that outcome
cat <<'EOF' | bon new -q
{
  "title": "Add export button to toolbar",
  "parent": "bon-abcdef",
  "brief": {
    "why": "Entry point for export flow",
    "what": "Button in toolbar, opens format picker",
    "done": "Button visible, click opens modal"
  }
}
EOF

# File a standalone action (field report, one-off fix)
cat <<'EOF' | bon new -q
{
  "type": "action",
  "title": "Field Report: CSV encoding broken on non-ASCII",
  "brief": {
    "why": "Japanese characters produce mojibake in exports",
    "what": "Diagnose encoding, fix or file under outcome",
    "done": "Non-ASCII exports render correctly"
  }
}
EOF

# See what's ready
bon list --ready

# Mark done when complete
bon done bon-ghijkl
```

Flags work too for quick stubs: `bon new "Fix typo" --why w --what x --done d -q`

## Commands

| Command | Description |
|---------|-------------|
| `init [--prefix P] [--backend {jsonl\|dolt}]` | Initialize `.bon/` directory |
| `new [TITLE] [--outcome PARENT] --why W --what X --done D` | Create outcome or action (JSON stdin or flags) |
| `list [--ready\|--waiting\|--all] [--limit N]` | Show items hierarchically |
| `show ID [--current]` | View item details and brief |
| `done ID` | Mark item complete |
| `doctor` | Check items.jsonl for health issues |
| `wait ID REASON` | Mark as waiting for something |
| `unwait ID` | Clear waiting status |
| `edit ID --flag VALUE` | Edit item fields (title, brief, parent, order) |
| `work ID [STEPS...] [--status\|--clear\|--force]` | Manage tactical steps for an action |
| `step` | Complete current step, advance to next |
| `convert ID [--outcome P] [--force]` | Convert outcome↔action |
| `archive [IDs...] [--all]` | Move done items to archive.jsonl |
| `log [-n N]` | Show recent activity (creations, completions, archives) |
| `reopen ID` | Reopen a completed or archived item |
| `migrate --to {jsonl\|dolt}` | Switch storage backend |
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
bon list --limit 5    # First 5 top-level items (children come along)
```

**`--limit N`** truncates to the first N top-level items — outcomes first, then standalones. Children of kept outcomes always come along, so output never cuts mid-item. Combine with any filter (e.g. `--ready --limit 3`).

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

## Storage Backends

By default, bon stores work in `.bon/items.jsonl` — local, git-tracked, zero dependencies. An optional **Dolt** backend stores items in a MySQL-compatible database with git semantics (branch, merge, diff at the cell level). Useful for multi-machine workflows where you want live state without git sync.

```bash
# Default (JSONL)
bon init --prefix myproj

# With Dolt backend
pip install bon[dolt]                          # adds pymysql
bon init --prefix myproj --backend dolt

# Switch an existing project
bon migrate --to dolt
bon migrate --to jsonl                         # and back
```

Dolt connection is configured via env vars (`BON_DOLT_HOST`, `BON_DOLT_PORT`, `BON_DOLT_DATABASE`, `BON_DOLT_USER`, `BON_DOLT_PASSWORD`) or `~/.config/bon/dolt.toml`. All Dolt code is lazily imported — JSONL users never load pymysql.

### Git-track all of `.bon/`

Commit the whole `.bon/` directory — including `prefix` and `backend`. They are
project identity, not machine state: the only machine-local piece of Dolt config
is `~/.config/bon/dolt.toml`, which already lives outside the repo. Repos that
gitignore `.bon/` (wholesale or just the markers) produce a nasty trap: a fresh
clone silently presents an empty default board instead of the real backlog.
Bon detects that shape and refuses with a reconnect recipe — `bon init
--prefix <prefix> --backend dolt` completes the missing markers without
touching anything else — but tracked markers mean clones just work.

### Running the Dolt Server

Bon expects a running Dolt SQL server. The quickest way is a systemd user service:

```bash
# 1. Create and initialize the database directory
mkdir -p ~/dolt-data/bon && cd ~/dolt-data/bon && dolt init

# 2. Set Dolt identity (required once)
dolt config --global --add user.email "you@example.com"
dolt config --global --add user.name "Your Name"

# 3. Install the systemd service
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/dolt-bon.service << 'EOF'
[Unit]
Description=Dolt SQL server for bon work tracker
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/dolt-data
ExecStart=/usr/local/bin/dolt sql-server --host 127.0.0.1 --port 3306 --data-dir %h/dolt-data
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# 4. Enable and start
systemctl --user daemon-reload
systemctl --user enable --now dolt-bon.service

# 5. Verify
systemctl --user status dolt-bon.service
```

Dolt auto-creates a `root@localhost` superuser on first start. Create a scoped user and drop root:

```bash
cd ~/dolt-data/bon
dolt sql -q "CREATE USER 'bon'@'127.0.0.1' IDENTIFIED BY '';"
dolt sql -q "GRANT ALL ON bon.* TO 'bon'@'127.0.0.1';"
dolt sql -q "DROP USER 'root'@'localhost';"
dolt add -A && dolt commit -m "security: scoped bon user, drop root"
```

Tables (`items`, `archive`, `config`) are auto-created by bon on first connection.

**Config file** (`~/.config/bon/dolt.toml`):
```toml
host     = "127.0.0.1"
port     = 3306
database = "bon"
user     = "bon"
```

## Data Model

Bon stores work in `.bon/items.jsonl` (or a Dolt database) as two item types:

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

**Actions** — Concrete next steps. Belong to outcomes, or standalone (field reports, one-off fixes).
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

Bon includes a skill for Claude Code at `skills/tracker/SKILL.md`. The plugin system auto-discovers skills from the `skills/` directory.

This gives Claude access to the draw-down workflow (read item → activate tactical steps → work with pauses) and draw-up patterns (file work with complete briefs for future sessions).

## Why Bon?

Bon was built after discovering that Claude working without checkpoints leads to drift. Complex work needs:

1. **Clear scope** — Brief fields force "why/what/done" clarity
2. **Checkpoints** — Draw-down to TodoWrite creates pause points
3. **Handoff** — Briefs written for zero-context readers survive session boundaries

See `docs/HOW_WE_BUILT_BON.md` (in aboyeur) for patterns used to build bon with Claude.

## Acknowledgements

Bon owes a huge debt to Steve Yegge's [Beads](https://github.com/steveyegge/beads). Bon is a simpler, more opinionated tool, but it borrows heavily from Beads — especially the idea of **agent-first ergonomics**. Beads demonstrated that work-tracking tools should be designed *for agents*, not just *used by* agents. If an agent felt a flag or switch would help, it got added. Bon follows that principle: every command, every output format, every flag was shaped by what makes an AI agent effective at managing work.

## Development

```bash
# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_done.py -k "test_done"
```

## The Kitchen

Bon is part of [Batterie de Savoir](https://spm1001.github.io/batterie-de-savoir/) — a suite of tools for AI-assisted knowledge work. See the [full brigade and design principles](https://spm1001.github.io/batterie-de-savoir/) for how the tools fit together.

## License

MIT
