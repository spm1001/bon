---
name: arc
description: Activate BEFORE running any arc CLI command. Enforces draw-down workflow (arc show → arc work → arc step) that prevents drift and tracks tactical progress. NEVER run 'arc list' via Bash (output collapses); instead Read arc.txt and output hierarchy as text. Triggers on 'arc init', 'arc new', 'arc list', 'arc done', 'what can I work on', 'next action', 'desired outcome', 'file this for later', 'track this work', or when .arc/ directory exists. (user)
---

# Arc Work Tracking

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

## The Three Questions

Every arc item answers three questions. These are CLI flags when creating, and the structure you read when picking up work:

| Flag | Question |
|------|----------|
| `--why` | Why are we doing this? |
| `--what` | What will we produce? |
| `--done` | How do we know it's complete? |

```bash
arc new "Add rate limiting" \
  --why "Users hitting 429s, server under load" \
  --what "Redis limiter, 100 req/min, Retry-After header" \
  --done "Load test passes, header present"
```

These three fields are stored together as the item's "brief" — but you always interact via the flags.

## Quick Example: Draw-Down in Action

```bash
arc show arc-zokte
# --why: OAuth flow causing race conditions...
# --what: 1. Add scope 2. Create processes module 3. Add CLI command 4. Add flags 5. Test
# --done: Can see running processes, duplicates prevented

arc work arc-zokte
# → 1. Add scope [current]
#   2. Create processes module
#   3. Add CLI command
#   4. Add flags
#   5. Test

# ... do the work ...
arc step
# ✓ 1. Add scope
# → 2. Create processes module [current]
```

Read the arc item → `arc work` activates tactical steps → `arc step` advances with pauses. That's the pattern.

## Running Arc

Arc is a Python CLI. If it's installed in the project:

```bash
uv run arc list              # If arc is a project dependency
arc list                     # If arc is in PATH
```

If arc isn't in PATH, see README.md "Add to PATH" section for symlink/alias options.

## When to Use This Skill

| Track in Arc | Just do it |
|-------------|------------|
| Multi-session work | Quick single-step action |
| Work needing handoff to future Claude | Research / exploration |
| Complex outcomes with multiple actions | Trivial fix (typo, config tweak) |
| Creating work for others to pick up | Side quest that'll be done in minutes |

**The test:** If the work has steps, use `arc work` to track them. If resuming after 2 weeks would be difficult without context, it needs an arc item.

## When NOT to Use This Skill

- **No `.arc/` directory** — check with user before `arc init`
- **Quick one-off actions** — just do them, no tracking needed
- **Research/exploration** — tracking adds friction to discovery

## Core Commands

```bash
arc init --prefix myproj     # Initialize .arc/ with prefix
arc list                     # Hierarchical view of open outcomes and actions
arc list --ready             # Actions with no waiting_for (outcomes always shown)
arc show ID                  # Full details including brief
arc show --current           # Show action with active tactical steps (for hooks)
arc new "title" --why W --what X --done D       # Create outcome
arc new "title" --for PARENT --why W --what X --done D  # Create action
arc done ID                  # Complete item (also unblocks waiters)
arc wait ID REASON           # Mark as waiting (clears tactical steps)
arc unwait ID                # Clear waiting
arc work ID                  # Initialize tactical steps from --what (if numbered)
arc work ID "step1" "step2"  # Initialize with explicit steps (actions only, not outcomes)
arc work --status            # Show current tactical state
arc work --clear             # Clear tactical steps without completing
arc step                     # Complete current step, advance to next
arc edit ID --title T        # Change title
arc edit ID --why/--what/--done  # Edit brief fields
arc edit ID --parent P       # Reparent (use 'none' for standalone)
arc edit ID --order N        # Reorder within parent
arc convert ID               # Action → outcome (preserves ID/metadata)
arc convert ID --parent P    # Outcome → action under P
arc convert ID --parent P --force  # Outcome with children → action (children become standalone)
arc status                   # Overview counts
arc migrate --from-beads F --draft  # Generate migration manifest
arc migrate --from-draft F   # Import completed manifest
```

All commands support `--json` for structured output. `arc new` supports `-q` for quiet mode (just prints ID).

