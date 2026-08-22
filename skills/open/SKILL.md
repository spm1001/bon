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

Every bon item answers up to five questions. Three are required, two optional:

| Flag | Question | Required |
|------|----------|----------|
| `--why` | Why are we doing this? | Yes |
| `--how` | How will we approach it? | No |
| `--what` | What will we produce? | Yes |
| `--done` | How do we know it's complete? | Yes |
| `--badly` | What would show this went wrong? | No — outcomes, and **the human writes it** |

**`--badly` is the falsifier, and it is not a fifth flag bolted onto a four-field
form** — it restores the half of GTD's first planning phase that bon dropped
(purpose *and principles*). `--done` asks how we know the work is complete, which
a Claude can satisfy by construction and routinely does; `--badly` asks what
would show it went wrong. Those catch different failures, and "met the criteria
but built the wrong thing" is now the more common one.

It only works if the implementer didn't author it. **If you are filing the item,
leave `--badly` absent** — an absent falsifier is an honest, visible gap, while
one you wrote is `--done` in a hat: a test that cannot fail. `/plan` asks the
human for it, in their words, verbatim. `/review` checks work against it.
Outcomes only; the CLI nudges if it lands on an action.

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

1. Read the project's `understanding.md` — the session-start hook resolves and prints its path as `UNDERSTANDING=<path>` (a visible root/nearest-room copy if the repo uses the visible convention, else `.bon/understanding.md`). Read *that* path.
2. Read the `## For Claudes to come` section from the handoff
3. **Rewrite** that same `understanding.md` (the resolved path — not blindly `.bon/`) — integrate the new knowledge, make salience judgments, restructure where needed. Don't append.

This synthesis is onboarding. Integrating new knowledge into an existing document forces you to read the existing understanding, find where the new insight fits, and rewrite with judgment. By the time you're done, you know the project — not just the words on the page.

