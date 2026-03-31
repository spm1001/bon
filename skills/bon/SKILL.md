---
name: bon
description: "Activate at session start when .bon/ exists AND before any bon CLI command. Handles session orientation (process contributions, present hierarchy, pick direction) and enforces draw-down workflow (bon show → bon work → bon step). Triggers on: session start with .bon/, /bon, 'bon init', 'bon new', 'bon list', 'bon done', 'what can I work on', 'next action', 'desired outcome', 'file this for later', 'track this work', or when .bon/ directory exists."
allowed-tools: "Bash(bon:*)", Read, Glob, Edit, Write
---

# Bon

Bon organizes work as **Outcomes** (desired results) and **Actions** (concrete next steps). No sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

---

## Session Start Ritual

The session-start hook provides orientation automatically (understanding, handoff, outcomes, suggested items). Your job at session start is the LLM-mediated work the hook can't do.

### 1. Process Contributions

If `.bon/contributions/` contains files:

1. Read `.bon/understanding.md`
2. Read each contribution file
3. **Rewrite** understanding.md — integrate new knowledge, make salience judgments about what matters, what's been superseded, what's new. Don't append.
4. Delete processed contribution files

If no understanding document exists but the project has substantial history, consider writing one from scratch. Expensive, but only happens once.

### 2. Present Hierarchy

The hook shows outcome titles. You show the full picture — outcomes with progress counts and their actions, **as text in your response** (not via Bash — Claude Code collapses tool output >10 lines behind Ctrl+O, making it invisible to the user).

Read the bon context file at `~/.claude/.session-context/<encoded-cwd>/bon.txt` and output it directly. To compute the path: `echo "$(pwd -P)" | sed 's/[^a-zA-Z0-9-]/-/g'`

If the context file is stale or missing, run `bon list` and capture to a file, then Read and output:
```bash
bon list > /tmp/bon-hierarchy.txt
```

### 3. Pick Direction

After listing ready items, assess which align with what's already in context — files read, handoff content, understanding document, recent work. State your reasoning briefly: "bon-xyz is closest to what I have loaded because..." This saves the user from mentally cross-referencing.

When context is thin (fresh session, no files read beyond startup), skip the ranking — just present the list honestly.

User picks direction. Then **draw-down** before touching code.

---

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

---

## The Draw-Down Pattern

**Pre-flight checklist** (before touching code):

1. **`bon show <id>`** — verify the item exists and check its type
   - If the ID came from a handoff, memory, or previous session, it may have been archived or done. Verify first.
   - If `Type: outcome`, you can't `bon work` it — pick one of its actions instead.
   - If `Type: action`, proceed.
2. **`bon work <id>`** — initialize tactical steps from `--what`
   - If `--what` has no numbered steps, provide explicit ones: `bon work <id> "Step 1" "Step 2"`
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

### UserPromptSubmit Hook

A hook injects the current tactical step into every prompt, making it impossible to ignore. When you see a `<user-prompt-submit-hook>` mentioning bon tactical, that's the hook — it fires on every prompt while tactical steps are active. Work on the current step, run `bon step` when complete.

---

## The Draw-Up Pattern

**When filing work for a future Claude:**

1. **All three flags required** — `--why`/`--what`/`--done` must stand alone
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Define `--done` clearly** — verifiable criteria, not vague "it works"
4. **Number steps in `--what`** — these become extractable tactical steps

**The test:** Could a Claude with zero context execute this from the three flags alone?

**Good draw-up:**
```bash
bon new "Add rate limiting to API" --outcome bon-gabdur \
  --why "Users hitting 429s during peak, server struggling under load" \
  --what "1. Redis-based rate limiter 2. 100 req/min per user 3. Retry-After header" \
  --done "Load test shows 429s after 100 requests, header present, Redis storing counts"
```

### When to Track vs Just Do

| Track in Bon | Just do it |
|-------------|------------|
| Multi-session work | Quick single-step action |
| Work needing handoff to future Claude | Research / exploration |
| Complex outcomes with multiple actions | Trivial fix (typo, config tweak) |
| Creating work for others to pick up | Side quest that'll be done in minutes |

**The test:** If resuming after 2 weeks would be difficult without context, it needs a bon item.

---

## Core Commands

```bash
bon init --prefix myproj     # Initialize .bon/ with prefix
bon list                     # Hierarchical view of open outcomes and actions
bon list --ready             # Actions with no waiting_for (outcomes always shown)
bon show ID                  # Full details including brief
bon show --current           # Show action with active tactical steps
bon new "title" --why W --what X --done D       # Create outcome
bon new "title" --outcome PARENT --why W --what X --done D  # Create action (--for and --parent are aliases)
bon done ID                  # Complete item (also unblocks waiters)
bon done ID --note "reason"  # Complete with context (stored as done_note)
bon wait ID REASON           # Mark as waiting (clears tactical steps!)
bon unwait ID                # Clear waiting
bon work ID                  # Initialize tactical steps from --what (if numbered)
bon work ID "step1" "step2"  # Initialize with explicit steps (actions only)
bon work --status            # Show current tactical state
bon work --clear             # Clear tactical steps without completing
bon step                     # Complete current step, advance to next
bon step --skip "reason"     # Skip current step (records reason)
bon step --no-complete       # On final step, don't auto-complete the action
bon edit ID --title T        # Change title
bon edit ID --why/--what/--done  # Edit brief fields
bon edit ID --parent P       # Reparent (use 'none' for standalone)
bon edit ID --order N        # Reorder within parent
bon convert ID               # Action → outcome (preserves ID/metadata)
bon convert ID --outcome P   # Outcome → action under P
bon status                   # Overview counts
```

