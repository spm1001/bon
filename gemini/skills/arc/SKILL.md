---
name: arc
description: GTD-flavoured work tracker. Activate before running any arc CLI command. Enforces draw-down workflow (arc show, arc work, arc step) that prevents drift and tracks tactical progress.
---

# Arc Work Tracking

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels -- just ordering and a clear answer to "what can I work on now?"

## Vocabulary

| Say This | Not This |
|----------|----------|
| Outcome | Epic, Story |
| Action | Task, Ticket |
| Waiting | Blocked, Blocker |
| Ready | Available |
| Done | Closed, Resolved |

## The Three Questions

Every arc item answers three questions. These are CLI flags when creating, and the structure you read when picking up work:

| Flag | Question |
|------|----------|
| `--why` | Why are we doing this? |
| `--what` | What will we produce? |
| `--done` | How do we know it's complete? |

```bash
arc new "API stays responsive under peak load" \
  --why "Users hitting 429s, server under load" \
  --what "Redis limiter, 100 req/min, Retry-After header" \
  --done "Load test passes, header present"
```

These three fields are stored together as the item's "brief" -- all three are mandatory.

## The Draw-Down Pattern

**When picking up an action to work on:**

1. **Read the item:** `arc show <id>` -- understand `--why`, `--what`, and `--done`
2. **Initialize tactical steps:** `arc work <id>` -- parses numbered steps from `--what`
   - If `--what` has no numbers, provide explicit steps: `arc work <id> "Step 1" "Step 2"`
3. **Work through with checkpoints:** `arc step` after each -- pauses for confirmation
4. **Final step auto-completes** the action

**Example:**
```bash
arc show arc-xyz
# --why: Users hitting 429s during peak load
# --what: 1. Add scope 2. Create rate limiter 3. Test
# --done: 429s after 100 requests

arc work arc-xyz
# -> 1. Add scope [current]
#    2. Create rate limiter
#    3. Test

# ... do the work ...
arc step
# Done: 1. Add scope
# -> 2. Create rate limiter [current]
#    3. Test
# Next: Create rate limiter
```

**Constraints:**
- **Actions only** -- `arc work` on an outcome will error (suggests children or creating one)
- Only one action may have active tactical steps at a time (serial execution)
- If you need to context-switch: `arc wait <id> "reason"` (clears tactical, re-plan on return)
- Steps persist in `items.jsonl` -- survives session crashes

**Why this matters:** Tactical steps are arc-native, persist across sessions, enforce serial execution, and survive session crashes. A new session can pick up mid-step via `arc show --current`.

## The Draw-Up Pattern

**When filing work for later:**

1. **All three flags required** -- `--why`/`--what`/`--done` must stand alone
2. **Include concrete details** -- file paths, API endpoints, error messages
3. **Define `--done` clearly** -- verifiable criteria, not vague "it works"

**The test:** Could someone with zero context execute this from the three flags alone?

**Good draw-up:**
```bash
arc new "Add rate limiting to API" --outcome arc-gabdur \
  --why "Users hitting 429s during peak, server struggling under load" \
  --what "1. Redis-based rate limiter 2. 100 req/min per user 3. Retry-After header" \
  --done "Load test shows 429s after 100 requests, header present, Redis storing counts"
```

## When to Use Arc

| Track in Arc | Just do it |
|-------------|------------|
| Multi-session work | Quick single-step action |
| Work needing handoff context | Research / exploration |
| Complex outcomes with multiple actions | Trivial fix (typo, config tweak) |
| Creating work for others to pick up | Side quest done in minutes |

**The test:** If the work has steps, use `arc work` to track them. If resuming after 2 weeks would be difficult without context, it needs an arc item.

## Core Commands

```bash
arc init --prefix myproj     # Initialize .arc/ with prefix
arc list                     # Hierarchical view of open outcomes and actions
arc list --ready             # Actions with no waiting_for (outcomes always shown)
arc show ID                  # Full details including brief
arc show --current           # Show action with active tactical steps
arc new "title" --why W --what X --done D       # Create outcome
arc new "title" --outcome PARENT --why W --what X --done D  # Create action
arc done ID                  # Complete item (also unblocks waiters)
arc wait ID REASON           # Mark as waiting (clears tactical steps)
arc unwait ID                # Clear waiting
arc work ID                  # Initialize tactical steps from --what (if numbered)
arc work ID "step1" "step2"  # Initialize with explicit steps (actions only)
arc work --status            # Show current tactical state
arc work --clear             # Clear tactical steps without completing
arc step                     # Complete current step, advance to next
arc edit ID --title T        # Change title
arc edit ID --why/--what/--done  # Edit brief fields
arc edit ID --parent P       # Reparent (use 'none' for standalone)
arc edit ID --order N        # Reorder within parent
arc convert ID               # Action -> outcome (preserves ID/metadata)
arc convert ID --outcome P   # Outcome -> action under P
arc status                   # Overview counts
arc log                      # Show recent activity
arc archive                  # Archive done items
arc reopen ID                # Reopen a completed item
```

All commands support `--json` for structured output. `arc new` supports `-q` for quiet mode (just prints ID).

## Quality: The Three Flags

Every item needs all three flags -- no shortcuts:

| Flag | Question | Bad | Good |
|------|----------|-----|------|
| `--why` | Why are we doing this? | "Needs fixing" | "Users hitting 429s during peak load" |
| `--what` | What will we produce? | "Fix it" | "1. Redis limiter 2. 100 req/min 3. Retry-After header" |
| `--done` | How do we know? | "It works" | "Load test: 429 after 100 requests, header present" |

**For AI-created items**, include:
- **Concrete details:** File paths, function names, API endpoints
- **Numbered steps** in `--what` when multiple deliverables exist
- **Verifiable criteria** in `--done` -- not "it works" but "returns 200 with valid token"

## Outcome Language Coaching

Outcomes describe what will be true, not work to be done.

| Activity (bad for outcomes) | Achievement (good for outcomes) |
|-----------------------------|--------------------------------|
| Implement OAuth | Users can authenticate with GitHub |
| Build rate limiter | API stays responsive under peak load |
| Add test coverage | Edge cases don't cause surprising failures |
| Document the architecture | Any team member can onboard without guidance |

**The pattern:** Past-tense or present-state verb, describes what's *different* when done, includes the "so what".

Actions *should* use activity language -- they're concrete steps. "Add OAuth callback endpoint" is a perfectly good action title.

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Working without `arc work` | No checkpoints, drift accumulates | Always draw-down into tactical steps |
| Thin briefs | Next session can't execute | Write for zero-context reader |
| Skipping draw-down on "continue" | Scope ambiguity | Always read brief, activate tactical |
| Motor through without `arc step` | Miss direction changes | Run `arc step` after each completion |

## Session Workflow

**Starting work:**
1. Run `arc list` or `arc list --ready` to see available work
2. Present items as a readable hierarchy
3. After picking an item, **draw-down before writing any code**: `arc show` -> `arc work` -> `arc step`

**Mid-session transitions:**
1. Complete current action: `arc done <id>`
2. Check what's unblocked: `arc list --ready`
3. Draw-down the next action before starting

**Ending a session:**
1. Complete finished items: `arc done <id>`
2. File new actions discovered during work (with full briefs)
3. Ensure briefs are complete for next session
