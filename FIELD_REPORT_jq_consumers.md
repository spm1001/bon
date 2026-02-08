# Field Report: External jq consumers of items.jsonl

**Source:** claude-suite session hooks and scripts (Feb 2026)
**Observer:** Claude working on arc-read.sh test coverage

## Context

claude-suite reads `.arc/items.jsonl` directly with jq instead of the arc Python CLI. This avoids ~30ms Python startup per invocation, which matters for hooks that fire on every prompt. The pattern is: **Python for writes (validation, ID generation, tactical management), jq for reads (hooks, scripts, session briefing).**

This means items.jsonl has consumers outside the arc codebase that don't go through the CLI's data layer.

## Consumers

Three scripts in claude-suite read items.jsonl directly:

| Script | Purpose | Frequency |
|--------|---------|-----------|
| `scripts/arc-read.sh` | `list`, `ready`, `current` commands for session briefing | Once per session start |
| `hooks/arc-tactical.sh` | Inject current tactical step into every prompt | Every user prompt |
| `scripts/open-context.sh` | Look up parent outcome for zoom display | Once per session start |

## Fields Read

| Field | Used by | How |
|-------|---------|-----|
| `.id` | all three | Display, parent lookup, children grouping key |
| `.type` | arc-read.sh (list, ready) | Filter: `select(.type == "outcome")` |
| `.title` | all three | Display |
| `.status` | all three | Filter: `select(.status == "open")`, done/open markers |
| `.parent` | arc-read.sh (list, ready), open-context.sh | Group children by parent, filter top-level outcomes |
| `.order` | arc-read.sh (list, ready) | `sort_by(.order)`, display numbering |
| `.waiting_for` | arc-read.sh (ready) | Filter: exclude items with non-null/non-empty waiting_for |
| `.tactical` | arc-read.sh (current), arc-tactical.sh | Presence check, `.tactical.steps[]`, `.tactical.current` |

**Not read:** `.brief`, `.created_at`, `.created_by`, `.done_at`

## What Would Break

If any of these fields change shape, the jq queries silently produce wrong output:

| Change | Impact |
|--------|--------|
| Rename `.status` values (e.g. "open" → "active") | Everything — filter matches nothing, empty output |
| Rename `.parent` to `.parent_id` | list/ready lose hierarchy, show flat outcomes only |
| Change `.tactical.steps` from array to object | current command produces jq error, suppressed by `|| true` |
| Add new status values (e.g. "archived") | Harmless — queries filter for "open"/"done" explicitly |
| Add new fields | Harmless — jq ignores unknown fields |

## Tested

claude-suite now has 34 pytest tests covering arc-read.sh edge cases (empty JSONL, all-done items, malformed input, no .arc/, tactical steps, waiting_for filtering). These tests use fixture data, not live arc CLI comparison, so they'd catch jq query regressions but not schema drift.

## Proposal

**Option A: Schema version field.** Add `"schema_version": 1` to `.arc/config.json` (or as a header line in items.jsonl). Consumers check version before querying. Breaking changes bump version.

**Option B: Document stable fields.** Add a section to SPEC.md listing fields that external consumers may rely on. Changes to these fields require a migration note.

**Option C: Do nothing.** The field set is small, the consumer base is one repo, and the test suite in claude-suite would catch regressions during development. The risk is low enough that documenting the dependency (this report) is sufficient.

**Recommendation: Option C for now, with this report as the documentation.** The consumer base is just claude-suite, the fields are core to arc's data model (unlikely to change names), and the test suite provides a safety net. If arc gains more external consumers, revisit with Option B.
