# The shared work-atom — a sketch

**Date:** 2026-06-17 (evening)
**Status:** SKETCH — for the next session to *test*, not gospel. Companion to `2026-06-17-todoist-substrate-anatomy.md`.

> **SUPERSEDED IN BOTH HALVES — 2026-08-16 (bon-wivuti).** The projection half died first: the estate ruled twice against syncing (the 2026-07-11 portfolio cull; the 2026-08-02 treaty table — Todoist holds what Sameer has committed to, bon holds what the workshop is doing about it, **nothing syncs**), and the gap a projection was meant to fill is served by the weekly Toolmaking reconciliation ceremony instead. The schema-delta half is now adjudicated: `context`, `tier`, `provenance` and tier-gated briefs are all **rejected** with reasons recorded in `.bon/understanding.md` ("The work-atom sketch's schema deltas"); the deferred Areas-of-Focus question ships as the `area` field (bon-razonu). Don't re-derive this bet.
**Purpose:** Design a single work-atom that serves both Sameer (+ human team) and Claude (+ future autonomous team), owned by bon/Dolt, projected into faces (Todoist, kuwivo). Relates to `bon-kepuko` (docket contract), `bon-welogi` (MCP), `bon-kuwivo` (GUI face), `bon-pujawo` (candidate mode), `bon-hibehi` (session identity).

## The landing that produced this (tonight's arc, compressed)

- The two systems are **photographic negatives**: Todoist drops the outcome→action link and stores *context* (the human's hard bit is *where/when/headspace*, not *why*); bon stores the link + spec and no context (the agent's hard bit is the link it can't retain across cold starts, and it needs no reminder-context because being handed the task *is* the reminder).
- **The SaaS truth:** semantics-wrapped-round-a-database is the asset; the DB is commodity. The agent-grade semantics (spec, real dependencies, enforced `done`) are *bon's*, not Todoist's. bon is already semantics-over-Dolt — twice over, since Dolt adds git-semantics (branch/diff/history) Todoist can't touch. So **bon/Dolt owns the atom; faces are projections.**
- **The spike taught us two things in the flesh** (real Goals+tasks in Sameer's Todoist, 2026-06-17):
  1. **GIFT — the goal-link is orthogonal to the project.** An action can live in `Smooth Brain` (human context) *and* carry its `🎯 outcome` chip (agent link) at once. The GTD "killer weirdness" (link not stored) is solved *without de-contexting the action*. This is the key enabler.
  2. **STRIKE — putting the spec *into* Todoist bloats it.** The full why/what/done as a task description sprawls a paragraph next to "rebook Nigel"; nothing enforces it (Claude "was the rails"); the dependency was theater (a `blocked-by` label Todoist can't act on). → the spec must live in bon, where it's enforced; faces stay lean.

## The core idea: one atom, two tiers, orthogonal overlays

The atom is an **Action** sitting at the intersection of a **spine edge** (→ its Outcome, for the agent) and a **context bucket** (where/when/headspace, for the human) — the two are orthogonal, so it serves both readers simultaneously. Discipline is applied **on promotion, not on everything**: most actions are loose human *reminders*; an action becomes an agent-grade *spec* only when promoted, at which point the store enforces the contract.

This is the central reconciliation: bon today mandates a full brief on *every* item — correct when bon is agent-only, a **misfeature once a human shares the store.** The two-tier action keeps Sameer's air loose while guaranteeing agents only ever pick up enforced specs.

## Entities

### Outcome  (= Goal, in a Todoist face)

| field | serves | Todoist face | enforced | notes |
|---|---|---|---|---|
| `id` | both | bracket-tag in name | store | immutable, pronounceable |
| `title` | both | `Goal.name` | store | achievement-framed (past-tense + so-what) |
| `intent` (why) | both | `Goal.description` (lean) | store | one line, not a wall |
| `done` (success definition) | agent | `Goal.description` | store | when is the *outcome* achieved |
| `horizon` | human | project grouping | store | `active` \| `someday` \| (area-of-focus above) |
| `owner` | team | `Goal.responsibleUid` | store | maps cleanly — Goals carry an owner |
| `deadline` | both | `Goal.deadline` | optional | |

### Action  (= Task, in a Todoist face)

| field | serves | Todoist face | enforced | notes |
|---|---|---|---|---|
| `id` | both | bracket-tag | store | immutable |
| `title` | both | `Task.content` | store | next-action framed, concrete |
| `parent` → Outcome | **agent** | **goal-link (orthogonal!)** | store | the edge bon owns; trivial for the human to recall, impossible for the agent to retain |
| `tier` | both | `@spec` label | store | **`reminder`** \| **`spec`** |
| `brief{why,what,done}` | agent | `Task.description` (drill-in, **not** the list) | store, **mandatory iff `tier=spec`** | the verifiable completion contract |
| `waiting_for` → Action | **agent** | chip / hint only | store, **with unblock-on-done** | the REAL dependency edge; faces can only *hint*, never enforce |
| `context` | **human** | `Task.project` / label | human assigns; **Claude proposes** | where/when/headspace (Smooth/Munchy/Curly/Toolmaking/At-Home…) — the field bon lacks today |
| `due` | human | `Task.dueString` | optional | human time-anchor |
| `assignee` | team | `Task.responsibleUser` | optional | |
| `provenance{actor,status}` | both | label | store | `minted` \| `candidate`; which session/human/agent created it (ties to pujawo + hibehi) |
| `status` | both | checkbox | store | `open` \| `done` |

## Five design moves (where the night's lessons live)

1. **Discipline on demand.** Enforcement triggers at `tier=spec` (why/what/done + a resolvable parent become mandatory). Reminders stay free. Promotion `reminder→spec` *is* the agent-handoff moment — the point a human task becomes pick-up-able by Claude.
2. **Context ⟂ parent.** Both first-class, neither displaces the other (the spike gift). New field for bon. Claude *proposes* the context (the bit Sameer finds hard); Sameer confirms with a tap.
3. **Dependencies are real edges in bon, hints in faces.** `waiting_for` + unblock-on-done is the thing Todoist structurally cannot do. bon owns the truth; faces show a "blocked" chip but can't gate or auto-unblock.
4. **Faces are lean and they specialize.** bon/Dolt = truth + enforcement + dependency graph + change feed. **Todoist** = casual context/capture/reminder surface (mobile, NL, *your air*) — title + context + goal-chip + due, spec on drill-in/backlink. **kuwivo** = the dependency-aware "what's *ready* / what's *blocked*" view — which is *exactly the thing Todoist can't render*, so kuwivo earns its place rather than duplicating Todoist. **bon CLI** = the agent's verb surface.
5. **Provenance travels.** Every atom carries actor + minted/candidate. Candidate-mode (pujawo) and the change-feed/actor work (welogi) drop straight in.

## Deltas to bon's *current* atom

- **Add** `context` (Action).  **Add** `tier` (Action; `reminder`|`spec`).  **Add** `provenance{actor,status}`.  Optionally `due`, `horizon`, `owner/assignee`.
- **Relax** the mandatory `brief` to **tier-gated** (mandatory only when `tier=spec`). Backward-compatible: every existing item is `tier=spec` and already has a brief.
- Keep `parent`, `waiting_for` + unblock-on-done, `id`, `status`, `brief{why,what,done,how?}` unchanged.

## What the next session should TEST

1. **Encode 3–5 real bon actions in the new atom** (add context, tier, provenance) — does the model hold without contortion?
2. **Build the *lean* projection into Todoist** (title + context + goal-chip; spec stays in bon) — does the human list stay clean *this* time, vs tonight's bulky spike? This is the make-or-break for "Todoist as a face."
3. **Promotion flow** `reminder→spec` — does enforcement kick in cleanly; is the promotion ergonomic?
4. **Confirm the face split**: dependencies as real edges in bon, hint-chips in Todoist, the ready/blocked view rendered by kuwivo (prove Todoist *can't* do it, so kuwivo isn't redundant).
5. **Decide the projection mechanism**: one-way bon→Todoist + narrow back-flow (done, context-reassign, new loose reminders the human jots) — built into welogi's MCP, or a separate sync?

## Open questions

- Migration: relaxing mandatory-brief is a CLI/schema change — verify it doesn't break validation or existing fixtures. (Should be additive + backward-compatible.)
- Does the human ever author `spec`-tier directly, or only via Claude promotion?
- `context`: single value or multi (Todoist labels allow many; an action could be both `@toolmaking` and `@curly`)?
- Areas of Focus / GTD horizons — model now, or defer?
- Back-flow conflict handling — if Sameer edits a projected task in Todoist while bon also changed it (the sync problem in miniature, even one-way).
