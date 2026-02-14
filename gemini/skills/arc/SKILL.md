---
name: arc
description: GTD-flavoured work tracker. Activate before running any arc CLI command. Enforces draw-down workflow (arc show, arc work, arc step) that prevents drift and tracks tactical progress.
---

# Arc Work Tracking

Arc organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points — just ordering and "what can I work on now?"

## Vocabulary

| Say This | Not This |
|----------|----------|
| Outcome | Epic, Story |
| Action | Task, Ticket |
| Waiting | Blocked |
| Done | Closed, Resolved |

## The Three Flags

Every item needs `--why`, `--what`, `--done` — all mandatory, all must stand alone for a zero-context reader.

```bash
arc new "API stays responsive under peak load" \
  --why "Users hitting 429s, server under load" \
  --what "1. Redis limiter 2. 100 req/min 3. Retry-After header" \
  --done "Load test passes, header present"
```

## Draw-Down (picking up work)

1. `arc show <id>` — read the brief
2. `arc work <id>` — activates tactical steps (parsed from numbered `--what`)
3. `arc step` — complete current step, advance to next
4. Final step auto-completes the action

Only one action may have active tactical steps per session. Steps persist across crashes.

## Draw-Up (filing work)

Include concrete details (file paths, endpoints, error messages). Define `--done` as verifiable criteria, not "it works". The test: could someone with zero context execute from the three flags alone?

## Outcome Language

Outcomes describe what will be true, not work to be done. Actions *should* use activity language.

| Bad (activity) | Good (achievement) |
|----------------|-------------------|
| Implement OAuth | Users can authenticate with GitHub |
| Build rate limiter | API stays responsive under peak load |

## Commands

```bash
arc init --prefix myproj     # Initialize .arc/
arc list                     # Hierarchical view
arc list --ready             # Unblocked work only
arc show ID                  # Full details
arc show --current           # Active tactical steps
arc new "title" --why W --what X --done D       # Create outcome
arc new "title" --outcome PARENT --why W --what X --done D  # Create action
arc done ID                  # Complete (unblocks waiters)
arc wait ID REASON           # Mark waiting (clears tactical)
arc unwait ID                # Clear waiting
arc work ID                  # Start tactical steps
arc work ID "step1" "step2"  # Explicit steps
arc work --status            # Show tactical state
arc step                     # Advance to next step
arc edit ID --title/--why/--what/--done/--order  # Edit fields
arc edit ID --parent P       # Reparent ('none' for standalone)
arc convert ID               # Action → outcome
arc convert ID --outcome P   # Outcome → action
arc status                   # Overview counts
arc log                      # Recent activity
arc archive                  # Archive done items
arc reopen ID                # Reopen completed item
```

All commands support `--json`. Mutation commands support `-q` (quiet, prints ID only).

## Session Workflow

**Start:** `arc list --ready` → pick item → `arc show` → `arc work` → work through steps with `arc step`

**Transition:** `arc done <id>` → `arc list --ready` → draw-down next item

**End:** Complete finished items, file new actions with full briefs, ensure handoff context is complete.
