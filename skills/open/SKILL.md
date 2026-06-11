---
name: open
description: "Activate at session start when .bon/ exists AND before any bon CLI command. Handles session orientation (process contributions, present hierarchy, pick direction) and structures draw-down workflow (bon show → bon work → bon step). Triggers on: session start with .bon/, /open, /bon, 'bon init', 'bon new', 'bon list', 'bon done', 'what can I work on', 'next action', 'desired outcome', 'file this for later', 'track this work', or when .bon/ directory exists."
allowed-tools:
  - "Bash(bon:*)"
  - Read
  - Glob
  - Edit
  - Write
---

# Bon

Bon tracks work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

---

## The Brief

Every bon item answers four questions. Three are required, one optional:

| Flag | Question | Required |
|------|----------|----------|
| `--why` | Why are we doing this? | Yes |
| `--how` | How will we approach it? | No |
| `--what` | What will we produce? | Yes |
| `--done` | How do we know it's complete? | Yes |

`--how` captures approach, strategy, constraints, and sequencing — things that don't belong in `--what` (deliverables) or `--why` (motivation). For simple work, skip it. For anything with technology choices, ordering dependencies, or coordination needs, include it.

**For outcomes:** `--how` is the overall strategy. "Use Redis distributed locks, not file locks. Coordinate with API gateway. Don't modify auth middleware."

**For actions:** `--how` is the specific approach. "Parse the JSONL with streaming reads, not load-all. Test with the 10k-item fixture."

**`bon work` surfaces `--how` as "Approach:" above the step list**, so the executing Claude has strategy context before touching code.

---

## Plans Become Bons

When you'd normally enter plan mode, create bon items instead. A bon hierarchy **replaces** a plan file — it's persistent, trackable, and the next Claude can pick it up.

| Plan mode | Bon |
|-----------|-----|
| Goal/context | `--why` |
| Approach, strategy, constraints | `--how` |
| Steps (ordered) | `--what` (numbered → tactical steps) |
| Success criteria | `--done` |

**The transmutation:**
1. Think through the work as you normally would
2. Create an outcome with `--why` (motivation) and `--how` (strategy)
3. Break into actions with `--how` (approach per step) and `--what` (numbered deliverables)
4. The plan IS the bon hierarchy — no separate document to maintain

**The test:** After creating the bons, could you delete the plan file with no information loss?

---

## Session Start Ritual

The session-start hook provides orientation automatically (handoff, outcomes, suggested items). Your job is the LLM-mediated work the hook can't do.

The hook output may be truncated in the system-reminder preview. When you see "Output too large ... Full output saved to: {path}", Read that file — the handoff (including "For Claudes to come") is likely past the truncation point.

### 1. Synthesize Knowledge

The most recent handoff may contain a `## For Claudes to come` section — durable knowledge written by the previous Claude to transcend their session. When present:

1. Read `.bon/understanding.md`
2. Read the `## For Claudes to come` section from the handoff
3. **Rewrite** understanding.md — integrate the new knowledge, make salience judgments, restructure where needed. Don't append.

This synthesis is onboarding. Integrating new knowledge into an existing document forces you to read the existing understanding, find where the new insight fits, and rewrite with judgment. By the time you're done, you know the project — not just the words on the page.

The handoff stays on disk — never delete it. Not every handoff has a compost zone; when absent, skip this step.

**Transition:** If `.bon/contributions/` contains files, process those the same way (read, integrate into understanding.md, delete the contribution files). This path is being retired.

### 2. Present Hierarchy

Show the full picture — outcomes with progress and their actions — **as text in your response** (not via Bash, which collapses behind Ctrl+O).

Run `bon list`, capture to a temp file, Read and output:
```bash
bon list > /tmp/bon-hierarchy.txt
```

### 3. Pick Direction

Assess which ready items align with what's already in context — files read, handoff content, understanding document. State your reasoning briefly. When context is thin, just present the list.

User picks direction. Then **draw-down** before touching code.

---

## The Draw-Down Pattern

