---
name: arc
description: Lightweight work tracker for Claude-human collaboration using GTD vocabulary. Triggers on 'arc command', 'arc list', 'arc new', 'what can I work on', 'next action', 'desired outcome', 'file this for later', 'waiting for', or when starting/finishing arc items. Use when tracking outcomes and actions across sessions. For single-session linear tasks, use TodoWrite directly.
---

# Arc Work Tracking

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

## When to Use Arc vs TodoWrite

| Use Arc | Use TodoWrite |
|---------|---------------|
| Multi-session work | Single-session tasks |
| Work needing handoff to future Claude | Immediate execution |
| Complex outcomes with multiple actions | Linear step-by-step |
| Creating work for others to pick up | Just need a checklist |

**The test:** If work will take >10 minutes, create arc items. If resuming after 2 weeks would be difficult without arc, use arc.

## Core Commands

```bash
arc list              # Hierarchical view of open outcomes and actions
arc list --ready      # Only items that can be worked on now
arc show ID           # Full details including brief
arc new "title" --why W --what X --done D       # Create outcome
arc new "title" --for PARENT --why W --what X --done D  # Create action
arc done ID           # Complete item
arc wait ID REASON    # Mark as waiting
arc unwait ID         # Clear waiting
arc status            # Overview counts
```

All commands support `--json` for structured output.

## The Draw-Down Pattern

**When you pick up an action to work on:**

1. **Read the brief:** `arc show <id>` — understand `why`, `what`, and `done`
2. **Create TodoWrite items** from `brief.what` and `brief.done`
3. **Show user the breakdown:** "I'm reading this as: [list]. Sound right?"
4. **VERIFY:** TodoWrite is not empty before proceeding
5. **Work through items with checkpoints** — pause at each completion to confirm direction

**The test:** If work will take >10 minutes, it needs TodoWrite items.

**Why this matters:** Without draw-down, you work from the arc item directly, context accumulates, and by close you've drifted. TodoWrite creates checkpoints where course-correction happens.

**Example:**
```
arc show arc-zoKte
# Why: OAuth flow causing race conditions...
# What: 1. processes list command 2. --guard flag 3. --force flag
# Done: Can see running processes, duplicates prevented

--> TodoWrite:
1. Add script.processes scope to auth
2. Create processes.py with list_processes()
3. Add processes list command to CLI
4. Add --guard/--force flags to run command
5. Test: processes list shows running jobs
6. Test: --guard aborts on duplicate
```

Each TodoWrite item is a checkpoint. When you complete item 3 and start item 4, pause: "Still on track?"

## The Draw-Up Pattern

**When you're filing work for a future Claude:**

1. **Write the brief thoroughly** — `why`/`what`/`done` must stand alone
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Define done clearly** — verifiable criteria, not vague "it works"

**The test:** Could a Claude with zero context execute this from the brief alone?

**Good draw-up:**
```bash
arc new "Add rate limiting to API" --for arc-gaBdur \
  --why "Users hitting 429s during peak, server struggling under load" \
  --what "1. Redis-based rate limiter 2. 100 req/min per user 3. Retry-After header" \
  --done "Load test shows 429s after 100 requests, header present, Redis storing counts"
```

**Bad draw-up (will fail):**
```bash
arc new "Fix the API thing" --for arc-gaBdur
# Error: Brief required. Missing: --why, --what, --done
```

## Session Boundaries

**At session start:**
1. `arc list --ready` — see what's available
2. Pick an action
3. **Draw-down** — read brief, create TodoWrite items

**At session close:**
1. Update arc items with progress
2. File new actions discovered during work
3. **Draw-up** — ensure briefs are complete for next Claude

**Between actions (mid-session):**
1. Complete current action: `arc done <id>`
2. Check what's unblocked: `arc list --ready`
3. If continuing, **draw-down the next action** before starting

## Brief Quality

The `brief` field has three required subfields:

| Subfield | Question it answers |
|----------|---------------------|
| `why` | Why are we doing this? |
| `what` | What will we produce/achieve? |
| `done` | How do we know it's complete? |

**For AI-created items**, briefs should include:
- **Concrete details:** File paths, function names, API endpoints
- **Numbered steps** in `what` when multiple deliverables exist
- **Verifiable criteria** in `done` — not "it works" but "returns 200 with valid token"

## Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Working without TodoWrite | No checkpoints, drift accumulates | Always draw-down |
| Thin briefs | Next Claude can't execute | Write for zero-context reader |
| Skipping draw-down on "continue" | Scope ambiguity | Always read brief, create todos |
| Motor through without pauses | Miss direction changes | Checkpoint at each TodoWrite completion |

## Vocabulary Reference

| Say This | Not This |
|----------|----------|
| Outcome | Epic, Story |
| Action | Task, Ticket |
| Waiting | Blocked, Blocker |
| Ready | Available |
| Done | Closed, Resolved |