All commands support `--json` for structured output. `bon new` supports `-q` for quiet mode (just prints ID).

---

## JSON Field Reference

**`bon show ACTION --json`** returns:
```json
{
  "id": "bon-muvuri", "type": "action", "title": "...",
  "brief": { "why": "...", "what": "...", "done": "..." },
  "status": "open", "parent": "bon-zovili", "order": 2,
  "waiting_for": null, "tactical": { "steps": [...], "current": 0, "session": "..." },
  "created_at": "...", "updated_at": "...", "done_at": null, "done_note": null
}
```

**`bon show OUTCOME --json`** — same shape but with nested `"actions": [...]` array, no `parent` or `waiting_for`.

**Field-name traps** (from real failures):

| Wrong | Right | Notes |
|---|---|---|
| `item["created"]` | `item["created_at"]` | Timestamp, not date |
| `item["why"]` | `item["brief"]["why"]` | Brief fields are nested |
| `item["what"]` | `item["brief"]["what"]` | Brief fields are nested |
| `item["done"]` | `item["brief"]["done"]` | Also: `item["done_at"]` is the completion timestamp |
| `item["note"]` | `item["done_note"]` | Only present when `bon done --note` was used |
| `item["parent_id"]` | `item["parent"]` | String ID or null |
| `item["actions"][0]` | Check `"actions" in item` first | Only present on outcomes via `bon show` |
| `item["tactical"]` | May be absent | Only present after `bon work` has been run |

**JSON shape contract:**
- `bon list --json` → `{"outcomes": [...], "standalone": [...]}` (wrapper object)
- `bon show ID --json` → single object, NOT an array (use `.field` not `.[0].field`)

---

## Common Mistakes

These errors appear repeatedly in real Claude sessions. Check here before inventing flags.

| What you typed | What to use instead | Why it fails |
|---|---|---|
| `bon add "title"` | `bon new "title"` | `add` isn't a command |
| `bon new -t action -p proj` | `bon new "title" --outcome ID --why ...` | No short flags. All long-form. |
| `bon done ID --resolution "text"` | `bon done ID --note "text"` | `--resolution` doesn't exist |
| `bon --dir /path done ID` | `cd /path && bon done ID` | No `--dir` flag. Bon always uses CWD. |
| `bon work OUTCOME_ID` | `bon show OUTCOME_ID` then pick an action | `work` is for actions only |
| `bon step` (at session start) | `bon show --current` or `bon work ID` | Check for active tactical first |

### Shell Escaping in Inline Python

When piping `bon --json` through inline python, **use a heredoc, not a double-quoted string**:

```bash
# WRONG — the \! bug (seen in 4+ separate sessions):
bon list --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for o in data['outcomes']:
    if o['status'] != 'done': print(o['id'])   # bash mangles \!=
"

# RIGHT — heredoc avoids all shell escaping issues:
bon list --json | python3 << 'PYEOF'
import json, sys
data = json.load(sys.stdin)
for o in data["outcomes"]:
    if o["status"] != "done":
        print(o["id"])
PYEOF
```

### Creating Multiple Items

**Create bon items sequentially, not in parallel tool calls.** If one `bon new` fails (e.g. missing `--why`), Claude Code cancels all sibling tool calls — you get 1 real error and N ghost errors.

### Stale Global Install

If a valid flag (e.g. `--note`) gives `unrecognized arguments`, the global `bon` binary is stale. Run: `uv cache clean bon && uv tool install ~/Repos/bon --force --reinstall`

---

## Outcome Language Coaching

Outcomes describe what will be true, not work to be done. The CLI warns on activity-verb titles automatically.

**Coach before `bon new` for outcomes:**

| Activity (bad) | Achievement (good) |
|----------------|-------------------|
| Implement OAuth | Users can authenticate with GitHub |
| Build rate limiter | API stays responsive under peak load |
| Add test coverage | Claudes don't hit surprising edges |
| Migrate to new format | Data flows cleanly through the new pipeline |

**The pattern:** Past-tense or present-state verb, describes what's *different* when done, includes the "so what."

**Don't coach on actions.** Actions *should* be activity language — "Add OAuth callback endpoint" is a fine action title.

---

## Mid-Session Transitions

Between actions:
1. Complete current action: `bon done <id>`
2. Check what's unblocked — run `bon list --ready`, capture to file, Read and output as text
3. Draw-down the next action before starting

**The gap this fills:** Draw-down happens at session start. Mid-session transitions need the same discipline.

---

## Session Close Protocol

At session close:
1. Complete finished items: `bon done <id>`
2. File new actions discovered during work (with full briefs)
3. **Draw-up** — ensure briefs are complete for next Claude
4. Handoff mentions bon items worked on
5. **Contribute to understanding** — if you learned something durable about the project (a landmine, an architectural insight, a taste judgment), write a short prose fragment to `.bon/contributions/`. One paragraph, timestamped filename (`YYYY-MM-DDTHHMMSS.md`). Not everything — only what a future Claude would benefit from knowing. These get synthesized into `.bon/understanding.md` by a future session's start ritual.

---

## Reorganization with Convert

When work evolves and classifications change, use `bon convert` instead of archive+recreate:

```bash
bon convert bon-zokte                          # Action → outcome (preserves ID)
bon convert bon-gabdur --outcome bon-tufeme    # Outcome → action under parent
bon convert bon-gabdur --outcome bon-tufeme --force  # With children → standalone
```

**Why convert > archive+recreate:** Preserves original ID (links in notes/handoffs stay valid), preserves timestamps, single command.
