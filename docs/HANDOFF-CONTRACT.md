# Handoff Contract v7

The handoff file is an interface between sessions. This document specifies the stable contract that external consumers (e.g. aboyeur, overnight composting) can depend on.

## Location

Handoffs are resolved by a shared walk (`scripts/lib-handoff.sh`, sourced by both the reader and the writer so they cannot drift). The "visible substrate" convention: prose (handoffs/, understanding.md) lives VISIBLE at the room where work happens; the board (`.bon/items.jsonl`) stays hidden + repo-global.

Resolution order, walking up from CWD to the board root (the repo's `.bon/` dir):

1. A visible `handoffs/` at the nearest room — a room adopts the convention simply by having one — then
2. A visible `handoffs/` at the board root — the default, created on first write — then
3. `~/.bon/handoffs/` — global catch-all for a session outside any board, not git-tracked.

The **writer** picks the first that applies; the **reader** ranks the latest across all of them, so a repo holding prose at several levels surfaces the genuinely newest. A handoff is always read from exactly where it was written.

**`.bon/handoffs/` is no longer a rung** (v6, bon-sedoze). A repo still holding a pile there has it moved into the board root's visible `handoffs/` by `handoff_migrate_legacy`, which both the reader and the writer run *before* resolving — so the first `/open` or `/close` after upgrading converges the repo and then reads the migrated location. Tracked files move with `git mv` (the rename is staged); untracked ones — the wholesale-`.bon/`-ignore case — move plainly. Nothing is ever overwritten: a name collision whose content differs is kept as `<name>-legacy2.md`.

**Consumers that read handoffs directly** (aboyeur, overnight composting, gueridon) should source the resolver rather than hardcoding any of these paths. A consumer still globbing `.bon/handoffs/` will find it empty after the owning repo's first post-upgrade session.

## Discovery

Most recent handoff across all resolved locations, ranked by the header date (`# Handoff — YYYY-MM-DD`), then write time within the day (the filename's HHMM where the v4 scheme carries one, else HHMM derived from mtime), then raw mtime. Header-date ranking, not raw mtime: a fresh clone flattens every mtime to checkout time, so mtime-first would pick an arbitrary (often ancient) handoff — and the same flattening makes cross-host mtime order arbitrary within a day, which is why the filename time outranks it.

- **v4 filename scheme** (2026-08-16, notes-sovike): `YYYY-MM-DD-HHMM-{session-id-8}.md` (e.g. `2026-08-16-1913-51d17dc5.md`). The HHMM makes same-day siblings sort chronologically under a plain `ls` — the id8 is random, so under v3 a superseded same-day handoff could sort last and hand a routing session the stale frame (that happened, 2026-07-31, sky-transaction).
- **v3 filename scheme:** `YYYY-MM-DD-{session-id-8}.md` (e.g. `2026-04-04-51d17dc5.md`). Still valid — old files are never renamed; within a day they rank by mtime.
- **v2 filename scheme:** `{session-id-8}.md` (e.g. `51d17dc5.md`). Still valid — consumers must handle all three during transition.
- Consumers must not depend on filename format beyond `.md` extension.

## Ledger and the sweep (v7, bon-supuko)

Each handoffs directory may carry a `LEDGER.md`: one line per handoff, newest first, led by a processed-marker checkbox.

```markdown
- [ ] 2026-08-30 [2026-08-30-2010-fb49cab3.md](2026-08-30-2010-fb49cab3.md) — {purpose line}
```

- **The writer (/close) appends its line in the same change that writes the handoff**, creating `LEDGER.md` (with a two-line header) when absent — creating it is how a repo adopts the sweep.
- **The reader (/open) processes EVERY unticked line, oldest first** — synthesis and candidate minting are batch-safe — and ticks each: `- [x] … (processed YYYY-MM-DD)`, the generalisation of the candidates `(minted YYYY-MM-DD)` heading-edit. This replaces latest-wins, under which the older of two interleaved closes was silently dropped: never synthesised, never minted, nothing said so.
- **Fallbacks, both honest:** a line WITHOUT a checkbox is legacy prior art (~/notes' prose ledger predates this spec) and counts as processed; a handoff in no ledger at all is covered by latest-wins only — the newest still surfaces via discovery above, older unlisted files don't. Adoption is per-directory and zero-config beyond the close appending its line.
- The link target resolves relative to the ledger's own directory; absolute paths are accepted.

## File Format

### Metadata (first 5 lines)

```
---
session_id: <uuid or identifier>
purpose: <one-line summary — no ": " (colon-space), which breaks the YAML parse>
author: <OKF actor id, e.g. claude/fable-5>
items: <bon IDs worked, comma-separated>
format: fond-v2
---

# Handoff — YYYY-MM-DD
```

- `session_id` — identifies the originating session. Used for debugging and log correlation.
- `purpose` — human-readable summary.
- `items` — optional (v7, bon-jeweke): the bon IDs this session WORKED (closed, stepped, materially advanced — never merely filed, whose briefs carry their own origin). One physical line, comma-separated, full IDs. This is the baton's address — `bon work` surfaces the newest handoff citing the drawn item at draw-down, so the thread's briefing reaches its next runner rather than whoever opens next. Absent when no board items were worked, and in all pre-v7 handoffs.
- `author` — optional (v8): the writing session's OKF actor id (`claude/<model>`, `human:<id>`, `process:<id>`). Frontmatter-aware renderers (mit-kg's `kg gen ledger`) show it per line.
- `format` — template version. `fond-v1` indicates the two-zone layout below with bare metadata lines; `fond-v2` is the same layout with the metadata fenced as real YAML frontmatter. Absent in legacy handoffs.

### Two-Zone Layout (fond-v1)

Handoffs have two zones serving different audiences:

**Zone 1: For the next Claude** — consumed at session start for orientation.

| Information | Heading | Purpose |
|-------------|---------|---------|
| What was accomplished | `### Done` | Orient the next session |
| Process observations | `### Reflection` | What worked, what didn't |
| Concerns and traps | `### Risks` | Prevent repeat mistakes |
| Suggested direction | `### Opportunities` | Next steps with bon IDs |
| Verification commands | `### Commands` | Optional. Pick up where we left off |
| Board mutations to mint | `### Candidates` | Optional. A no-writer session's proposals; a writer-bearing /open mints them (see Candidate mode) |

**Zone 2: For Claudes to come** — consumed by overnight composting for synthesis into understanding.md and garde.

Single prose block under `## For Claudes to come`. Architectural knowledge that transcends the session, written to stand alone without session context.

Scripts that extract section content should grep for `## For the next Claude` and `## For Claudes to come` as zone markers. Section headings within zones are flexible — content matters, not labels.

### Candidate mode (`### Candidates`)

A session that can **see** the board but can't **reach** a writer (Cowork's mounted sandbox is the live case — files visible, no `bon` CLI, no git) runs the rite knowledge-side and records its intended board mutations in the handoff as **candidates**: provenance-tagged proposals a writer-bearing `/open` mints at the next full-fat session. This is the "visible / unreachable" quadrant of the probe in `docs/CONTRACT.md` — that document owns the probe; this one owns the block's shape.

The block lives in Zone 1 (it's consumed at the next open) and is **optional**: only no-writer sessions produce it, so existing handoffs and consumers are untouched.

```markdown
### Candidates

<!-- Board visible, writer unreachable — a writer-bearing /open mints or drops each; unminted = wish. -->
Provenance: {vehicle} session {session_id} — {YYYY-MM-DD}

- **NEW** action under `bon-PARENT` — "Title"
  - why: … / what: … / done: …   (how: … — optional)
- **DONE** `bon-xxxx` — "one-line reason"
- **EDIT** `bon-yyyy` — --how: "new text"
```

- **Provenance line** — which vehicle and session produced the candidates, and the date; the minting session carries this into each item's brief so origin survives.
- **One entry per mutation**, keyed by verb (`NEW` / `DONE` / `EDIT`), with enough detail to mint without the originating session's context.
- **Minting is part of the full-fat open, not a courtesy** — a candidate not minted at the next open is a wish. After minting, the open marks the block `### Candidates (minted YYYY-MM-DD)` so a re-open doesn't double-mint.

Two worked examples predate this spec and carry their candidates as an `### Opportunities — bon candidates` list (`~/notes/handoffs/2026-06-10-7c379a74.md`, `2026-06-12-804b6ba8.md`); readers should treat that legacy shape as candidates too.

### Legacy Layout (pre-fond)

Older handoffs use flat sections: `## Done`, `## Next`, `## Gotchas`, `## Risks`, `## Reflection`. No zone markers, no `format:` field. The full handoff is always available on disk.

### Escalation Signal

```
HUMAN REVIEW NEEDED
```

Plaintext, grep-able, anywhere in the body. Presence means the session identified something requiring human attention before the next builder proceeds.

## Roles

### Writer: Worker session (/close)

The primary handoff author. /close reflects, proposes a plan, and writes the handoff. Internal mechanics (Orient/Reflect/Act, script dependencies) are not part of this contract.

### Reviewer: Reflector (aboyeur)

Reads the worker's handoff to understand session state. Acts on the workspace — tidying, committing, flagging. Does not write a new handoff.

The reflector may add the escalation signal to the existing handoff if it identifies a concern the worker missed.

### Reader: Next session (/open or session-start hook)

Discovers the most recent handoff plus every unticked ledger line, processes them all (oldest first), ticks each. Does not know or care whether the previous session was a worker or reflector.

### Compost: Overnight processing

Reads the Compost zone (`## For Claudes to come`) and synthesizes into understanding.md and garde extractions. Marks handoffs as processed.

## What's Stable (don't break these)

- Handoff resolution via `scripts/lib-handoff.sh`: visible `handoffs/` (nearest room, then board root), `~/.bon/handoffs/` global catch-all
- Discovery by header date (newest wins), mtime breaking same-day ties
- Metadata fields: `session_id`, `purpose`
- Escalation signal: `HUMAN REVIEW NEEDED` as grep target
- File format: markdown with sections

## What's Flexible (can evolve)

- Section heading names within zones (content matters, not labels)
- Filename scheme (date-prefixed is current, UUID-based is legacy)
- Number of sections, presence of optional sections
- Prose style and detail level
- Whether `### Commands` or `### Reflection` are present
- Whether `## For Claudes to come` is present (not every session produces durable insight)
- Whether the optional `### Candidates` block is present (only no-writer sessions produce it)

## What's Out of Scope

- How /close gathers context (scripts, hooks)
- How /open finds and presents handoffs (indexing, caching, briefing format)
- Session indexing and memory extraction
- Bon or any other work tracker integration

## Versioning

This is v8.

- **v1** (Jan 2026): Initial contract. `~/.claude/handoffs/` location, flat sections.
- **v2** (Feb 2026): Path encoding widened. Still `~/.claude/handoffs/`.
- **v3** (Apr 2026): Location moved to `.bon/handoffs/` (git-tracked). Two-zone layout (fond-v1). Date-prefixed filenames. `format:` metadata field.
- **v4** (Jun 2026): Visible-substrate resolution (bon-zopopu). Handoffs resolve to a visible `handoffs/` (nearest-room, then board-root) before the legacy `.bon/handoffs/`, via the shared `scripts/lib-handoff.sh`; `understanding.md` resolves the same way. The `.bon/` fallback keeps every existing repo working untouched. **Consumers that read handoffs directly** (aboyeur, overnight composting) should use that resolver — or handle visible `handoffs/` + nearest-room — rather than assuming `.bon/handoffs/`.
- **v5** (Jul 2026): Candidate mode (bon-pujawo). An optional `### Candidates` block in Zone 1 lets a no-writer session (board visible, writer unreachable — e.g. Cowork) record board mutations for a writer-bearing `/open` to mint. Additive and optional; the handoff format stays `fond-v1`.
- **v6** (Aug 2026): `.bon/handoffs/` retired as a resolution rung (bon-sedoze). The visible `handoffs/` is now the default for a fresh board, not just an opt-in, and the reader no longer looks under `.bon/`. Because bon ships publicly, the same change carries the migration: `handoff_migrate_legacy` converges a legacy pile onto the visible dir on the back of the next open or close, so no consumer sees a session with their handoffs missing. The v4 note above is the state this supersedes — kept because a reader may still hold it.
- **v7** (Aug 2026): The ledger sweep (bon-supuko) and the baton (bon-jeweke). `LEDGER.md` per handoffs dir with `- [ ]` processed-markers; the close appends, the open sweeps ALL unticked lines and ticks them — latest-wins survives only as the fallback for un-ledgered repos. Metadata gains the optional `items:` field (the bon IDs a session worked); `bon work` surfaces the newest handoff citing the drawn item, so the thread briefing follows the ticket. Both additive: no existing file changes shape.
- **v8** (Aug 2026): fond-v2 — the metadata block gains `---` fences (real YAML frontmatter) and an optional `author:` field. Motivated by mit-kg's generated ledger (kg-gonose): a frontmatter-aware renderer reads `purpose`/`author`/`swept` as data, while every fond-v1 consumer survives unchanged because all are line-anchored — the `^purpose:` grep (open-context.sh), the `# Handoff —` date ranker, and the `items:` baton scan each match the same lines fenced or bare. Verified against all three before shipping. fond-v1 files stay valid forever; a `: ` inside a fenced value breaks that block's YAML parse, degrading that file to fond-v1 behaviour rather than erroring.