> **Note — `understanding.md` has two authors.** `/open` *maintains* it (synthesizing each handoff's durable knowledge, as above); `/plan` *seeds* it with architectural framing when planning multi-session work (`/plan` Phase 2). Same file, two roles — don't clobber plan-seeded framing during synthesis; integrate around it.

The handoff stays on disk — never delete it. Not every handoff has a compost zone; when absent, skip this step.

**Transition:** If `.bon/contributions/` contains files, process those the same way (read, integrate into understanding.md, delete the contribution files). This path is being retired.

### 2. Mint Pending Candidates

The latest handoff may carry a `### Candidates` section — board mutations proposed by a session that could see the board but couldn't reach a writer (candidate mode; the live case is a Cowork close). They are proposals, not tracked work: mint them now, or they're lost. When the handoff has no such section — the common case — skip this step.

For each candidate, run the matching verb, tagging where it came from so provenance survives:

- **NEW** → `bon new` (JSON stdin); add its origin to the brief, e.g. `"(candidate from Cowork session local_7c379a74, 2026-06-10)"`
- **DONE** → `bon done ID --note "…"`
- **EDIT** → `bon edit ID …`

Mint deliberately, not on autopilot: if a candidate is stale, already done, or wrong, drop it and say so to the user — a conscious drop is a real decision; an unnoticed one is the leak this step exists to close. The two worked examples (`~/notes/handoffs/2026-06-10-7c379a74.md`, `2026-06-12-804b6ba8.md`) carry their candidates as an "Opportunities — bon candidates" list rather than a `### Candidates` heading — treat that shape as candidates too.

**Then mark them minted**, so a re-open doesn't double-mint: edit the handoff's candidate heading to `### Candidates (minted YYYY-MM-DD)`. This is the step that re-syncs the board with the handoffs — it's what cures "where do I pick up".

**And adopt the file when its candidates belong to another board.** A candidate-mode handoff lands on whatever mount its session had, which isn't always the board that owns the work. When the board you just minted on is a different repo, move the handoff into that repo's handoffs dir in the same change (updating any ledger line that links it) — the board item and its artefact travel together. Minting the item while leaving the file behind lets it drift into another room's briefing: the 2026-08-04 Cowork hello wrote a mit-commons handoff to the notes root, its candidate was minted on the mit-commons board five days later, and the stranded file was then served as the baton to an unrelated notes session.

### 3. Present Hierarchy

Show the full picture — outcomes with progress and their actions — **as text in your response** (not via Bash, which collapses behind Ctrl+O).

Run `bon list`, capture to a temp file, Read and output:
```bash
OUT=$(mktemp /tmp/bon-hierarchy-XXXXXX.txt); bon list > "$OUT"; echo "$OUT"
```

Read the path it echoes. The path must be unique per session: a fixed
`/tmp/bon-hierarchy.txt` is shared by every concurrent `/open`, and on
2026-07-26 one session overwrote another's capture seconds before its Read —
the second session was one unnoticed glance from presenting a different repo's
board as its own (bon-potipe). Wrong-board orientation fails silently, so the
collision-proof path is the whole guard.

### 4. Toolmaking Compass

Sameer's session-boundary guide — where this session sits in his intentions. Render it right after the hierarchy, before picking direction: the compass informs the pick. (Origin and contract: bon-leturo; his framing — "the high level guide for me and a reminder of what we're going to do together.")

```bash
accomplis tasks --project "& Toolmaking" 2>/dev/null \
  | jq -r '.[] | "\(.priority)|\(.content)"'                  # his dispatch queue
accomplis tasks --project "Projects - Toolmaking" 2>/dev/null \
  | jq -r '.[] | select(.priority==4 and .parent_id==null and .section_id==null) | .content'   # his P1 DOs (root + un-sectioned = active; Someday section = parked)
```

The jq filters are load-bearing, not taste: the raw JSON runs ~37KB on a 30-line queue (every task carries full metadata and comments), which blows the Bash output cap and costs a persisted-file round trip (measured 2026-08-19). The render needs two fields; ask for two fields.

Render exactly three lines — the budget is fixed, do not grow it:

```
🧭 Toolmaking compass (read-only, HH:MM)
→ This repo: <queue lines pointing here> — or "nothing points here"
→ His P1 DOs: <priority-4 root tasks in Projects - Toolmaking, one clause each>
→ Queue: <N> lines; <one nudge — e.g. the oldest line with no matching board motion>
```

Matching "points here": the dispatch grammar is `Open <repo> → <desire> (<bon-id>)` — match the repo name against this repo, and any cited bon-id against this board's prefix. NB the Todoist API inverts the app's priority scale: the UI's P1 arrives as `priority: 4`.

Rules:
- **Gate on the CLI.** `command -v accomplis` absent → skip silently (not our estate, not his book). Present but erroring → render `🧭 Toolmaking compass: Todoist unreachable — not shown`. A missing compass must be visible, never silent.
- **The tap never writes.** Two reads, three lines. Writes to the queue are deliberate session acts under the tell-after norm — they live in /close's tap, never here.
- Cost: two CLI calls, ~2–3s. Invoke `accomplis:coaching` first if the session will touch Todoist beyond these two reads.

### 5. Pick Direction

Assess which ready items align with what's already in context — files read, handoff content, understanding document, the compass. State your reasoning briefly. When context is thin, just present the list.

User picks direction.

### 6. Read the Room

In a **multi-room repo** — one with a `rooms.md` index, or nested `CLAUDE.md` files below the root — read the tissue of the room you'll actually work in *before* touching its files: its `CLAUDE.md`, its `understanding.md`, and its recent `handoffs/`. Do this with the Read tool, yourself — the harness won't. It loads a subtree `CLAUDE.md` only on-demand (and Cowork not at all), and it *never* autoloads understanding.md or handoffs on any launch. A session that skips this works a room half-blind and mints twins — the `notes` egta twin was a duplicate room built beside its unread predecessor, caught twelve days later.

This fires **regardless of where the session launched**: a room-launched session still needs the explicit understanding.md + handoffs read, because the harness's upward walk carries only CLAUDE.md. `rooms.md`, when present, is the map of what rooms exist — read it first to place your work. In a single-room repo this is a no-op: the tissue the hook already resolved is the whole story.

Then **draw-down** before touching code.

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
- Parking work that's waiting on a scheduled event, not on a blocker: `bon work --release`
  keeps the steps and your position, hands the claim back so the session can draw down
  something else, and stops the step being injected into every prompt. `bon work <id>`
  resumes at the same step, no `--force`. Reach for this over `--clear` (discards) or
  `bon wait` (silently discards) whenever the progress is worth keeping.

### UserPromptSubmit Hook

A hook injects the current tactical step into every prompt. When you see a `<user-prompt-submit-hook>` mentioning bon tactical, work on the current step and, when complete, run the `bon step --expect N` invocation the hook prints — the guard refuses without writing if another session moved the board (re-read with `bon work --status`).

**The injected tactical may belong to another live session.** Session identity is CWD-keyed, so a parallel session in the same repo (a bg fork, a second roster session, a dispatched agent) sees — and is invited to advance — a tactical it didn't claim. If the injected step doesn't match work you've been asked to do, leave it alone: it's another Claude's thread, and stepping it desynchronises their bookkeeping (observed 2026-06-10: an email-dispatched session finished a tester's tactical and closed an item under them).

---

## The Draw-Up Pattern

**When filing work for a future Claude:**

1. **Add `--how` for complex work** — approach, constraints, things to avoid
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Number steps in `--what`** — these become extractable tactical steps
4. **Define `--done` clearly** — verifiable criteria, not vague "it works"
5. **Name the progenitor** — an item discovered mid-work opens `--why` with where it came from ("Discovered while working bon-A"). Write-once provenance: it never rots, grep finds it, and the genealogy survives without a schema field

**The test:** Could a Claude with zero context execute this from the brief alone?

### Use JSON stdin by default — for `bon new` **and** `bon edit`

