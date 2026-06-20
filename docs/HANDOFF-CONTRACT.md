# Handoff Contract v4

The handoff file is an interface between sessions. This document specifies the stable contract that external consumers (e.g. aboyeur, overnight composting) can depend on.

## Location

Handoffs are resolved by a shared walk (`scripts/lib-handoff.sh`, sourced by both the reader and the writer so they cannot drift). The "visible substrate" convention: prose (handoffs/, understanding.md) lives VISIBLE at the room where work happens, with `.bon/` as the legacy fallback; the board (`.bon/items.jsonl`) stays hidden + repo-global.

Resolution order, walking up from CWD to the board root (the repo's `.bon/` dir):

1. A visible `handoffs/` at the nearest room — a room adopts the convention simply by having one — then
2. A visible `handoffs/` at the board root, then
3. `.bon/handoffs/` at the board root — the legacy default; fresh repos still write here — then
4. `~/.bon/handoffs/` — global catch-all, not git-tracked.

The **writer** picks the first that applies (visible-first); the **reader** ranks the latest across all of them, so a migration-in-progress repo (both populated) surfaces the genuinely newest. A handoff is always read from exactly where it was written.

## Discovery

Most recent handoff across all resolved locations, ranked by the header date (`# Handoff — YYYY-MM-DD`) with mtime breaking same-day ties. Header-date ranking, not raw mtime: a fresh clone flattens every mtime to checkout time, so mtime-first would pick an arbitrary (often ancient) handoff.

- **v3 filename scheme:** `YYYY-MM-DD-{session-id-8}.md` (e.g. `2026-04-04-51d17dc5.md`). Date-prefixed for chronological sorting; session ID suffix links to the JSONL transcript.
- **v2 filename scheme:** `{session-id-8}.md` (e.g. `51d17dc5.md`). Still valid — consumers must handle both during transition.
- Consumers must not depend on filename format beyond `.md` extension.

## File Format

### Metadata (first 5 lines)

```
# Handoff — YYYY-MM-DD

session_id: <uuid or identifier>
purpose: <one-line summary>
format: fond-v1
```

- `session_id` — identifies the originating session. Used for debugging and log correlation.
- `purpose` — human-readable summary.
- `format` — template version. `fond-v1` indicates the two-zone layout below. Absent in legacy handoffs.

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

**Zone 2: For Claudes to come** — consumed by overnight composting for synthesis into understanding.md and garde.

Single prose block under `## For Claudes to come`. Architectural knowledge that transcends the session, written to stand alone without session context.

Scripts that extract section content should grep for `## For the next Claude` and `## For Claudes to come` as zone markers. Section headings within zones are flexible — content matters, not labels.

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

Discovers the most recent handoff, reads it, orients. Does not know or care whether the previous session was a worker or reflector.

### Compost: Overnight processing

Reads the Compost zone (`## For Claudes to come`) and synthesizes into understanding.md and garde extractions. Marks handoffs as processed.

## What's Stable (don't break these)

- Handoff resolution via `scripts/lib-handoff.sh`: visible `handoffs/` (room/root) preferred, `.bon/handoffs/` legacy fallback, `~/.bon/handoffs/` global catch-all
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

## What's Out of Scope

- How /close gathers context (scripts, hooks)
- How /open finds and presents handoffs (indexing, caching, briefing format)
- Session indexing and memory extraction
- Bon or any other work tracker integration

## Versioning

This is v4.

- **v1** (Jan 2026): Initial contract. `~/.claude/handoffs/` location, flat sections.
- **v2** (Feb 2026): Path encoding widened. Still `~/.claude/handoffs/`.
- **v3** (Apr 2026): Location moved to `.bon/handoffs/` (git-tracked). Two-zone layout (fond-v1). Date-prefixed filenames. `format:` metadata field.
- **v4** (Jun 2026): Visible-substrate resolution (bon-zopopu). Handoffs resolve to a visible `handoffs/` (nearest-room, then board-root) before the legacy `.bon/handoffs/`, via the shared `scripts/lib-handoff.sh`; `understanding.md` resolves the same way. The `.bon/` fallback keeps every existing repo working untouched. **Consumers that read handoffs directly** (aboyeur, overnight composting) should use that resolver — or handle visible `handoffs/` + nearest-room — rather than assuming `.bon/handoffs/`.