**Pre-flight checklist** (before touching code):

1. **`bon show <id>`** — verify the item exists, check its type and brief
   - If the ID came from a handoff or memory, it may have been archived. Verify first.
   - If `Type: outcome`, pick one of its actions instead.
2. **`bon work <id>`** — initialize tactical steps from `--what`
   - Shows "Approach:" context from `--how` when present
   - If `--what` has no numbered steps, provide explicit ones: `bon work <id> "Step 1" "Step 2"`
3. **Work through with checkpoints:** `bon step` after each
4. **Final step auto-completes** the action

**Constraints:**
- **Actions only** — `bon work` on an outcome will error
- One active tactical per session (CWD) — different worktrees can run in parallel
- Two CWDs cannot claim the same action
- Context-switch: `bon wait <id> "reason"` (clears tactical — re-plan on return)

### UserPromptSubmit Hook

A hook injects the current tactical step into every prompt. When you see a `<user-prompt-submit-hook>` mentioning bon tactical, work on the current step and run `bon step` when complete.

**The injected tactical may belong to another live session.** Session identity is CWD-keyed, so a parallel session in the same repo (a bg fork, a second roster session, a dispatched agent) sees — and is invited to advance — a tactical it didn't claim. If the injected step doesn't match work you've been asked to do, leave it alone: it's another Claude's thread, and stepping it desynchronises their bookkeeping (observed 2026-06-10: an email-dispatched session finished a tester's tactical and closed an item under them).

---

## The Draw-Up Pattern

**When filing work for a future Claude:**

1. **Add `--how` for complex work** — approach, constraints, things to avoid
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Number steps in `--what`** — these become extractable tactical steps
4. **Define `--done` clearly** — verifiable criteria, not vague "it works"

**The test:** Could a Claude with zero context execute this from the brief alone?

### Use `bon new --json` by default

**When creating outcomes or actions with `--how`, or with more than 3 numbered steps
in `--what`, use `bon new --json` — not flags.** Flags with backslash continuations
look like they work but produce quoting errors on special characters (quotes, backticks,
parentheses in technical content). JSON stdin eliminates this entire class of failure.

**The rule:** Pipe JSON to `bon new` for all real work. Flags are only for quick
throwaway stubs: `bon new "Fix typo" --why w --what x --done d -q`

```bash
cat <<'EOF' | bon new -q
{
  "title": "API stays responsive under peak load",
  "parent": "bon-zovili",
  "brief": {
    "why": "Load tests show 5s P99 at 200 RPS — users are dropping off",
    "how": "Redis distributed locks, not file locks. Don't modify auth middleware.",
    "what": "1. Add rate limiter middleware 2. Configure per-endpoint limits 3. Load test at 500 RPS",
    "done": "P99 < 500ms at 500 RPS sustained for 10 minutes"
  }
}
EOF
```

**Standalone actions** — for field reports, one-off fixes, observations — use `type: "action"`:

```bash
cat <<'EOF' | bon new -q
{
  "type": "action",
  "title": "Field Report: OAuth flaky under concurrent load",
  "brief": {
    "why": "Noticed 3 failures in 10 test runs under load",
    "what": "Document the pattern, identify root cause",
    "done": "Either fixed or filed as action under appropriate outcome"
  }
}
EOF
```

### When to Track vs Just Do

| Track in Bon | Just do it |
|-------------|------------|
| Multi-session work | Quick single-step action |
| Work needing handoff to future Claude | Research / exploration |
| Complex outcomes with multiple actions | Trivial fix (typo, config tweak) |
| Anything with approach worth preserving | Side quest done in minutes |

---

## Mid-Session Transitions

Between actions:
1. Complete current action: `bon done <id>`
2. Run `bon list --ready`, capture to file, Read and output
3. Draw-down the next action before starting

---

## Session Close

Use `/close` at session end. It handles reflection, handoff, and capture.

---

## Outcome Language Coaching

Outcomes describe what will be true, not work to be done. The CLI warns on activity-verb titles automatically.

