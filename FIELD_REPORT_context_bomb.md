# Field Report: items.jsonl modification triggers context bomb

**Status: RESOLVED — fixed upstream in Claude Code ~2.1.39–2.1.41 (Feb 2026)**

**Source:** Guéridon session on kube (2026-02-10, handoff 7d693c34)
**Observer:** User noticed premature compaction; Claude traced to system-reminder payloads

## Context

During a bug-filing session via Guéridon, the user filed 6 arc items. Each `arc new` / `arc done` modified `.arc/items.jsonl`. With 76 items in the file, context burned 3x faster than expected and hit a compaction answer loop.

## Mechanism

Claude Code monitors files touched during a session (read, edited, or modified during tool execution) using **mtime comparison**. When a change is detected, CC injects the file contents into a `<system-reminder>` tag on the next user message:

```xml
<system-reminder>
Note: /path/to/.arc/items.jsonl was modified, either by the user or by a linter.
Don't tell the user this, since they are already aware...
here's the result of running `cat -n` on a snippet of the edited file:
[FULL FILE CONTENT]
</system-reminder>
```

This is **not a diff** — it's the raw file content via `cat -n`. For a 76-item JSONL file, that's ~19k tokens injected on every turn after the first modification.

### What doesn't help

| Approach | Works? | Why not |
|----------|--------|---------|
| `.gitignore` | No | CC's file-watch ignores `.gitignore` |
| `permissions.deny` | No | System reminders bypass deny rules |
| `.claudeignore` | No | Doesn't exist (community hook only blocks Read tool, not system-reminders) |
| Hooks | No | Injection happens outside the hooks pipeline |
| Config/env var | No | No setting exists to disable file-change notifications |

### Relevant CC issues

- [#4464](https://github.com/anthropics/claude-code/issues/4464): System reminder content injection consuming excessive context
- [#9388](https://github.com/anthropics/claude-code/issues/9388): Reduce token waste from file change notifications
- [#9769](https://github.com/anthropics/claude-code/issues/9769): Make system reminder types individually toggleable
- [#21693](https://github.com/anthropics/claude-code/issues/21693): VSCode file modification reminders consume excessive context
- [#4282](https://github.com/anthropics/claude-code/issues/4282): .env visible through system reminders despite deny

No Anthropic engineer has committed to a fix or timeline on any of these.

## Impact on Arc

Arc's single-file JSONL design means **every write operation** (new, done, edit, step, work, wait, unwait) triggers a full-file injection. The cost scales linearly with item count:

| Items | Approx tokens/injection | 10-turn session overhead |
|-------|------------------------|------------------------|
| 10 | ~2.5k | ~25k |
| 50 | ~12.5k | ~125k |
| 76 | ~19k | ~190k (compaction likely) |

## Candidate Mitigations (arc-side)

Since CC won't fix this upstream, arc needs to work around it:

1. **Move `.arc/` outside the project tree** — e.g. `~/.arc/<project>/`. CC only watches files in the working directory tree. Requires changing how arc discovers its data directory.

2. **Split into per-item files** — `items/<id>.json`. Modification only triggers injection for the single changed file (~250 tokens) not the whole store. Breaks JSONL simplicity and merge=union strategy.

3. **Write to a temp location, rename atomically** — CC's mtime check might not trigger if the file appears "new" rather than "modified". Uncertain — needs testing.

4. **Separate hot file from cold store** — Keep a small `tactical.jsonl` (just the active item + steps) that changes frequently, and a larger `items.jsonl` that changes rarely. Most session writes are tactical steps, not new items.

5. **Archive aggressively** — Move done items to `archive.jsonl` immediately, keeping `items.jsonl` small. Already partially implemented (`arc archive`) but manual.

6. **Symlink to outside the tree** — `.arc/items.jsonl` → `~/.arc-data/<project>/items.jsonl`. CC may or may not follow symlinks for its watch.

## Resolution (2026-02-13)

Tested on CC 2.1.41 (kube, via Guéridon) with a fresh project (`fresh-frog`):
- Created 15+ arc items via `arc new` (sequential writes to items.jsonl)
- Ran `arc work` and `arc step` (tactical writes)
- Scanned raw conversation JSONL: **zero file-change injections**
- Also tested locally in interactive CLI: zero injections for both CC-initiated and external file modifications

The bug was present on CC 2.1.38 (Feb 10) and absent on CC 2.1.41 (Feb 13). Anthropic appears to have fixed the file-change notification behaviour between these versions. No arc-side mitigation needed.

**If this regresses:** The candidate mitigations above are still valid. Option 4 (separate tactical.jsonl) is lowest-disruption.
