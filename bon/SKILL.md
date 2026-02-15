---
name: bon
description: Activate BEFORE running any bon CLI command. Enforces draw-down workflow (bon show → bon work → bon step) that prevents drift and tracks tactical progress. NEVER run 'bon list' via Bash (output collapses); instead Read bon.txt and output hierarchy as text. Triggers on 'bon init', 'bon new', 'bon list', 'bon done', 'what can I work on', 'next action', 'desired outcome', 'file this for later', 'track this work', or when .bon/ directory exists. (user)
requires:
  - cli: bon
    check: "bon --version"
---

# Bon Work Tracking

Bon organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

## The Three Questions

Every bon item answers three questions. These are CLI flags when creating, and the structure you read when picking up work:

| Flag | Question |
|------|----------|
| `--why` | Why are we doing this? |
| `--what` | What will we produce? |
| `--done` | How do we know it's complete? |

```bash
bon new "API stays responsive under peak load" \
  --why "Users hitting 429s, server under load" \
  --what "Redis limiter, 100 req/min, Retry-After header" \
  --done "Load test passes, header present"
```

These three fields are stored together as the item's "brief" — but you always interact via the flags.

## Quick Example: Draw-Down in Action

```bash
bon show bon-zokte
# --why: OAuth flow causing race conditions...
# --what: 1. Add scope 2. Create processes module 3. Add CLI command 4. Add flags 5. Test
# --done: Can see running processes, duplicates prevented

bon work bon-zokte
# → 1. Add scope [current]
#   2. Create processes module
#   3. Add CLI command
#   4. Add flags
#   5. Test

# ... do the work ...
bon step
# ✓ 1. Add scope
# → 2. Create processes module [current]
```

Read the bon item → `bon work` activates tactical steps → `bon step` advances with pauses. That's the pattern.

## Running Bon

Bon is a Python CLI. If it's installed in the project:

```bash
uv run bon list              # If bon is a project dependency
bon list                     # If bon is in PATH
```

If bon isn't in PATH, see README.md "Add to PATH" section for symlink/alias options.

## When to Use This Skill

| Track in Bon | Just do it |
|-------------|------------|
| Multi-session work | Quick single-step action |
| Work needing handoff to future Claude | Research / exploration |
| Complex outcomes with multiple actions | Trivial fix (typo, config tweak) |
| Creating work for others to pick up | Side quest that'll be done in minutes |

**The test:** If the work has steps, use `bon work` to track them. If resuming after 2 weeks would be difficult without context, it needs a bon item.

## When NOT to Use This Skill

- **No `.bon/` directory** — check with user before `bon init`
- **Quick one-off actions** — just do them, no tracking needed
- **Research/exploration** — tracking adds friction to discovery

## Core Commands

```bash
bon init --prefix myproj     # Initialize .bon/ with prefix
bon list                     # Hierarchical view of open outcomes and actions
bon list --ready             # Actions with no waiting_for (outcomes always shown)
bon show ID                  # Full details including brief
bon show --current           # Show action with active tactical steps (for hooks)
bon new "title" --why W --what X --done D       # Create outcome
bon new "title" --outcome PARENT --why W --what X --done D  # Create action
bon done ID                  # Complete item (also unblocks waiters)
bon wait ID REASON           # Mark as waiting (clears tactical steps)
bon unwait ID                # Clear waiting
bon work ID                  # Initialize tactical steps from --what (if numbered)
bon work ID "step1" "step2"  # Initialize with explicit steps (actions only, not outcomes)
bon work --status            # Show current tactical state
bon work --clear             # Clear tactical steps without completing
bon step                     # Complete current step, advance to next
bon edit ID --title T        # Change title
bon edit ID --why/--what/--done  # Edit brief fields
bon edit ID --parent P       # Reparent (use 'none' for standalone)
bon edit ID --order N        # Reorder within parent
bon convert ID               # Action → outcome (preserves ID/metadata)
bon convert ID --outcome P    # Outcome → action under P
bon convert ID --outcome P --force  # Outcome with children → action (children become standalone)
bon status                   # Overview counts
bon migrate --from-beads F --draft  # Generate migration manifest
bon migrate --from-draft F   # Import completed manifest
```

All commands support `--json` for structured output. `bon new` supports `-q` for quiet mode (just prints ID).

