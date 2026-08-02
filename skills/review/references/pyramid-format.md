# Pyramid Format — the review's opening view

Format settled by Sameer's own hand-edit of the 2026-08-01 pyramid. The canonical exemplar pair: `~/scratch/estate-pyramid-2026-08-01.md` (his edited copy — the desire-truth) and `~/notes/raw/claude/bon-audit-2026-08-01/pyramid-final-snapshot.md` (the archived snapshot). When they differ, his scratch edits are the freshest desire data — diff before regenerating, fold his lines back in, never overwrite them.

**The draft-and-edit loop is load-bearing.** The skill generates a DRAFT; Sameer's edit pass adds desire-knowledge no board holds (the 2026-08-01 run added "handed to Flore Data", "models unstable", "launcher work" — none of it on any board). Treat his edited lines as data, not formatting.

## Document shape

```markdown
# Bon Review

As of <date> — ~N significant Desired Outcomes (M open in all) across K boards

## Cross-cutting Work
✅ Recent Progress:  (2–3 multi-repo achievement lines)
🚧 Desired Outcomes (top 4 — Sameer's ranking, <date>)
1. <repo>: <desire in one line>          ← ranked, each with a next action in reach

## 🧠 Knowledge Work
(mermaid stockpot loop — see below)
✅ Recent Progress:
- <Repo>: <one human-grain line>
🚧 Desired Outcomes
- <Repo>: <one line per significant DO>
Small/dormant:
- <repo> (n), <repo> (n)                 ← the tail is named, never silently dropped

## 📺 MIT / ITV delivery
… same two-list shape per group …

## 🅿️ Parked / Someday
- <board or outcome>: <why parked> — revisit <condition>
```

## Jobs-group display mapping

The survey emits `job` slugs (from Dolt `repos.job` via `bon register --job`, or a JSONL board's `.bon/job` marker). Render them as:

| slug | header |
|------|--------|
| `knowledge-work` | 🧠 Knowledge Work |
| `mit-delivery` | 📺 MIT / ITV delivery |
| `batterie` | 🔪 Batterie — the kitchen itself |
| `estate-infra` | 🏠 Estate & infrastructure |
| `apps-research` | 🔬 Apps & research |

Boards in `jobs_unassigned` get a one-line "Unassigned — where do these live?" list at the bottom of the pyramid; agree placement with Sameer, then persist it (`bon register --job <slug>` from the clone for Dolt boards; write `.bon/job` for JSONL boards). Never guess a group silently.

## Line grain

One line per repo, plain English at human grain: "mit-plongeur: Handed over to Flore Data", not item IDs or counts. Derive Recent Progress lines from `recent_dones` (titles + done_notes) and `git.last_commit`, compressed by judgment — pick what a Monday-morning Sameer would want to know, drop the plumbing. Desired Outcomes lines come from open outcomes at their own wording, tightened. Headline counts are **Desired Outcomes, not items** — an item count is workshop trivia; a DO count is a commitment count.

**Parked items are excluded from the headline DO count** (a parked project's outcomes aren't open commitments). Parking is first-class since suite 1.30.0: the survey's `someday` field on an item carries its revisit condition, and the Parked/Someday section renders from it — each line shows the condition, and the review's Someday re-check pass (SKILL.md Phase 3) fires conditions that have come true. Boards parked only in prose (the previous pyramid's hand-curated list) get carried forward once more and converted to real `bon someday` flags as they're confirmed.

## Stockpot loop (Knowledge Work only)

Embed the loop map as a small mermaid flowchart with per-stage health (🟢🟡🔴) and a one-line caption. Canonical map: `~/notes/practices/stockpot-map.html`. Health = whether each stage's output actually feeds the next, judged from the survey's motion data (recent dones + git), not asserted from memory.

## Alignment block (the Toolmaking reconciliation seam)

The pyramid gains a `## 🤝 Toolmaking alignment` section: **Sameer's Todoist & Toolmaking DOs as headings, the bon outcomes serving each grouped under them.** The foreign key lives on the many side — bon points at his grain; render the join, never sync (his tracker holds what he's committed to; bon holds what the workshop is doing about it).

Fetch his & Toolmaking project via the accomplis tooling — invoke the `accomplis:coaching` skill first for structure discovery and semantics. If Todoist is unreachable, render the pyramid **without** the block and say so — a silently missing section reads as "nothing to align".

The block's product is the two orphan lists — they ARE the reconciliation:

- **Workshop motion with no Sameer-DO** → drift, or an uncaptured commitment he should adopt.
- **Sameer-DO with no workshop motion** → desire stalling invisibly; file a bon vessel or park it consciously.

## Dispatch queue proposal

The apex top-N renders as ready-to-adopt dispatch lines in Sameer's settled grammar:

```
Open <repo> → <desire fragment> (<bon-id>)
```

The review **proposes** these lines; Sameer adopts them into Todoist by hand. Expect the previous week's lines to carry stale bon-ids (items close mid-week) — refreshing them is part of the ceremony, not an error.

## Mechanics

- **No hard line-wrapping** — Sameer edits this file; one line per bullet, let his editor soft-wrap.
- Draft lands in `~/scratch/estate-pyramid-<date>.md`; the durable copy goes to the audit archive (`~/notes/raw/claude/bon-audit-<date>/`) at Phase 5.
- Adjudication happens in **conversational Q&A clusters** (AskUserQuestion with a recommendation first), not file-homework — his stated preference from the first ceremony (2026-08-02).