**JSON shape contract:**
- `arc list --json` → `{"outcomes": [...], "standalone": [...]}` (wrapper object)
- `arc show ID --json` → single object, NOT an array (use `.field` not `.[0].field`)
- `arc show OUTCOME --json` → object with nested `"actions"` array

## Migrating from Beads

Two-phase process: generate manifest, fill briefs, import. See [references/migration.md](references/migration.md) for full guide.

```bash
arc migrate --from-beads .beads/ --draft > manifest.yaml  # Phase 1: extract
# ... fill why/what/done briefs in manifest.yaml ...
arc migrate --from-draft manifest.yaml                     # Phase 2: import
```

## The Draw-Down Pattern

**When you pick up an action to work on:**

1. **Read the item:** `arc show <id>` — understand `--why`, `--what`, and `--done`
2. **Initialize tactical steps:** `arc work <id>` — parses numbered steps from `--what`
   - If `--what` has no numbers, provide explicit steps: `arc work <id> "Step 1" "Step 2"`
3. **Work through with checkpoints:** `arc step` after each — pauses for confirmation
4. **Final step auto-completes** the action

**Example:**
```bash
arc show arc-xyz
# --why: Users hitting 429s during peak load
# --what: 1. Add scope 2. Create rate limiter 3. Test
# --done: 429s after 100 requests

arc work arc-xyz
# → 1. Add scope [current]
#   2. Create rate limiter
#   3. Test

# ... do the work ...
arc step
# ✓ 1. Add scope
# → 2. Create rate limiter [current]
#   3. Test
# Next: Create rate limiter
```

**Constraints:**
- **Actions only** — `arc work` on an outcome will error (suggests children or creating one)
- Only one action may have active tactical steps at a time (serial execution)
- If you need to context-switch: `arc wait <id> "reason"` (clears tactical, re-plan on return)
- Steps persist in `items.jsonl` — survives session crashes

**The test:** If `--what` has numbered steps, `arc work` parses them automatically. If not, formulate steps and pass them explicitly: `arc work ID "step1" "step2"`.

**Why this matters:** Tactical steps are arc-native, persist across sessions, enforce serial execution, and survive session crashes. A new Claude can pick up mid-step via `arc show --current`.

### Enforcement: UserPromptSubmit Hook

Without a hook, Claude must *choose* to run `arc step` — and may forget. The hook injects the current tactical step into every prompt, making it impossible to ignore.

**Script** (`~/.claude/hooks/arc-tactical.sh`):
```bash
#!/bin/bash
# Silent when: no .arc/, no active tactical, arc not in PATH.
tactical=$(arc show --current 2>/dev/null)
[ -z "$tactical" ] && exit 0
escaped=$(echo "$tactical" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
cat <<EOF
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "🎯 Active arc tactical:\n${escaped}\n\nWork on the CURRENT step. Run 'arc step' when it's complete before moving on."}}
EOF
```

**Hook config** (in `~/.claude/settings.json`):
```json
"UserPromptSubmit": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "$HOME/.claude/hooks/arc-tactical.sh"
      }
    ]
  }
]
```

**Why this works:** The hook output appears as a `<user-prompt-submit-hook>` system reminder — Claude treats hook output as informational context it can't dismiss. Every prompt carries the current step, creating persistent tactical awareness without Claude needing to remember to check.

**When silent:** No `.arc/` directory, no active tactical steps, or `arc` not in PATH. Zero overhead outside arc projects.

## The Draw-Up Pattern

**When you're filing work for a future Claude:**

1. **All three flags required** — `--why`/`--what`/`--done` must stand alone
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Define `--done` clearly** — verifiable criteria, not vague "it works"

**The test:** Could a Claude with zero context execute this from the three flags alone?

**Good draw-up:**
```bash
arc new "Add rate limiting to API" --for arc-gabdur \
  --why "Users hitting 429s during peak, server struggling under load" \
  --what "1. Redis-based rate limiter 2. 100 req/min per user 3. Retry-After header" \
  --done "Load test shows 429s after 100 requests, header present, Redis storing counts"
```

**Bad draw-up (will fail):**
```bash
arc new "Fix the API thing" --for arc-gabdur
# Error: Brief required. Missing: --why, --what, --done
```

