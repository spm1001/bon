# Pyramid Format — the review's opening view

Format settled by the operator's own hand-edit of the first live pyramid (2026-08-01). An operator's accent (`## review` → `review.exemplars`, docs/ACCENT.md) may name canonical exemplar copies on their estate — the edited working copy is the desire-truth, the archived snapshot the baseline. When they differ, the operator's edits are the freshest desire data — diff before regenerating, fold their lines back in, never overwrite them.

**The lane-era mechanics were adjudicated at the 2026-08-29 ceremony** (with the first lane run, 2026-08-23), which ran the queue-population step by hand before this spec was written; its record's mechanics footer holds the adjudicated shape: one annotation pass joining every queue line against the survey, bucket-is-verdict triage, the workable lane refilled in the operator's approved order. Where an operator's accent (`review.exemplars`) names that archived record and it disagrees with this file, the record wins — it is the spec's source (bon-veleru); on a machine without it, this file stands alone.

**The draft-and-edit loop is load-bearing.** The skill generates a DRAFT; the operator's edit pass adds desire-knowledge no board holds (the first run added three whole workstreams no board mentioned). Treat their edited lines as data, not formatting.

## Document shape

```markdown
# Bon Review

As of <date> — ~N significant Desired Outcomes (M open in all) across K boards

## Cross-cutting Work
✅ Recent Progress:  (2–3 multi-repo achievement lines)
🚧 Desired Outcomes (top 4 — the operator's ranking, <date>)
1. <repo>: <desire in one line>          ← ranked, each with a next action in reach

## 🧠 Knowledge Work
(mermaid loop map — accent-supplied, see below)
✅ Recent Progress:
- <Repo>: <one human-grain line>
🚧 Desired Outcomes
- <Repo>: <one line per significant DO>
Small/dormant:
- <repo> (n), <repo> (n)                 ← the tail is named, never silently dropped

## 📺 MIT / ITV delivery
… same two-list shape per group …

## 🤝 Alignment (the lanes ARE the join)
Your list → the boards: <what checking every line found — which shipped, which formally wait, which dates slipped, which ids no longer resolve>
The boards → your list: <work moving with no line — worth a line? worth a lane? benign and self-contained?>
<one reading of the lanes themselves — e.g. a with-operator-lane swell>
(the rendered pyramid is HIS document — these lines land at human grain; "annotation pass" and "drift sweep" stay stage direction)

## 🅿️ Parked / Someday
- <board or outcome>: <why parked> — revisit <condition>
```

Where the queue exists and Up Next is dry (or draining), the pyramid opens with an `## Up Next refill candidates (proposal — your order to set)` list right after the headline — dispatch-shaped lines in the queue's own grammar, entering the lane only at adjudication (2026-08-29 exemplar). In a book with no queue, the Alignment section and this refill list both skip named — the shape keeps its other sections.

## Jobs-group display mapping

The survey emits `job` slugs (from Dolt `repos.job` via `bon register --job`, or a JSONL board's `.bon/job` marker). Render them as:

| slug | header |
|------|--------|
| `knowledge-work` | 🧠 Knowledge Work |
| `mit-delivery` | 📺 MIT / ITV delivery |
| `batterie` | 🔪 Batterie — the kitchen itself |
| `estate-infra` | 🏠 Estate & infrastructure |
| `apps-research` | 🔬 Apps & research |

Boards in `jobs_unassigned` get a one-line "Unassigned — where do these live?" list at the bottom of the pyramid; agree placement with the operator, then persist it (`bon register --job <slug>` from the clone for Dolt boards; write `.bon/job` for JSONL boards). Never guess a group silently.

**The jobs-groups are not the operator's task-system carve, and shouldn't be forced to match it.** The worked example that settled this (2026-08-09, bon-jagoha step 6): one Todoist project whose DOs spanned all five jobs-groups. The mapping is many-to-many and the alignment block below IS the join — render it, don't mirror either carve onto the other (settled 2026-08-09, bon-jagoha step 6).

## Line grain

One line per repo, plain English at human grain: "mit-plongeur: Handed over to Flore Data", not item IDs or counts. Derive Recent Progress lines from `recent_dones` (titles + done_notes) and `git.last_commit`, compressed by judgment — pick what a Monday-morning operator would want to know, drop the plumbing. Desired Outcomes lines come from open outcomes at their own wording, tightened. Headline counts are **Desired Outcomes, not items** — an item count is workshop trivia; a DO count is a commitment count.

**Parked items are excluded from the headline DO count** (a parked project's outcomes aren't open commitments). Parking is first-class since suite 1.30.0: the survey's `someday` field on an item carries its revisit condition, and the Parked/Someday section renders from it — each line shows the condition, and the review's Someday re-check pass (SKILL.md Phase 3) fires conditions that have come true. Boards parked only in prose (the previous pyramid's hand-curated list) get carried forward once more and converted to real `bon someday` flags as they're confirmed.

## Stockpot loop (Knowledge Work only)

Accent-supplied (`review.loop-map`): where the operator's accent names a canonical loop map, embed it as a small mermaid flowchart with per-stage health (🟢🟡🔴) and a one-line caption; without one, skip the loop map — the pyramid is complete without it. Health = whether each stage's output actually feeds the next, judged from the survey's motion data (recent dones + git), not asserted from memory.

## Alignment block (the lanes ARE the join)

The pyramid gains a `## 🤝 Alignment` section. In the lane era the join between the operator's book and the boards is the queue itself — **membership = whose move it is, order = what's next** — so the block reads the reconciliation off the annotation pass (see Queue population below) rather than rendering a separate DO-headings join. Two directions, and both are the block's product:

- **Queue → boards**: every line's cited bon verified live in the annotation pass — ticks found, formal waits, overdue dates, id rot. (2026-08-29 exemplar: 34 lines checked in one pass; one tick, one formal wait, one overdue, no id rot.)
- **Boards → queue (drift sweep)**: board motion with no queue line — new boards carrying no jobs-group, shipped work deserving a tick, a deadline arguing a line up a lane, motion that warrants a proposed mint. Self-contained motion (a board quietly maintaining itself) is benign — say so rather than minting noise.

Read the lanes themselves as a finding too: the 2026-08-29 run's headline was a with-operator swell (13 → 22 in the loop's first week) — the loop moving work to the operator's court faster than the weekly ceremony drains it.

Fetch via the accomplis tooling — where accomplis exists, invoke the `accomplis:coaching` skill first for structure discovery and semantics. A book with no Todoist at all skips the block the same one-named-line way as the population step — absence is a non-event, not a fault. If Todoist is expected but unreachable, render the pyramid **without** the block and say so — a silently missing section reads as "nothing to align". (The old shape — his DOs as headings, bon outcomes grouped under — retired with the flat queue, 2026-08-30, bon-veleru; the join's grain moved from DO-level to line-level when the lanes arrived.)

## Falsifier ask (outcomes entering Up Next)

As lines settle into Up Next at adjudication, ask the operator for a `--badly` falsifier — in their words, verbatim — on any entering outcome that lacks one. One ask per outcome per ceremony, at the lane threshold only; no nagging further down the board, and /plan remains the venue for new outcomes. Never draft the falsifier for them — a Claude-authored one is `--done` in a hat (the bon-meliga authorship rule). Venue adopted 2026-08-09 (bon-hipapu) as "the ceremony's apex"; the apex became the Up Next threshold when the lanes arrived (2026-08-29 exemplar: the falsifier landed on the trial-deadline outcome as its line entered the lane, in the operator's words).

## Queue population (socket: `review.populate-queue`)

**The populated lanes are the ceremony's product — not a proposed top-N for hand adoption.** (Rewritten 2026-08-30, bon-veleru, from the 2026-08-23 and 2026-08-29 ceremonies; the flat-queue "dispatch proposal" this section replaces would have produced the wrong artefact at any lane-era ceremony.) This step is a variation point, not the rite's spine: it exists where the operator runs a dispatch queue, and a review with no queue skips it complete — one plain line ("no dispatch queue in this book, so no lane population this review") and move on. The socket name is stage direction for the Claude; it never renders at the human.

**The lane model** (adjudicated 2026-08-23; the operator's accent `review.queue` names their queue project, its lane names, and any semantics pointer): the queue project's sections are status lanes, and a queue line wants exactly two bits of state, neither of them a field — **whose move is it** (lane membership: the workable lane = the loop's, the with-operator lane = theirs) and **what's next** (position: their drag order — the Sync API's `child_order`, which accomplis emits as `order`; a jq on `.child_order` nulls silently against this surface). The unsectioned rest is backlog the loop leaves alone. Line grammar is unchanged — `Open <repo> → <desire fragment> (<bon-id>)` — and expect standing lines to carry stale bon-ids from mid-week closes; refreshing them is part of the ceremony, not an error.

**Pre-annotation — the ceremony's real instrument.** Before the conversation, join every queue line — all three lanes, backlog included (the 2026-08-29 pass checked the whole project) — against board truth from the ONE Phase 1 survey pass: each line gets its cited bon's live state (open / done with date / parked / formally waiting, i.e. `waiting_for` set) plus any board motion around it. This table is what let a 44-line triage cost the operator one word per line on 2026-08-23 — without it the human triages from memory and the ceremony drowns. The conversational clusters are just the table's pagination. Four edge rules, each hit on a live queue: fetch every line's **description** at annotation time — steers live there, and a content-only read cannot tell a steer-bearing line from a bare one; a failed join is not yet id rot — the survey's `recent_dones` is capped (10 per board, inside `window_days`), so a cited id it can't see may simply be done-and-aged-out, and `bon show` from the clone is the fallback before you call it rot; a line with NO cited id joins on nothing — annotate it "no board join" and bucket it only in conversation, never silently (4 of 35 live lines on 2026-08-30); and resolve repo names tolerantly — the queue is a human surface, so a fragment's name may drop the org prefix or the owner bucket, and the survey's repos-table labels settle most of them.

**Bucket IS the verdict.** Triage and sorting fuse into one pass — a line's answer is its destination, with no separate ranking step:

| Verdict | Move |
|---|---|
| tick | work shipped — `accomplis done`; ticks are the done log, never reword their lines |
| yours | the operator's move — lane to the with-operator lane |
| up next | loop-workable — lane to the workable lane, position set by their order |
| backlog | keep, not now — unsectioned |
| dead | superseded or wrong — removed on the operator's explicit call, with the evidence; never silently |

The drift sweep runs the join's other direction — board motion with no queue line becomes proposed mints in the queue's grammar, entering only on the operator's word. And the falsifier ask fires at this threshold — framed as its own beat, never another one-word row ("before this enters Up Next: what would show we were wrong to start it?"): an outcome entering Up Next without a `--badly` gets asked for one (see Falsifier ask above).

**The two-writer write-window protocol.** A live ceremony has TWO writers on one queue: the operator dragging lines in the app while the session writes through the API — and the races are silent, because a line that lands in the wrong lane looks deliberate. Both shapes were observed on 2026-08-23: a freshly-minted line landed in the wrong lane, and a count came back off by two mid-flight; neither lost data, both cost a verification round. The protocol:

- **Batch your writes and announce the window** — "touching the queue now" before; close the window by itemising the moves, never just counting them ("bon line → workable #2 · X line ticked · Y line → with-operator"), because a count cannot surface the wrong-lane write this protocol exists to catch. Between announced windows the session does not write.
- **Never reorder after the operator's drags start — and say the gear change out loud, once.** Order is their steering wheel: the moment their hand is on it, `accomplis reorder` is off the table for the rest of the ceremony ("order's yours now — I'm down to membership moves only"), and position stays theirs. A silent mode-switch reads from their seat as the session mysteriously stopping.
- **Re-read after any overlapping window.** A count or lane listing taken while both writers were live is stale on arrival — re-fetch the lane before asserting counts or positions to him or to the record.

## Mechanics

- **No hard line-wrapping** — the operator edits this file; one line per bullet, let their editor soft-wrap.
- Draft lands at the accent's `review.draft-path` (default `/tmp/estate-pyramid-<date>.md`); the durable copy goes to the accent's `review.archive` location at Phase 5 (no accent → the run directory the survey wrote is the durable record).
- Adjudication happens in **conversational Q&A clusters** (AskUserQuestion with a recommendation first), not file-homework — the operator preference recorded at the first ceremony (2026-08-02).
- Queue writes happen only inside announced write-windows during adjudication — see Queue population above; every other surface that touches the queue stays read-only.
