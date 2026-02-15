---
name: bon
description: GTD-flavoured work tracker. Activate before running any bon CLI command. Enforces draw-down workflow (bon show, bon work, bon step) that prevents drift and tracks tactical progress.
---

# Bon Work Tracking

Bon organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points — just ordering and "what can I work on now?"

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
bon new "API stays responsive under peak load" \
  --why "Users hitting 429s, server under load" \
  --what "1. Redis limiter 2. 100 req/min 3. Retry-After header" \
  --done "Load test passes, header present"
```

## Draw-Down (picking up work)

1. `bon show <id>` — read the brief
2. `bon work <id>` — activates tactical steps (parsed from numbered `--what`)
3. `bon step` — complete current step, advance to next
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
bon init --prefix myproj     # Initialize .bon/
bon list                     # Hierarchical view
bon list --ready             # Unblocked work only
bon show ID                  # Full details
bon show --current           # Active tactical steps
bon new "title" --why W --what X --done D       # Create outcome
bon new "title" --outcome PARENT --why W --what X --done D  # Create action
bon done ID                  # Complete (unblocks waiters)
bon wait ID REASON           # Mark waiting (clears tactical)
bon unwait ID                # Clear waiting
bon work ID                  # Start tactical steps
bon work ID "step1" "step2"  # Explicit steps
bon work --status            # Show tactical state
bon step                     # Advance to next step
bon edit ID --title/--why/--what/--done/--order  # Edit fields
bon edit ID --parent P       # Reparent ('none' for standalone)
bon convert ID               # Action → outcome
bon convert ID --outcome P   # Outcome → action
bon status                   # Overview counts
bon log                      # Recent activity
bon archive                  # Archive done items
bon reopen ID                # Reopen completed item
```

All commands support `--json`. Mutation commands support `-q` (quiet, prints ID only).

## Session Workflow

**Start:** `bon list --ready` → pick item → `bon show` → `bon work` → work through steps with `bon step`

**Transition:** `bon done <id>` → `bon list --ready` → draw-down next item

**End:** Complete finished items, file new actions with full briefs, ensure handoff context is complete.