## Session Start Protocol (Integration with /open)

**Arc is loaded automatically by /open when `.arc/` exists.** The startup hook generates context at `~/.claude/.session-context/<encoded-cwd>/arc.txt`.

### What to Check

1. **Read the arc context file** — shows ready work and full hierarchy
2. **Check for handoff** — previous session may have left "Next" suggestions
3. **Present ready items** — outcomes and actions that can be worked on now

### Presenting Arc Items to User

> **Output as text, not Bash.** Claude Code collapses Bash tool output >10 lines behind Ctrl+O, making it invisible. Read arc.txt and output the hierarchy directly in your response.

Show hierarchy with outcomes (desired results) containing actions (concrete steps):

```
Ready work:

○ API Improvements (arc-abc123)
  1. ○ Add rate limiting (arc-def456)
  2. ○ Add request logging (arc-ghi789)

○ Documentation (arc-jkl012)
  1. ○ Write API reference (arc-mno345)

Which would you like to work on?
```

### After User Picks

**STOP. Do the draw-down before writing any code.** Follow the Draw-Down Pattern above: `arc show` → `arc work` → `arc step`. Show the user the steps before starting.

## Session Close Protocol

**At session close:**
1. Complete finished items: `arc done <id>`
2. File new actions discovered during work (with full briefs)
3. **Draw-up** — ensure briefs are complete for next Claude
4. Handoff mentions arc items worked on

## Mid-Session Transitions

**Between actions:**
1. Complete current action: `arc done <id>`
2. Check what's unblocked — run `arc list --ready > /tmp/arc-ready.txt` then Read that file, or just re-read the arc.txt context file if recently generated
3. **Output the ready items as text** in your response (don't let Bash output be the only place it appears)
4. If continuing, **draw-down the next action** before starting

**The gap this fills:** Draw-down happens at session start because /open commands it. But mid-session transitions need the same discipline.

## Quality: The Three Flags

Every item needs all three flags — no shortcuts, no `--brief` flag:

| Flag | Question | Bad | Good |
|------|----------|-----|------|
| `--why` | Why are we doing this? | "Needs fixing" | "Users hitting 429s during peak load" |
| `--what` | What will we produce? | "Fix it" | "1. Redis limiter 2. 100 req/min 3. Retry-After header" |
| `--done` | How do we know? | "It works" | "Load test: 429 after 100 requests, header present" |

**For AI-created items**, include:
- **Concrete details:** File paths, function names, API endpoints
- **Numbered steps** in `what` when multiple deliverables exist
- **Verifiable criteria** in `done` — not "it works" but "returns 200 with valid token"

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Run `arc list` via Bash to show items | Output collapsed, user can't see | Output hierarchy as text in response |
| Working without `arc work` | No checkpoints, drift accumulates | Always draw-down into tactical steps |
| Thin briefs | Next Claude can't execute | Write for zero-context reader |
| Skipping draw-down on "continue" | Scope ambiguity | Always read brief, activate tactical |
| Motor through without `arc step` | Miss direction changes | Run `arc step` after each completion |

## Reorganization with Convert

When work evolves and classifications change, use `arc convert` instead of archive+recreate:

```bash
# Action that grew into an outcome
arc convert arc-zokte    # Action → outcome (preserves ID, metadata)

# Outcome that should be part of another outcome
arc convert arc-gabdur --parent arc-tufeme   # Outcome → action

# Outcome with children being reclassified
arc convert arc-gabdur --parent arc-tufeme --force  # Children become standalone
```

**When to use convert:**
- Field reports identify misclassified items during real work
- Scope changes — an action turns into a larger piece of work (promote to outcome)
- Hierarchy changes — independent work becomes part of a bigger outcome

**Why convert > archive+recreate:**
- Preserves original ID (links in notes/handoffs stay valid)
- Preserves created_at timestamp (history intact)
- Single command vs two (no brief re-entry needed)

## Vocabulary Reference

| Say This | Not This |
|----------|----------|
| Outcome | Epic, Story |
| Action | Task, Ticket |
| Waiting | Blocked, Blocker |
| Ready | Available |
| Done | Closed, Resolved |