**JSON shape contract:**
- `bon list --json` → `{"outcomes": [...], "standalone": [...]}` (wrapper object)
- `bon show ID --json` → single object, NOT an array (use `.field` not `.[0].field`)
- `bon show OUTCOME --json` → object with nested `"actions"` array

## Migrating from Beads

Two-phase process: generate manifest, fill briefs, import. See [references/migration.md](references/migration.md) for full guide.

```bash
bon migrate --from-beads .beads/ --draft > manifest.yaml  # Phase 1: extract
# ... fill why/what/done briefs in manifest.yaml ...
bon migrate --from-draft manifest.yaml                     # Phase 2: import
```

## The Draw-Down Pattern

**When you pick up an action to work on:**

1. **Read the item:** `bon show <id>` — understand `--why`, `--what`, and `--done`
2. **Initialize tactical steps:** `bon work <id>` — parses numbered steps from `--what`
   - If `--what` has no numbers, provide explicit steps: `bon work <id> "Step 1" "Step 2"`
3. **Work through with checkpoints:** `bon step` after each — pauses for confirmation
4. **Final step auto-completes** the action

**Example:**
```bash
bon show bon-xyz
# --why: Users hitting 429s during peak load
# --what: 1. Add scope 2. Create rate limiter 3. Test
# --done: 429s after 100 requests

bon work bon-xyz
# → 1. Add scope [current]
#   2. Create rate limiter
#   3. Test

# ... do the work ...
bon step
# ✓ 1. Add scope
# → 2. Create rate limiter [current]
#   3. Test
# Next: Create rate limiter
```

**Constraints:**
- **Actions only** — `bon work` on an outcome will error (suggests children or creating one)
- Only one action may have active tactical steps *per session (CWD)* — different worktrees can each have active tactical simultaneously
- Two CWDs cannot claim the same action — the second gets an error
- If you need to context-switch: `bon wait <id> "reason"` (clears tactical, re-plan on return)
- Steps persist in `items.jsonl` — survives session crashes

**Session scoping is automatic:** `bon work` stamps `tactical.session` with `os.getcwd()`. All tactical lookups (`bon step`, `bon show --current`, `bon work --status/--clear`) filter by the current CWD. Legacy tacticals (no `session` field) are claimable by any CWD.

**The test:** If `--what` has numbered steps, `bon work` parses them automatically. If not, formulate steps and pass them explicitly: `bon work ID "step1" "step2"`.

**Why this matters:** Tactical steps are bon-native, persist across sessions, enforce per-worktree serial execution, and survive session crashes. A new Claude can pick up mid-step via `bon show --current`.

### Enforcement: UserPromptSubmit Hook

Without a hook, Claude must *choose* to run `bon step` — and may forget. The hook injects the current tactical step into every prompt, making it impossible to ignore.

**Script** (`~/.claude/hooks/bon-tactical.sh`):
```bash
#!/bin/bash
# Silent when: no .bon/, no active tactical, bon not in PATH.
tactical=$(bon show --current 2>/dev/null)
[ -z "$tactical" ] && exit 0
escaped=$(echo "$tactical" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
cat <<EOF
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "🎯 Active bon tactical:\n${escaped}\n\nWork on the CURRENT step. Run 'bon step' when it's complete before moving on."}}
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
        "command": "$HOME/.claude/hooks/bon-tactical.sh"
      }
    ]
  }
]
```

**Why this works:** The hook output appears as a `<user-prompt-submit-hook>` system reminder — Claude treats hook output as informational context it can't dismiss. Every prompt carries the current step, creating persistent tactical awareness without Claude needing to remember to check.

**When silent:** No `.bon/` directory, no active tactical steps, or `bon` not in PATH. Zero overhead outside bon projects.

## The Draw-Up Pattern

**When you're filing work for a future Claude:**

1. **All three flags required** — `--why`/`--what`/`--done` must stand alone
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Define `--done` clearly** — verifiable criteria, not vague "it works"

**The test:** Could a Claude with zero context execute this from the three flags alone?

**Good draw-up:**
```bash
bon new "Add rate limiting to API" --outcome bon-gabdur \
  --why "Users hitting 429s during peak, server struggling under load" \
  --what "1. Redis-based rate limiter 2. 100 req/min per user 3. Retry-After header" \
  --done "Load test shows 429s after 100 requests, header present, Redis storing counts"
```

