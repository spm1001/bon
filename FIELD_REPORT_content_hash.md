# Field Report: content_hash should use updated_at

**Source:** claude-mem integration (Jan 2026)
**Observer:** Claude working on mem adapter

## Context

While adding an arc adapter to claude-mem for session indexing, I noticed a subtle issue with change detection.

## Observation

The adapter uses `created_at:status` as the content_hash for detecting changes:

```python
change_key = f"{created_at_str}:{source.status}"
```

This means if someone edits an arc item (changes title, brief, etc.) without changing status, mem won't re-index it. The edit becomes invisible to search.

The beads adapter uses `updated_at` which correctly captures all changes:

```python
updated_at_str = source.updated_at.isoformat() if source.updated_at else ''
```

## Current arc item schema

Looking at `items.jsonl`:
```json
{"id": "arc-xxx", "type": "outcome", "title": "...", "brief": {...},
 "status": "done", "created_at": "...", "done_at": "..."}
```

There's no `updated_at` field currently.

## Suggestions

1. **Add `updated_at` to arc items** — Update on any field change
2. **Or: Use content hash** — Hash of title + brief fields for change detection

Option 1 is cleaner and matches beads behavior.

## Impact

This isn't critical — arc items rarely change after creation — but it's a subtle correctness issue. If someone refines an outcome's brief after initial creation, search won't reflect the update until a full re-index.

---

*Filed as field report per claude-suite conventions. Not a bug, not urgent — just knowledge transfer for future maintainers.*
