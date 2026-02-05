# Design: Tactical Step Tracking

Decompose an action's work into steps, track progress, prevent drift.

## Problem

TodoWrite provides session-scoped checkpoints. But:
- It's separate from arc (context switch)
- State doesn't persist across sessions
- No connection to the action's brief
- Allows parallel work on multiple items (drift risk)

Arc actions have `--what` fields that often contain numbered steps. We should track progress through them directly.

## Solution

Add tactical step tracking to actions. Steps are checkpoints, not journals. **Serial execution enforced** — only one action may have active tactical steps at a time.

## Philosophy: Serial vs Parallel

```
Parallel layer:  Actions     — multiple can be open, pick any
Serial layer:    Steps       — one action at a time, linear progress
```

**TodoWrite:** Flat list, parallel possible, drift happens in practice.

**Arc tactical:** Hierarchical, serial enforced, drift prevented by design.

The constraint is a feature. If you need to context-switch mid-action:
1. Mark the action as waiting: `arc wait arc-xyz "blocked on visa"`
2. Start work on a different action: `arc work arc-other`

This surfaces the block explicitly rather than accumulating hidden partial progress.

## Commands

### `arc work <id> [steps...]`

Initialize tactical steps for an action.

```bash
# Parse steps from --what field (if numbered)
arc work arc-xyz

# Explicit steps (override or when --what is prose)
arc work arc-xyz "Add scope" "Create module" "Wire CLI" "Test"
```

**Behavior:**
- If no steps provided, parse numbered items from `--what` (see Parsing Rules below)
- If `--what` is prose (no numbers found), error: "provide explicit steps or add numbered list to --what"
- Sets `current: 0` (on first step)
- If another action has active tactical, error: "arc-other has active steps. Complete it, wait it, or run `arc work arc-other --clear`"
- If this action already has steps with progress (`current > 0`), error: "steps in progress. Run `arc work --force` to restart from step 1"
- If this action has steps but no progress (`current == 0`), overwrites silently (no work lost)

**Output:**
```
→ 1. Add oauth2 scope [current]
  2. Create rate limiter module
  3. Wire into CLI
  4. Test
```

### `arc work --status`

Show current tactical state without advancing.

```bash
arc work --status
```