**Bad draw-up (will fail):**
```bash
bon new "Fix the API thing" --outcome bon-gabdur
# Error: Brief required. Missing: --why, --what, --done
```

## Session Start Protocol (Integration with /open)

**Bon is loaded automatically by /open when `.bon/` exists.** The startup hook generates context at `~/.claude/.session-context/<encoded-cwd>/bon.txt`.

### What to Check

1. **Read the bon context file** — shows ready work and full hierarchy
2. **Check for handoff** — previous session may have left "Next" suggestions
3. **Present ready items** — outcomes and actions that can be worked on now

### Presenting Bon Items to User

> **Output as text, not Bash.** Claude Code collapses Bash tool output >10 lines behind Ctrl+O, making it invisible. Read bon.txt and output the hierarchy directly in your response.

Show hierarchy with outcomes (desired results) containing actions (concrete steps):

```
Ready work:

○ API Improvements (bon-abc123)
  1. ○ Add rate limiting (bon-def456)
  2. ○ Add request logging (bon-ghi789)

○ Documentation (bon-jkl012)
  1. ○ Write API reference (bon-mno345)

Which would you like to work on?
```

### After User Picks

**STOP. Do the draw-down before writing any code.** Follow the Draw-Down Pattern above: `bon show` → `bon work` → `bon step`. Show the user the steps before starting.

## Session Close Protocol

**At session close:**
1. Complete finished items: `bon done <id>`
2. File new actions discovered during work (with full briefs)
3. **Draw-up** — ensure briefs are complete for next Claude
4. Handoff mentions bon items worked on

## Mid-Session Transitions

**Between actions:**
1. Complete current action: `bon done <id>`
2. Check what's unblocked — run `bon list --ready > /tmp/bon-ready.txt` then Read that file, or just re-read the bon.txt context file if recently generated
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

## Outcome Language Coaching

The CLI warns when outcome titles start with activity verbs ("Implement", "Build", "Add"). That's a lightweight lint. Your job as Claude is the richer coaching layer — helping reframe before `bon new` runs.

### The Test

**Outcomes describe what will be true, not work to be done.**

- "Would anyone dispute this is worth achieving?" → If yes, it has substance.
- "If I completed this, what would be different?" → That difference is the outcome.

### Activity → Achievement Reframes

| Activity (bad for outcomes) | Achievement (good for outcomes) |
|-----------------------------|--------------------------------|
| Implement OAuth | Users can authenticate with GitHub |
| Build rate limiter | API stays responsive under peak load |
| Add test coverage | Claudes don't hit surprising edges |
| Document the architecture | Any team member can onboard without guidance |
| Migrate to new format | Data flows cleanly through the new pipeline |
| Review and audit logs | Audit trail catches anomalies before users notice |

**The pattern:** Past-tense or present-state verb, describes what's *different* when done, includes the "so what".

### When to Coach

Coach **before** running `bon new` for outcomes. When the user or you propose an outcome title:

1. Check: does it start with an activity verb?
2. If yes, suggest a reframe: "That describes work. What will be true when it's done?"
3. Proceed with the reframed title

**Don't coach on actions.** Actions *should* be activity language — they're concrete steps. "Add OAuth callback endpoint" is a perfectly good action title.

### The CLI Helps

`bon new` warns on activity-verb outcome titles automatically. The item still gets created, but the warning is visible. If you see the warning, acknowledge it — don't ignore it.

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Run `bon list` via Bash to show items | Output collapsed, user can't see | Output hierarchy as text in response |
| Working without `bon work` | No checkpoints, drift accumulates | Always draw-down into tactical steps |
| Thin briefs | Next Claude can't execute | Write for zero-context reader |
| Skipping draw-down on "continue" | Scope ambiguity | Always read brief, activate tactical |
| Motor through without `bon step` | Miss direction changes | Run `bon step` after each completion |

## Reorganization with Convert

When work evolves and classifications change, use `bon convert` instead of archive+recreate:

```bash
# Action that grew into an outcome
bon convert bon-zokte    # Action → outcome (preserves ID, metadata)

# Outcome that should be part of another outcome
bon convert bon-gabdur --outcome bon-tufeme   # Outcome → action

# Outcome with children being reclassified
bon convert bon-gabdur --outcome bon-tufeme --force  # Children become standalone
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