**When creating outcomes or actions with `--how`, or with more than 3 numbered steps
in `--what`, use `bon new --json` — not flags.** Flags with backslash continuations
look like they work but produce quoting errors on special characters (quotes, backticks,
parentheses in technical content). JSON stdin eliminates this entire class of failure.

**`bon edit` reads JSON the same way**, and it matters more there, because an edit
rewrites content that already exists. Pipe an object with only the keys you want
changed — everything else is left alone:

```bash
printf '%s' '{"how": "Redis locks. Do not touch auth middleware."}' | bon edit bon-zovili
```

Brief fields work nested under `"brief"` or flat at the top level; an unrecognised key
is an error rather than a silent no-op. `"how": ""` clears the field.

**Annotating an item — appending to `--how` — is its own verb, never a
read-modify-write:**

```bash
bon edit bon-zovili --append-how "UPDATE: blocked on the API rename, resuming after."
printf '%s' '{"append_how": "Text with \"quotes\" survives the pipe."}' | bon edit bon-zovili
```

The append is atomic (sets the field when absent, joins with a blank line when
present). The old recipe — read the field, concatenate in python, write it back
with `--how` — silently REPLACES the field when any step misfires, which is how
a correction once destroyed the accurate half of another session's brief
(carte-vudusu). If you must script other whole-field edits, call bon via
`subprocess.run` with an argument **list** (no shell, so quotes can't be
reinterpreted), and read the field back — intent to encode is not execution
of encoding.

**Repairing a closing note:** `bon done ID --note` refuses to overwrite a note that's
already there, so a note mangled by shell quoting used to be permanent. `bon edit ID
--note "..."` is the way back (done items only; `--note ""` clears).

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

The JSON path honours `title`, `type`, `parent` (or `outcome`), `waiting_for` and `brief` — brief fields may also be given flat. `waiting_for` (a string or a list) lets an action be born blocked: `"waiting_for": ["bon-abc", "external review"]` creates it already waiting. Any other key is a hard error, never a silent drop — the same contract as `bon edit`.

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
bon list --group-by area     # Cluster by Area of Focus ((ungrouped) last); --area X filters to one

bon show ID                  # Full details including brief
bon show --current           # Active tactical steps
cat <<'EOF' | bon new -q                             # Pipe JSON to stdin (default)
{"title":"...","parent":"...","brief":{"why":"...","how":"...","what":"...","done":"..."}}
EOF
bon new "Quick fix" --why W --what X --done D -q     # Flags: only for one-line stubs
bon done ID                  # Complete (unblocks waiters)
bon done ID --note "reason"  # Complete with context
bon wait ID REASON           # Mark waiting (clears tactical!) — APPENDS to existing blockers, prints the resulting list
bon wait ID REASON --replace # Overwrite ALL blockers with this reason (correcting a stale one)
bon unwait ID                # Clear waiting (or one blocker: bon unwait ID BLOCKER)
bon unwait ID --note "..."   # Record WHY the block lifted (met/abandoned/decided against) — survives as released_note
bon work ID                  # Init tactical from --what
bon work ID "step1" "step2"  # Init with explicit steps
bon work --status            # Current tactical state
bon work --release           # Hand back the claim, KEEP the progress (resume with `bon work ID`)
bon work --clear             # Clear without completing (discards the progress)
bon step                     # Advance to next step
bon step --expect N          # Advance with CAS guard — refuses if the board moved (use the printed N)
bon step --skip "reason"     # Skip current step
bon step --no-complete       # Final step: don't auto-complete
bon edit ID --title/--why/--how/--what/--done/--note/--order  # Edit fields
printf '%s' '{"how":"..."}' | bon edit ID    # JSON stdin — only the keys present change
bon edit ID --how ""         # Clear how field
bon edit ID --note "..."     # Repair a closing note (done items only)
bon edit ID --parent NEW     # Move action to another outcome ('none' = standalone)
bon convert ID               # Action → outcome, or outcome → standalone action
bon convert ID --outcome P   # Outcome → action under P (demote + re-home in one move)
bon move ID --to REPO        # Move to another repo's board (path or ~/repos name);
                             # filed where you're cd'd ≠ where it belongs — move is cheap

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

**For reading items:** When piping `bon --json` output through inline python, use `python3 -c` (script as an argument) — **not** a heredoc:

```bash
bon list --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for o in data['outcomes']:
    if o['status'] != 'done':
        print(o['id'])
"
```

`python3 -c '…'` keeps stdin pointed at the pipe. `bon list --json | python3 <<'PYEOF' … PYEOF` is **broken**: the heredoc claims stdin, so python reads its *script* from there and the piped JSON never arrives — `json.load(sys.stdin)` then reads empty and raises. (If a heredoc is unavoidable, write the JSON to a file first and `json.load(open(path))`.)

### Creating Multiple Items

Create sequentially, not in parallel tool calls. If one fails, Claude Code cancels all sibling calls.

Pipe JSON to `bon new` for each item — clean heredocs with no escaping concerns:
