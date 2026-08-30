# The Docket/Rite Contract v1

Bon is two artifacts currently wearing one repo:

- **The docket** — the work tracker: items, briefs, statuses, tactical claims. A CLI any vehicle can query. Stable; changes on the cadence of schema.
- **The rite** — the session liturgy: orientation at open, reflection and capture at close. Rides whatever vehicle hosts the session (Claude Code today; Cornichon and others tomorrow). Fast-moving; changes on the cadence of practice.

This document is the boundary between them. A vehicle author should be able to implement the rite against this contract without reading bon source. Decided with Sameer 2026-06-10 (marketplace-convergence conversation — session `875c25f7`, mise-en-space repo, where the split was conceived, the category framing agreed, and TodoWrite ruled out-of-category); refined here under bon-bilegu.

This split is the first of **three cuts** that constrain each other (per the 2026-06-12 Cowork brief, `~/notes/handoffs/2026-06-12-804b6ba8.md`): (1) ritual vs ticket — this document; (2) bon vs Todoist — settled as agent-of-record, see the category section; (3) the surface boundary — who reaches tickets from where, pointing at a future hezza-hosted web MCP. The contract is written so cuts 2 and 3 land without moving this boundary: the Todoist relationship is a typed-edge seam, and the query surface is transport-agnostic.

## The category, not the product

The rite does not demand bon. It demands a **durable work memory**: something that survives the session and answers four questions at the session edges.

| Question | Edge | Answered by |
|----------|------|-------------|
| What is open? | open | Docket (`list`) |
| What is next? | open | Docket (`list --ready`) + the previous handoff's suggestions |
| What changed? | close | Docket (items done/created this session) + the vehicle's own session memory |
| What did we learn? | close | Vehicle tissue (handoff, understanding.md), with item-grain residue in the docket (`done --note`, brief edits) |

Membership test: **survives the session AND answers the queries.** Bon is member #1. A future tracker earns a thin shim when it actually exists — the abstraction lives in this contract's vocabulary now; adapter machinery is deferred until a second member is real.

**TodoWrite and its analogues are out of category, not backends**: ephemeral by design, nothing on the far side of either session edge. A TodoWrite-only session takes the probe's absent branch and gets the graceful no-board rite.

**Todoist is out of category by agent, not by durability.** It survives sessions, but its reader is the human: items are attention-shaped (short, dated, reminder-borne), where docket items are brief-shaped (`--why`/`--how` at a depth no human task manager wants; the reader is a future Claude). The boundary, reached independently three times (the 2026-03-28 mind-sweep: "bons are local to repo agents, Todoist is the human-facing layer above"; notes-forebi; the 2026-06-12 Cowork brief): **agent of record**. The docket is Claude's work memory; Todoist is Sameer's attention queue. They connect by **typed edges at transfer points, never board sync** — a future docket facet (`needs: <person>` / `waiting-for: <person>`) may materialise a Todoist task with a backlink, completion flowing back as a note. Named here as a seam; built only when the edge is real. Anti-goals carried from the brief: don't move the human onto the docket, don't move briefs into the attention queue (attention tax is the worst available failure mode), don't let the rite depend on ticket machinery being reachable.

## The probe

Two independent axes, probed separately:

1. **Board visibility**: a `.bon/` directory at or above CWD (resolution is git-like — walk up, stop at the `.git` boundary).
2. **Writer reachability**: a conformant transport for the query surface — today the `bon` CLI on PATH; tomorrow possibly a web MCP (cut 3). Reachable means the edge-tier verbs answer.

| Board | Writer | Mode |
|-------|--------|------|
| visible | reachable | **Full-fat** — orientation and capture include the board |
| visible | unreachable | **Candidate mode** — see below |
| absent | (either) | **Board-less** — silent skip: zero board noise, no error text, no install suggestions. Still a rite: orient from the vehicle's own memory, reflect, capture |

**Candidate mode** is for surfaces that can see the repo but can't run the writer (Cowork's mounted sandbox is the live case). The rite still runs, knowledge-side: orientation reads the vehicle-owned tissue (latest handoff, understanding.md — plain files, no writer needed); at close, board mutations are written into the handoff as **candidates** — explicit, provenance-tagged proposals ("file X under Y", "close Z") — for a writer-bearing session to mint at its next open. Candidates that aren't minted at next open are wishes: the minting check is part of the full-fat open, not a courtesy. Two worked examples exist in `~/notes/handoffs/` (2026-06-10-7c379a74, 2026-06-12-804b6ba8); the convention graduated from prose to contract here because the prose version demonstrably leaked work (one of the 06-10 handoff's five candidates was minted).

The probe is cheap and read-only. It runs at session start and again before any board interaction; either axis can change mid-session (`bon init` flips the first; a transport coming up flips the second).

## The query surface

Two tiers. Verbs outside this surface are bon features, not contract — the rite must not depend on them. The minimal-surface principle: every verb named here is multi-vehicle surface area; adding one obligates every future backend's shim.

### Edge tier — required of any category member

| Verb (bon spelling) | Role | Edge |
|---------------------|------|------|
| `list` | What is open — full hierarchy | open |
| `list --ready` | What is next — unblocked actions | open |
| `show ID` | Drill into one item's brief | open |
| `new` (JSON stdin) | Capture work that emerged | close, mid-session |
| `done ID [--note]` | Record what changed | close, mid-session |
| `edit ID` | True up briefs as understanding moves | close |

Every edge-tier verb supports `--json`. Rendered text is for humans and text-first vehicles; programmatic vehicles consume JSON. Both are contract output — the rite never reads storage directly.

**The surface is the contract; transport is deployment.** Today's transport is the CLI on a local PATH. Cut 3 points at a second: a hezza-hosted web MCP serving the same verbs to surfaces that can't run the CLI (Cowork, claude.ai, mobile). The verb list above is deliberately the MCP's future verb list — a vehicle written against this surface doesn't care which transport answers. The MCP serves *tickets only*: handoffs and understanding.md stay plain files, because knowledge must survive the MCP being down.

### Tactical tier — optional capability, bon implements it

| Verb | Role |
|------|------|
| `work ID` | Claim an action, expand its steps |
| `step` | Advance the claim |
| `work --status` | Cheap mid-session state query |
| `wait ID` / `unwait ID` | Blocker bookkeeping |
| `someday ID CONDITION` / `unsomeday ID` | Someday/Maybe parking — a flag with a required revisit condition, never a status |

A backend without the tactical tier still satisfies the category — the rite degrades to edge-only (orientation and capture, no draw-down). A vehicle that finds the tier present may use it; one that doesn't loses checkpointing, not correctness.

## The caller-mistake ladder

The surface's only users are models, so how a verb behaves when its caller's
priors misfire is contract, not polish (adjudicated 2026-08-16, bon-siciri,
triangulated against the tool-ergonomics room's diagnostic — 300,637 estate
tool calls). Four responses, ascending:

1. **Absorb silently — never.** A silently-accepted mistake looks exactly like
   success, and worse: the forgiving harness is the training mechanism behind
   slop itself — malformed calls that still complete still get rewarded
   (Ronacher, "Better Models: Worse Tools"). Absorbing mistakes manufactures
   the next generation's bad priors.
2. **Refuse loudly, naming the right move.** The floor, and it is cheap:
   measured estate-wide, 76% of genuine errors succeed on the very next call —
   a clean refusal costs one retry. The error text is the teaching surface;
   no skill text is guaranteed loaded.
3. **Coach.** Accept, warn, proceed — for input the caller might genuinely
   mean (a falsifier on an action, an area on a parented action).
4. **Bend the grammar to the prior — and say so.** Earned only when the prior
   is strong and the intent unambiguous (JSON-on-stdin; `--parent` aliasing
   `--outcome`; `convert --outcome none`, a prior bon's own `edit` taught).
   A repair must be REPORTED in the tool result ("accepted `oldText` as
   `old`; canonical is `old`") — the tool result is the only channel that
   reaches the next cold session. Silent bending is rung 1 by another route.

Choosing a rung from evidence: a **stable** wrong grammar across callers is a
naming mismatch — bend to it; a **zoo** of different mistakes is a structural
ambiguity — refuse better. And a mistake that produces no error at all (the
bare-`new` outcome-mint) is invisible to transcript mining, so its fix is
announcement — making the outcome watchable is instrumentation, not courtesy.

Theory and estate measurements: `~/notes/practices/tool-ergonomics/brief.md`
and `diagnostic-2026-08-16.md` in that room.

## Ownership

`.bon/` is shared real estate: the docket owns the registry files inside it; the vehicle parks its session tissue there for git-tracking convenience. Ownership is by artifact, not by directory.

| Artifact | Owner | Why |
|----------|-------|-----|
| Items, briefs, statuses, archive | Docket | The work memory itself |
| The falsifier *field* (`brief.badly`) | Docket | Optional, outcomes-shaped; stored, rendered and emitted like any brief subfield |
| The `area` field | Docket | Optional Areas-of-Focus tag, emitted in `--json`; the CLI's grouped/filtered list views are bon features over it, not contract — a programmatic vehicle groups from the field itself |
| Falsifier *authorship* (who may write it, and when) | Rite | The data layer cannot know who typed a string — see below |
| Tactical claims (steps, position, session identity) | Docket | Coordination state — must be visible to all sessions |
| Claim *surfacing* (hooks, prompt injection, UI) | Rite, per vehicle | Each vehicle projects state its own way: CC via UserPromptSubmit hook, programmatic vehicles natively |
| Handoffs (visible `handoffs/`, fond-v1) | Vehicle | Session memory, not registry data — see HANDOFF-CONTRACT.md |
| understanding.md | Vehicle | Cross-session knowledge synthesis is rite behaviour |
| The "For Claudes to come" zone | Vehicle | Ditto |
| The probe | Rite | Detection-gating is rite behaviour |
| Session identity *scheme* | Contract seam | See below |

## The falsifier seam

`brief.badly` is an optional brief subfield: what would show this outcome went
**wrong**, as against `--done`'s "how do we know it's complete". It restores the
principles half of GTD's first planning phase, which bon's four-field brief had
collapsed to purpose alone.

The field is docket-side and behaves like every other brief subfield — validated,
rendered, `--json`-emitted (absent normalises to `null` at the read boundary; no
backfill of existing items). **The rule that gives it its value is not.** A
falsifier is only worth anything if the party doing the work did not author it,
and no schema can enforce that: the docket sees a string, not a hand. So the rule
lives in the rite — *the vehicle asks the delegator for it, records the answer
verbatim, and leaves the field absent when there is no answer rather than
composing one.* An absent falsifier is an honest gap; a self-authored one is
`--done` wearing a hat, and the docket would happily store it.

A vehicle that skips the asking is still contract-conformant; it just doesn't get
the benefit. Stated here so a future vehicle implements the discipline
deliberately rather than discovering the field and filling it in.

Two rites ask in this estate today: `/plan` at outcome creation, and `/review` as
an outcome enters the dispatch queue's Up Next lane (the lane-era form of the
apex/top-N venue adopted 2026-08-09, bon-hipapu, after adoption measured 2/134
with /plan as the sole venue; re-scoped 2026-08-30, bon-veleru). Both record the
answer verbatim and leave silence absent.

## The session-identity seam

Tactical claims are keyed by a session identity that the vehicle supplies and the docket stores and validates. Current convention: realpath of the `.bon` root, hostname-prefixed on shared backends. This conscripts parallel sessions in the same repo — any co-located session holds the same claim (bon-hibehi tracks sharpening, e.g. vehicle-supplied session lineage).

The contract names the seam without fixing the scheme: the docket stores an opaque string and compares it; **defining and supplying** the identity is vehicle-side, **storing and validating** it is docket-side. Whatever hibehi decides slots in here without moving the boundary.

## Non-goals

- **No CC assumptions in the docket.** Core output contains no Claude Code-specific text: no hook references, no skill names, no "/close" mentions. (Agent-facing coaching — outcome-language warnings — is fine; it's vehicle-neutral.)
- **The rite carries no tracker internals.** It consumes the contract surface only, via whatever transport serves it — never parses `items.jsonl`, never speaks to Dolt. Storage may change under it without notice.
- **No adapter machinery yet.** One category member exists. The contract is vocabulary, not plumbing.
- **The docket never initiates rite behaviour.** No auto-orientation, no liturgy text in CLI output.

## Two fat levels — relationship to couvert

Piano's couvert is a lightweight open/close skill with `SESSION_LOG.md` as its memory, projected into multiple runtimes by piano's author-once machinery. The rite and couvert share a skeleton — orient → work → reflect → capture → commit — and differ only in where session memory lives and whether a board participates.

**Shape verdict (bon-bilegu step 2): confirmed.** The probe's absent branch *is* couvert-shaped: board-less orientation from the vehicle's own memory, board-less capture at close. Nothing in this contract blocks the two becoming one artifact at two fat levels — full-fat when the probe finds a board, couvert when not. Whether they *should* merge (one skill, piano-projected) is a packaging question, deliberately deferred to bon-kepuko step 4.

## Worked example: a hypothetical non-CC vehicle

Sanity check that the contract is implementable without reading bon source (bon-bilegu step 3). A Gemini-style vehicle would need:

1. **Probe** — at session start: `test -d` walk-up for `.bon/` (stop at `.git`), `command -v bon`. Both pass → board branch; else silent skip. No CC machinery required: this is two shell checks.
2. **Orientation** — run `bon list --json` and `bon list --ready --json`; render in the vehicle's own idiom (Gemini's system-prompt projection, a TUI panel, whatever). Read the newest file in the repo's visible `handoffs/` for the previous session's suggestions — format per HANDOFF-CONTRACT.md.
3. **Mid-session** — optionally use the tactical tier (`work`, `step`, `work --status`) and surface the current step natively. No UserPromptSubmit hook exists in this vehicle; surfacing is its problem, per the ownership table.
4. **Close** — file new items by piping JSON to `bon new`; complete with `done --note`; write a fond-v1 handoff into the repo's visible `handoffs/`; synthesize its own understanding document.

Every call is instructions + CLI. Nothing requires Claude Code, hooks, or bon internals. The one CC-flavoured artifact the vehicle touches is the handoff *format* (fond-v1) — which is why HANDOFF-CONTRACT.md is vehicle-side spec, versioned independently of the docket.

**And the degraded case isn't hypothetical — Cowork is running it now.** A Cowork session sees the repo as a mount: board visible, no CLI, no git. Per the probe table it takes candidate mode: orientation from the latest handoff and understanding.md (plain file reads), close writes a fond-v1 handoff to the mount with board mutations listed as provenance-tagged candidates, commit skipped (a writer-bearing hezza session sweeps and mints at next open). Two real handoffs exercise this path. A vehicle author implementing candidate mode has working examples, not just this spec.

## Relationship to existing artifacts

- **HANDOFF-CONTRACT.md** — the handoff file format (fond-v1). Vehicle-side; unchanged by the split.
- **The bon instruction shard** — CC's projection of the rite's always-on rules. Its "When `.bon/` exists…" conditional is this contract's probe in shard form. Its TodoWrite/bon line is inherited by this contract's category test, not blurred by it.
- **skills/open, skills/close, hooks/** — CC's projection of the rite. The split makes them one projection among N, not the rite itself.
