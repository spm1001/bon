# Todoist as a shared work-substrate — anatomy & decision record

**Date:** 2026-06-17
**Purpose:** Decide whether bon and Todoist should converge into one work-substrate shared by Sameer (+ human team) and Claude (+ future autonomous team), and if so, which way the graft runs. Triggered by the recurring pain: Claude files bon items that are *also* Todoist items, then asks if they're done — but the two of us aren't looking at the same system.

Relates to: `bon-kepuko` (docket/rite split), `bon-welogi` (web MCP), `bon-kuwivo` (GUI face).

## The fork

- **Option A — bon is the store of record; Todoist (and/or kuwivo) is a face.** bon's atom is designed for agents; Dolt is already the shared backend. Human needs (context, mobile, capture) become *projections*. Cost: Sameer must leap into bon's opinionated atom and give up Todoist as primary; we build kuwivo + a projection.
- **Option B — Todoist is the store of record; Claude gets an *opinionated MCP* that grafts on the discipline.** One store, no sync, Sameer's "air" untouched. bon-discipline (done-contract, parent link, dependencies) becomes a *protocol enforced at the tool boundary*, validated on read. Cost: the store can't enforce; two fields have no native home.
- The mushy middle (two peer stores synced, or Todoist as a thin one-way face) is rejected: it carries both costs and neither's cleanliness, and two-way sync between mismatched mandatory-field atoms loses information every round-trip.

## The two atoms

| Dimension | bon | Todoist |
|---|---|---|
| Unit | Outcome / Action | Task (+ Goal, new) |
| `why` | mandatory | optional `description` |
| **`done` (completion contract)** | **mandatory** | **none — boolean checkbox only** |
| Outcome→Action link | stored (`parent`) | **Goals + `link-goal-tasks` (now first-class)** |
| **Dependencies** | `waiting_for` + auto-unblock | **none — confirmed absent from API & MCP** |
| Context | none | project / label |
| Owner | session identity | assignee + Goal `responsibleUid` |
| Discipline | CLI **refuses** bad atom | free-form; enforced only by a wrapping tool |

A bon item is a **specification**; a Todoist task is a **reminder**.

## Field-by-field mapping (Option B)

| bon field | Todoist home | Native / encoded | Enforced |
|---|---|---|---|
| Outcome | Goal (name, description, deadline, `responsibleUid`) | native ✅ | store |
| Outcome→Action link | `link-goal-tasks` | native ✅ | store |
| Action | Task (content, description, labels, parentId, due, deadlineDate, assignee) | native | store |
| `why`/`what` | description (Markdown) | encoded convention | tool only |
| **`done`** | description section + `@spec` label | **encoded — no native field** ⚠️ | tool only |
| **`waiting_for`/dependency** | `blocked-by:<id>` label + unblock computed in tool | **fully synthetic** ⚠️⚠️ | tool only, invisible in Todoist UI |
| status done | complete/uncomplete | native | store |
| context | project or label | native | (human assigns) |
| owner | Goal `responsibleUid` / assignee | native ✅ | store |
| provenance (candidate/minted) | label | encoded | tool |

## The two structural holes (the whole risk)

1. **No definition-of-done field.** The verifiability needed for autonomous pickup lives in a description convention + label, policed by the tool's read-validation — never guaranteed by the store.
2. **No dependency primitive (confirmed from source).** `waiting_for`/unblock-on-done is entirely synthetic: a label graph the tool computes, **invisible in Todoist's own views**. The human can't see "what's blocked" in the tool they live in.

Because the store can't refuse a malformed atom (a phone edit, the Todoist UI, another integration can all write loose tasks), Option B *requires* the opinionated tool to **validate-on-read and quarantine** non-conforming atoms — the agent only ever acts on tool-blessed items.

## What `todoist-gtd` proves — and its gap

Proves the **architecture**: a thin Python CLI over the official `todoist_api_python` SDK + token in Keychain + a coaching skill. That's exactly the shape an opinionated bon-interface takes, and it works today. **Wrong atom for bon**, though: it maps outcome → *section* (the old hack, link not stored — `add-section` help literally says "(outcome)"), has no done-contract, no dependencies, and its discipline is **coached in the skill, not enforced in the CLI**. No goal verbs (predates Goals).

## Attractive build path

`Doist/todoist-ai` (the official MCP) is **open source and already has a `src/middleware/` layer**. So the "opinionated MCP" could be a *fork* injecting bon-discipline middleware (refuse-without-done, dependency resolver, read-validation/quarantine) over the real tools — smaller than a from-scratch wrapper.

## Lean (2026-06-17)

**B, staged — with named kill-criteria.** B kills *today's* actual pain immediately (one store, no double-filing, Sameer's air intact, team ownership free via Goals), and "discipline injected at agent-handoff, not on everything" is the *correct* shape for a shared human+agent world, not just cheaper. The two holes only become decisive at the **autonomous-overnight** horizon — and the asymmetry is the decider: **the human (in the loop) is forgiving; the 3am autonomous Claude is not.** Today the agent is Claude-in-session with Sameer present, so validate-on-read is plenty.

**What would flip to A:** if the dependency graph being invisible in Todoist makes "what's ready / what's blocked" unanswerable in the tool Sameer lives in; or loose human tasks and spec-grade agent atoms can't comfortably share one list; or the unattended-overnight need arrives and `done`-as-convention proves too risky.

The spike's job is to feel exactly those holes before committing.

## Open gaps (pressure-test before committing)

- Per-account Goals limit (help article: 10 personal / 50 team — unconfirmed in source, may have moved).
- Can a task link to multiple Goals?
- `description` reliability for structured multi-line content (max length?).
- API rate limits for overnight autonomous use.

## Sources

- Official MCP source: `github.com/Doist/todoist-ai` (`src/tools/*.ts` — task schema in `add-tasks.ts`, goal schema in `add-goals.ts`, link in `link-goal-tasks.ts`; no dependency primitive found by grep).
- Todoist Goals beta: https://www.todoist.com/help/articles/goals-beta-connect-your-tasks-to-what-actually-matters-may-14-x0RWRaKDS
- Todoist + Claude Code CLI/MCP: https://www.todoist.com/help/articles/use-todoist-with-claude-code-cli-and-mcp-b1USJ4HB3
- Our proof: `~/repos/spm1001/todoist-gtd` (SDK-based CLI + coaching skill; outcome=section hack).
