# Handoff Contract v3

The handoff file is an interface between sessions. This document specifies the stable contract that external consumers (e.g. aboyeur, overnight composting) can depend on.

## Location

Handoffs live per-repo in `.bon/handoffs/`, git-tracked. The close-context script walks up from CWD to find the nearest `.bon/` directory.

```
.bon/handoffs/
```

Fallback for sessions without a `.bon/`: `~/.bon/handoffs/` (global catch-all, not git-tracked).

## Discovery

Most recent file by modification time in the project's handoff directory.

```bash
ls -t .bon/handoffs/ | head -1
```

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

- Handoff directory: `.bon/handoffs/` per-repo
- Discovery by mtime (newest wins)
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

This is v3.

- **v1** (Jan 2026): Initial contract. `~/.claude/handoffs/` location, flat sections.
- **v2** (Feb 2026): Path encoding widened. Still `~/.claude/handoffs/`.
- **v3** (Apr 2026): Location moved to `.bon/handoffs/` (git-tracked). Two-zone layout (fond-v1). Date-prefixed filenames. `format:` metadata field.
