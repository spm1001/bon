---
name: arc
description: Lightweight work tracker for Claude-human collaboration using GTD vocabulary. Triggers on 'arc init', 'arc new', 'arc list', 'arc done', 'what can I work on', 'next action', 'desired outcome', 'file this for later', 'waiting for', 'track this work', or when starting/finishing arc items. Use when tracking outcomes and actions across sessions. For single-session linear tasks, use TodoWrite directly.
---

# Arc Work Tracking

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

## Quick Example: Draw-Down in Action

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

Read the arc item → Break into TodoWrite checkpoints → Work with pauses. That's the pattern.

## Running Arc

Arc is a Python CLI. If it's installed in the project:

```bash
uv run arc list              # If arc is a project dependency
arc list                     # If arc is in PATH
```

If arc isn't installed locally, use the full path:

```bash
/Users/modha/Repos/arc/.venv/bin/arc list
# Or add alias: alias arc='/Users/modha/Repos/arc/.venv/bin/arc'
```

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
arc init --prefix myproj     # Initialize .arc/ with prefix
arc list                     # Hierarchical view of open outcomes and actions
arc list --ready             # Actions with no waiting_for (outcomes always shown)
arc show ID                  # Full details including brief
arc new "title" --why W --what X --done D       # Create outcome
arc new "title" --for PARENT --why W --what X --done D  # Create action
arc done ID                  # Complete item (also unblocks waiters)
arc wait ID REASON           # Mark as waiting
arc unwait ID                # Clear waiting
arc edit ID                  # Edit in $EDITOR
arc status                   # Overview counts
arc migrate --from-beads F --draft  # Generate migration manifest
arc migrate --from-draft F   # Import completed manifest
```

All commands support `--json` for structured output. `arc new` supports `-q` for quiet mode (just prints ID).

## Migrating from Beads

Migration is a two-phase process — the tool extracts structure, you write proper briefs.

### Phase 1: Generate Draft Manifest

```bash
bd export --format jsonl > beads-export.jsonl
arc migrate --from-beads beads-export.jsonl --draft > manifest.yaml
```

This produces a YAML manifest with:
- **Structure preserved:** epics → outcomes, tasks → actions, parent relationships
- **`_beads` context:** raw description/design/acceptance_criteria/notes for reference
- **Empty `brief` placeholders:** you must fill why/what/done

**Orphan actions are excluded.** Standalone tasks/bugs with no parent epic are reported but not included — they need an outcome to live under.

### Phase 2: Complete Briefs and Import

Review `manifest.yaml`. For each item, use `_beads` context to write proper briefs:

```yaml
- id: proj-abc
  title: User Authentication
  _beads:
    description: Add OAuth to the app
    design: Use passport.js with JWT
    notes: "COMPLETED: research. NEXT: implement"
  brief:
    why: Users need secure, frictionless login    # ← Fill this
    what: OAuth2 flow with Google/GitHub options  # ← Fill this
    done: Users can login, tokens refresh correctly  # ← Fill this
```

Then import:

```bash
arc migrate --from-draft manifest.yaml
```

**Validation enforced:**
- All briefs must be complete (why/what/done non-empty)
- `.arc/` must not already exist
- `_beads` context is stripped on import

### Why This Pattern?

Beads fields don't map cleanly to arc's opinionated brief structure. Rather than auto-generating weak briefs, the manifest pattern forces you to think about each item's why/what/done — resulting in items that future Claudes can actually execute.

## The Draw-Down Pattern

**When you pick up an action to work on:**

1. **Read the brief:** `arc show <id>` — understand `why`, `what`, and `done`
2. **Create TodoWrite items** from `brief.what` and `brief.done`
3. **Show user the breakdown:** "I'm reading this as: [list]. Sound right?"
4. **VERIFY:** TodoWrite is not empty before proceeding
5. **Work through items with checkpoints** — pause at each completion to confirm direction

**The test:** If work will take >10 minutes, it needs TodoWrite items.

**Why this matters:** Without draw-down, you work from the arc item directly, context accumulates, and by close you've drifted. TodoWrite creates checkpoints where course-correction happens.

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

## Session Start Protocol (Integration with /open)

**Arc is loaded automatically by /open when `.arc/` exists.** The startup hook generates context at `~/.claude/.session-context/<encoded-cwd>/arc.txt`.

### What to Check

1. **Read the arc context file** — shows ready work and full hierarchy
2. **Check for handoff** — previous session may have left "Next" suggestions
3. **Present ready items** — outcomes and actions that can be worked on now

### Presenting Arc Items to User

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

**STOP. Do the draw-down before writing any code:**

1. `arc show <id>` — read the brief (why/what/done)
2. Create TodoWrite items from `brief.what` and `brief.done`
3. Show user: "Breaking this down into: [list]. Sound right?"
4. **VERIFY:** TodoWrite is not empty
5. Then start working

## Session Close Protocol

**At session close:**
1. Complete finished items: `arc done <id>`
2. File new actions discovered during work (with full briefs)
3. **Draw-up** — ensure briefs are complete for next Claude
4. Handoff mentions arc items worked on

## Mid-Session Transitions

**Between actions:**
1. Complete current action: `arc done <id>`
2. Check what's unblocked: `arc list --ready`
3. If continuing, **draw-down the next action** before starting

**The gap this fills:** Draw-down happens at session start because /open commands it. But mid-session transitions need the same discipline.

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
