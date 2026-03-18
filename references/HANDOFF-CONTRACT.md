# Handoff Contract v2

The handoff file is an interface between sessions. This document specifies the stable contract that external consumers (e.g. aboyeur) can depend on.

## Location

```
~/.claude/handoffs/<encoded-path>/
```

Each project gets a subdirectory. The encoded path is derived from the project's absolute working directory.

## Path Encoding

```bash
pwd -P | sed 's/[^a-zA-Z0-9-]/-/g'
```

- `/Users/modha/Repos/trousse` → `-Users-modha-Repos-trousse`
- `/Users/modha/.claude` → `-Users-modha--claude`
- Google Drive paths: `@`, spaces, `~` all become `-`
- Leading dash is significant (from the leading `/`)
- Matches Claude Code's own encoding for `~/.claude/projects/`

**v2 change (Feb 2026):** Encoding widened from `tr '/.' '-'` (v1, replaced only `/` and `.`) to `sed 's/[^a-zA-Z0-9-]/-/g'` (v2, replaces everything non-alphanumeric). Existing directories migrated in place. v1 and v2 produce identical results for `~/Repos/*` paths (no special characters beyond `/`).

Canonical implementation: `bon/scripts/open-context.sh`

## Discovery

Most recent file by modification time in the project's handoff directory.

```bash
ls -t ~/.claude/handoffs/<encoded-path>/ | head -1
```

- Filename scheme is not part of the contract. Currently UUID-based (e.g. `b4db9cba.md`), but any `.md` file works.
- Consumers must not depend on filename format, only recency.

## File Format

### Metadata (first 5 lines)

```
# Handoff — YYYY-MM-DD

session_id: <uuid or identifier>
purpose: <one-line summary>
```

- `session_id` — identifies the originating session. Used for debugging and log correlation.
- `purpose` — human-readable summary. Used by the handoff index for at-a-glance scanning.

### Sections

Handoff content is organised in markdown sections. These are read by Claudes, not by scripts. The content matters; the exact headings are flexible.

Expected information (under whatever headings convey it):

| Information | Typical heading | Purpose |
|-------------|----------------|---------|
| What was accomplished | `## Done` | Orient the next session |
| What should happen next | `## Next` | Suggest trajectory |
| Surprises and traps | `## Gotchas` | Prevent repeat mistakes |
| Unresolved concerns | `## Risks` | Flag things that might bite |
| Session learnings | `## Reflection` | Optional. Captures what both sides observed |

Scripts that extract section content (e.g. open-context.sh's briefing) grep for `## Done`, `## Next`, `## Gotchas`. If heading names drift, extraction degrades gracefully — the full handoff is always available on disk.

### Escalation Signal

```
HUMAN REVIEW NEEDED
```

Plaintext, grep-able, anywhere in the body. Presence means the session identified something requiring human attention before the next builder proceeds.

No structured vocabulary beyond this. If a consumer needs richer signals in future, it proposes an extension to this contract rather than inventing a parallel format.

## Roles

### Writer: Worker session (/close)

The primary handoff author. /close gathers context, reflects, and writes the handoff. Internal mechanics (GODAR ritual, hook chain, script dependencies) are not part of this contract.

### Reviewer: Reflector (aboyeur)

Reads the worker's handoff to understand session state. Acts on the workspace — tidying, committing, flagging. Does not write a new handoff. The cobbler's elves: they prepare the work, they don't leave a note.

The reflector may add the escalation signal to the existing handoff if it identifies a concern the worker missed.

### Reader: Next session (/open or session-start hook)

Discovers the most recent handoff, reads it, orients. Does not know or care whether the previous session was a worker or reflector — the handoff is the handoff.

## What's Stable (don't break these)

- Handoff directory location and path encoding
- Discovery by mtime (newest wins)
- Metadata fields: `session_id`, `purpose`
- Escalation signal: `HUMAN REVIEW NEEDED` as grep target
- File format: markdown with sections

## What's Flexible (can evolve)

- Section heading names (content matters, not labels)
- Filename scheme
- Number of sections, presence of optional sections
- Prose style and detail level
- Whether `## Reflection` is present

## What's Out of Scope

- How /close gathers context (scripts, hooks, GODAR)
- How /open finds and presents handoffs (indexing, caching, briefing format)
- Session indexing and memory extraction
- Bon or any other work tracker integration

## Versioning

This is v1. If the contract needs breaking changes:

1. Update this document with a new version number
2. Coordinate with all known consumers (currently: aboyeur)
3. Provide migration path for existing handoffs if location/encoding changes