| Activity | Achievement |
|----------|-------------|
| Implement OAuth | Users can authenticate with GitHub |
| Build rate limiter | API stays responsive under peak load |
| Add test coverage | Claudes don't hit surprising edges |

**Don't coach on actions.** Actions *should* be activity language.

---

## Core Commands

```bash
bon init --prefix myproj     # Initialize .bon/ with prefix
bon list                     # Hierarchical view
bon list --ready             # Actions with no blocker
bon show ID                  # Full details including brief
bon show --current           # Active tactical steps
cat <<'EOF' | bon new -q                             # Pipe JSON to stdin (default)
{"title":"...","parent":"...","brief":{"why":"...","how":"...","what":"...","done":"..."}}
EOF
bon new "Quick fix" --why W --what X --done D -q     # Flags: only for one-line stubs
bon done ID                  # Complete (unblocks waiters)
bon done ID --note "reason"  # Complete with context
bon wait ID REASON           # Mark waiting (clears tactical!)
bon unwait ID                # Clear waiting
bon work ID                  # Init tactical from --what
bon work ID "step1" "step2"  # Init with explicit steps
bon work --status            # Current tactical state
bon work --clear             # Clear without completing
bon step                     # Advance to next step
bon step --skip "reason"     # Skip current step
bon step --no-complete       # Final step: don't auto-complete
bon edit ID --title/--why/--how/--what/--done/--order  # Edit fields
bon edit ID --how ""         # Clear how field
bon edit ID --parent NEW     # Move action to another outcome ('none' = standalone)
bon convert ID               # Action → outcome, or outcome → standalone action
bon convert ID --outcome P   # Outcome → action under P (demote + re-home in one move)
bon status                   # Overview counts
```

All commands support `--json` for output. `bon new` reads JSON from piped stdin by default — no flag needed. `bon new` supports `-q` (quiet, prints ID only).

---

## JSON Field Reference

**`bon show ACTION --json`** returns:
```json
{
  "id": "bon-muvuri", "type": "action", "title": "...",
  "brief": { "why": "...", "how": "...", "what": "...", "done": "..." },
  "status": "open", "parent": "bon-zovili",
  "waiting_for": null, "tactical": { "steps": [...], "current": 0, "session": "..." }
}
```

`how` is `null` in JSON output when not set. Absent from stored data when not provided.

**Field-name mapping:**

| Instead of | Use |
|---|---|
| `item["why"]` | `item["brief"]["why"]` |
| `item["how"]` | `item["brief"]["how"]` |
| `item["done"]` | `item["brief"]["done"]` (not `item["done_at"]`) |
| `item["parent_id"]` | `item["parent"]` |

**JSON shape contract:**
- `bon list --json` → `{"outcomes": [...], "standalone": [...]}`
- `bon show ID --json` → single object (use `.field` not `.[0].field`)

---

## Quick Corrections

| What you typed | Use instead | Why |
|---|---|---|
| `bon add "title"` | `bon new "title"` | `add` isn't a command |
| `bon work OUTCOME_ID` | Pick an action | `work` is for actions only |
| `bon step` (at session start) | `bon show --current` first | Check for active tactical |
| `bon done ID --resolution "text"` | `bon done ID --note "text"` | `--resolution` doesn't exist |
| Recreate item under new outcome | `bon edit ID --parent NEW` | Re-parenting is one edit, not a copy-and-close dance |

### Shell Escaping

**For creating items:** Pipe JSON to `bon new` with a heredoc for anything with special
characters (quotes, backticks, parentheses). Flags are only for quick stubs.

**For reading items:** When piping `bon --json` output through inline python, use a heredoc:

```bash
bon list --json | python3 << 'PYEOF'
import json, sys
data = json.load(sys.stdin)
for o in data["outcomes"]:
    if o["status"] != "done":
        print(o["id"])
PYEOF
```

### Creating Multiple Items

Create sequentially, not in parallel tool calls. If one fails, Claude Code cancels all sibling calls.

Pipe JSON to `bon new` for each item — clean heredocs with no escaping concerns:
