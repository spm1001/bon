---
name: plan
description: >
  Plan multi-session work as a bon hierarchy. Outcomes narrate the journey,
  actions carry execution detail, understanding.md provides the frame.
  Replaces plan mode for work that spans sessions. Triggers on 'plan this',
  'how should we approach', or when about to enter plan mode for non-trivial
  work. (user)
allowed-tools: [Read, Glob, Grep, Bash, Edit, Write, Agent, AskUserQuestion]
---

# Bon Plan

Express your thinking as a bon hierarchy instead of a plan file.

**Why this exists:** Plan files are orphans. Written once, never synthesized,
never updated. understanding.md has /open and /close maintaining it every
session. Bon items have tracking, persistence, tactical steps. This skill
channels planning into artifacts that are already alive.

**What it replaces:** Plan mode. Don't call EnterPlanMode — stay in normal
conversation mode where writing to understanding.md and creating bon items
is natural behavior, not a format conversion.

## When to Use

- Multi-session work: features, refactors, new components
- Work that needs handoff to a future Claude
- When you'd normally reach for EnterPlanMode

## When NOT to Use

- Quick exploration before a small fix — just read and work
- Single-session tasks — create a bon action directly, or just do it
- Research or investigation — explore first, plan when direction is clear

---

## The Calvino Principle

In Calvino's *If on a winter's night a traveller*, the chapter titles read
as a continuous story. The Table of Contents IS a narrative.

Your outcomes work the same way. Read them in sequence — they should tell
the implementation story:

> 1. A shared Yjs document serves a CodeMirror editor
> 2. Claude reads and edits the document as a Yjs peer
> 3. Documents are markdown files on disk, not CRDT blobs
> 4. Comments are a standalone messaging layer
> 5. Documents export cleanly to Google Docs

Each title is a clause in the story. Each outcome expands into actions with
rich `--how`. The narrative lives in the sequence; the detail lives in the
chapters.

---

## Phases

**Personal half (variation point `plan.personal` — a point inside this one rite, not a sibling command; one /plan for everyone):** if `~/.claude/mit-accent.md` exists and carries a `## plan.personal` section, Read it before Phase 1 and honour it at the points it names (spec and laws: `docs/ACCENT.md`). No file or no section — the common case, since plan's personal half is still reserved — means skip silently: the rite is complete without it, and an empty slot is never nagged.

### Phase 1: Orient

Read the terrain. Same exploration you'd do in plan mode, without entering
the mode.

1. Read `.bon/understanding.md` — the project's soul
2. Read `CLAUDE.md` — the manual
3. Explore the codebase: relevant source files, tests, existing patterns
4. Run `bon list` — what work already exists?

Take your time. Planning quality depends on understanding what's already here.

### Phase 2: Frame

Seed understanding.md with the architectural context that applies across all
outcomes. This is where cross-cutting concerns live — the content that would
have been Context, Approach, Gotchas, and Scope in a plan file.

> **Note — `understanding.md` has two authors.** `/plan` *seeds* this framing;
> `/open` then *maintains* it, synthesizing each session's handoff knowledge
> into the same file (`/open` → Synthesize Knowledge). Seed the durable
> architectural frame here and expect /open to grow it around what you wrote.

**Write to understanding.md:**
- Architectural decisions and rationale
- Key technical constraints discovered during orientation
- Scope boundaries — what we're NOT building
- Gotchas from existing code or dependencies
- Patterns to follow or avoid

**The sorting question:** Does it apply to multiple outcomes? →
understanding.md. Does it apply to one action? → that action's `--how`.

Present the understanding.md update to the user before proceeding.

### Phase 3: Narrate

Create outcomes whose titles, read in sequence, tell the implementation
story.

For each outcome:
- **Title:** Achievement language. What's true when this chapter is complete.
- **--why:** Why this chapter exists in the story.
- **--how:** Strategy and approach at the outcome level.
- **--what:** What will be true when achieved.
- **--done:** Verifiable completion criteria.
- **--badly:** The falsifier — **ask the user for it, never write it yourself.** See below.
- **--order:** Sequence position in the narrative.

**The narrative test:** Read all outcome titles in order. Ask the user:
"does this read as a story?" Reorder or reword until it does.