No ID needed — finds the active tactical (there's only one).

**Output (if tactical active):**
```
Working on: Add rate limiting to API (arc-xyz)

✓ 1. Add oauth2 scope
→ 2. Create rate limiter module [current]
  3. Wire into CLI
  4. Test
```

**Output (if no tactical active):**
```
No active tactical steps. Run `arc work <id>` to start.
```

### `arc work --clear`

Clear tactical steps without completing the action.

```bash
arc work --clear
```

No ID needed — clears the active tactical (there's only one).

Use when: steps were wrong, want to restructure, or abandoning this approach.

**If no tactical active:** Silent success (nothing to clear).

### `arc step`

Complete current step, advance to next.

```bash
arc step
```

**Behavior:**
- Increments `current`
- If `current == len(steps)`, auto-completes the action (sets status=done, done_at=now)
- No arguments — serial means there's only one place to advance
- No notes — steps are checkpoints, not journals

**Output (mid-work):**
```
✓ 1. Add oauth2 scope
→ 2. Create rate limiter module [current]
  3. Wire into CLI
  4. Test

Next: Create rate limiter module
```

**Output (final step):**
```
✓ 1. Add oauth2 scope
✓ 2. Create rate limiter module
✓ 3. Wire into CLI
✓ 4. Test

Action arc-xyz complete.
```

**Errors:**
- No active tactical: "no steps in progress. Run `arc work <id>` first"
- Action already complete: "action already complete"

### `arc show <id>` (updated)

Shows tactical section when present.

```
○ Add rate limiting to API (arc-xyz)
   Type: action
   Status: open
   Parent: arc-abc (API Improvements)

   --why: Users hitting 429s during peak load
   --what: 1. Add oauth2 scope 2. Create rate limiter 3. Wire CLI 4. Test
   --done: Load test shows 429s after 100 requests

   Steps (2/4):
   ✓ 1. Add oauth2 scope
   → 2. Create rate limiter module [current]
     3. Wire into CLI
     4. Test
```

### `arc show --current`

Show only the action with active tactical steps. For hook injection.

```bash
arc show --current
```

Returns nothing (exit 0, no output) if no tactical active.

## Parsing Rules for `--what`

When `arc work <id>` is called without explicit steps, parse from `--what`:

**Pattern:** `(\d+)[.)]\s*(.+?)(?=\d+[.)]|$)`

- Looks for digit(s) followed by `.` or `)`
- Captures everything until the next numbered item or end of string
- Strips leading/trailing whitespace from each step

**Examples:**

```
--what: 1. Add scope 2. Create module 3. Test
→ ["Add scope", "Create module", "Test"]

--what: 1) Add scope, 2) Create module, 3) Test
→ ["Add scope,", "Create module,", "Test"]

--what: First add scope (1), then create module (2)
→ Error: no numbered list found (parenthetical numbers don't match pattern)

--what: Add the scope and create the module
→ Error: "provide explicit steps or add numbered list to --what"
```

**Newlines handled:**
```
--what:
1. Add scope
2. Create module
→ ["Add scope", "Create module"]
```

## Schema

Addition to action items in `items.jsonl`:

```json
{
  "id": "arc-xyz",
  "type": "action",
  "title": "Add rate limiting to API",
  "brief": {
    "why": "Users hitting 429s during peak load",
    "what": "1. Add oauth2 scope 2. Create rate limiter 3. Wire CLI 4. Test",
    "done": "Load test shows 429s after 100 requests"
  },
  "status": "open",
  "tactical": {
    "steps": [
      "Add oauth2 scope",
      "Create rate limiter module",
      "Wire into CLI",
      "Test"
    ],
    "current": 1
  }
}
```

**Fields:**
- `tactical`: null/absent until `arc work` called
- `tactical.steps`: array of strings (step descriptions)
- `tactical.current`: 0-indexed pointer to current step

**Progress derived from `current`:**
- `index < current` → done
- `index == current` → active
- `index > current` → pending
- `current == len(steps)` → all done (action auto-completed)

**Invariant:** At most one action in `items.jsonl` may have `tactical` with `current < len(steps)` at any time.

## Context Injection

### Command output (immediate)

Every `arc step` returns current state. Claude sees progress as tool output.

### UserPromptSubmit hook (persistent)

Optional hook injects arc state before every prompt:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "type": "command",
      "command": "arc show --current 2>/dev/null || true"
    }]
  }
}
```

This gives Claude persistent awareness of tactical state without explicit queries.

## Edge Cases

| Case | Behavior |
|------|----------|
| `arc work` on outcome | Error: "tactical steps only for actions" |
| `arc work` when another action has steps | Error: "arc-other has active steps..." |
| `arc work` when this action has progress | Error: "steps in progress. Use --force to restart" |
| `arc work` when this action has steps but no progress | Overwrites silently |
| `arc work --force` | Clears existing steps, starts fresh |
| `arc work --force` with explicit steps | Works: `arc work arc-xyz --force "A" "B" "C"` |
| `arc work --clear` with no active tactical | Silent success (nothing to clear) |
| `arc work --status` with no active tactical | Shows "no active tactical steps" message |
| `arc step` with no tactical | Error: "no steps in progress" |
| `arc step` when already complete | Error: "action already complete" |
| `arc done` with incomplete steps | Completes action, preserves tactical for forensics |
| `arc wait` with active steps | Clears tactical, sets waiting_for (see note below) |
| `arc edit --what` with active tactical | Allowed; steps may now be out of sync with --what |
| Final `arc step` | Auto-completes action, preserves tactical |

### Why `arc wait` clears tactical

If you're blocked long enough to formally mark an action as waiting, you should re-evaluate the steps when you return. The world changed while you waited.

This is intentional. Short blocks (waiting for API response, build running) don't need `arc wait` — just wait. Long blocks (need human input, external approval) warrant re-planning.

**Crash recovery is different.** Session crash or context exhaustion doesn't clear tactical — it persists in `items.jsonl`. When you return, `arc show --current` shows exactly where you were. The serial constraint prevents drift; persistence prevents data loss.

## What This Replaces

**TodoWrite** for arc-tracked work. The draw-down pattern becomes:

```
arc show arc-xyz          # Read the brief
arc work arc-xyz          # Initialize steps from --what
arc step                  # Checkpoint 1
arc step                  # Checkpoint 2
...                       # (auto-completes on final step)
```

**Key difference:** Persistence. TodoWrite state is lost on session crash or context exhaustion. Tactical steps survive in `items.jsonl`.

TodoWrite remains for:
- Non-arc work (quick tasks, exploration)
- Work that doesn't fit the arc model

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Actions only | Outcomes are containers; work happens in actions |
| Serial (one active) | Prevents drift. Parallel is at action level, not step level. |
| No notes | Steps are checkpoints, not journals. Handoff captures learnings. |
| Auto-advance | Simpler than step numbers. `arc step` always means "this one, next." |
| Auto-complete on last step | Natural completion. No ceremony. |
| Parse from --what | Briefs often have numbered steps. Reward good briefs. |
| Protect progress | `--force` required to discard in-progress work. |
| `arc wait` clears tactical | Long blocks warrant re-planning. Short blocks don't need `arc wait`. |
| Preserve tactical on done | Forensic value: see what steps were active at completion. |
| `--status`/`--clear` need no ID | Only one active tactical; symmetric ergonomics. |

## Not In Scope

- Step dependencies (always linear)
- Step timestamps (noise)
- Skipping steps (complete or restructure)
- Notes per step (handoff is the journal)
- Nested steps (use child actions instead)
- Undo/back (re-init with --force if needed)
- Multiple active tacticals (serial by design)
- Pause-and-resume at exact step (not a real workflow; crash recovery handles accidental interruption, `arc wait` means re-plan on return)

## Implementation Order

1. Schema: add `tactical` field to action items
2. `arc work`: parse --what, accept explicit steps, enforce single-active
3. `arc work --status`: show current state
4. `arc work --clear`: abandon steps
5. `arc step`: advance, auto-complete
6. `arc show`: display tactical section
7. `arc show --current`: for hook injection
8. Skill update: document draw-down with tactical
9. Hook example: UserPromptSubmit injection