Create outcomes sequentially, not in parallel.

#### Asking for the falsifier

`--done` says how we'll know the work is **complete**. `--badly` says what would
show it went **wrong** — and the two are not the same question. A Claude can
satisfy `--done` by construction, and reliably does; "met the criteria but built
the wrong thing" is now a more common failure than "didn't finish". A falsifier
only catches that if the person who wants the answer wrote it, before work started.

This is ordinary GTD delegation, not an AI-era invention. It restores the half of
the Natural Planning Model's first phase that bon dropped: purpose *and
principles*. Allen's elicitation is the delegator's own sentence — *"I would give
others totally free rein to do this as long as they…"* — completed until you'd be
happy handing the project over.

So ask, in the user's own frame:

> "What would tell you this went wrong, even if I ticked every box in `--done`?"

Then **record the answer verbatim.** Their wording is the artefact; paraphrasing
it into criteria-speak is how it turns back into `--done`.

A falsifier you wrote is `--done` in a hat — it tests what you already intended to
do, which is exactly the thing that needed independent checking. So an invented
`--badly` is a test that cannot fail, and an empty one is an honest gap.

**But if they don't answer, the question is unasked — not declined.** Silence means
*"I didn't see it"*, never *"I don't care"* (a busy human misses questions far more
often than they dismiss them; the previous version of this section said "leave it
absent and move on", which institutionalises the wrong reading and predicts its own
empty column).
So an empty `--badly` is honest only while it is a **stated** gap: name the
outcomes that have no falsifier yet, on their own line near the end of the turn
where a question is actually visible, and raise it again next time rather than
letting it lapse. Outcomes only — an action like "fix the racing temp path" needs
no pre-registered falsifier, and the CLI will say so.

### Phase 4: Detail

Create actions under each outcome. Each action is a chapter opening — rich
enough that a cold-start Claude can pick it up and execute.

For each action:
- **--why:** Why this action matters for its parent outcome.
- **--how:** Implementation detail. Reference code patterns by file:line
  rather than pasting snippets — living references over stale snapshots.
  Include pitfalls, things to avoid, specific APIs. This is where
  execution quality lives.
- **--what:** Numbered steps (these become tactical steps via `bon work`).
- **--done:** How to verify completion.
- **--order:** Sequence within the outcome.

Set `waiting_for` where real dependencies exist, not just ordering preference.

**The self-containment test:** For each action, ask: could a Claude with
only this brief and understanding.md execute this? If not, the `--how`
needs more detail.

### Phase 5: Verify

Present the full hierarchy (capture `bon list` to a file and Read it).
Three checks:

1. **The Calvino test:** Read outcome titles in sequence. Does it narrate?
2. **The cold-start test:** Pick the hardest action. Could a fresh Claude
   execute it from the brief + understanding.md alone?
3. **The frame test:** Does understanding.md cover everything cross-cutting?

Iterate until the user is satisfied. The hierarchy IS the plan — there's
nothing else to write.

---

## What Goes Where

| Content type | Home | Example |
|---|---|---|
| Architecture decisions | understanding.md | "Y.Text not Y.XmlFragment because..." |
| Cross-cutting constraints | understanding.md | "Don't import Combine anywhere" |
| Gotchas from spikes | understanding.md | "StickyIndex constructor doesn't work" |
| Scope boundaries | understanding.md | "Not multi-user beyond one human + Claude" |
| Implementation strategy | Outcome --how | "Redis distributed locks, not file locks" |
| Per-step approach | Action --how | "Mirror Injector.swift:89-108 pattern" |
| Deliverables | Action --what | "1. Add middleware 2. Configure limits" |
| Completion criteria | Action --done | "P99 < 500ms at 500 RPS for 10 min" |
| The story | Outcome titles in order | Table of Outcomes |

---

## Quick Corrections

| About to do this | Do this instead |
|---|---|
| Call EnterPlanMode | Stay in normal mode, follow these phases |
| Write a plan file | Frame → understanding.md, work → bons |
| Paste code blocks in --how | Reference by file:line |
| Create one large outcome | Multiple outcomes that narrate a sequence |
| Skip --how on actions | --how is where execution quality lives |
| Put cross-cutting context on one action | Put it in understanding.md |
