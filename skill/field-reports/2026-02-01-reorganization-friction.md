# Field Report: Arc Reorganization Friction

**Date:** 2026-02-01
**Context:** Reorganizing mise-en-space arc items — 15 outcomes needed to become actions with parents
**Claude:** Opus 4.5

## The Task

19 outcomes in `.arc/items.jsonl`, but 15 were actually actions masquerading as outcomes — created without `--for` when they should have had parents. Needed to:
1. Reparent 4 existing actions from one outcome to another
2. Close a milestone outcome
3. Convert 14 outcomes → actions under correct parents

## What Went Wrong First

My first instinct was to edit `items.jsonl` directly — change `"type": "outcome"` to `"type": "action"` and add `"parent": "..."`. The user rightly stopped me: **bypassing the CLI bypasses the tool's invariants**.

## The Correct Workflow (Discovered)

```bash
# For existing actions: --parent works
arc edit mise-lft --parent mise-jy3  ✓

# For misclassified outcomes: archive and recreate
arc done mise-PepuZa                 # Archive the mistake
arc new "Wire pre-exfil..." --for mise-4mj  # Recreate correctly
```

This required 14× `arc done` + 14× `arc new` — verbose but semantically correct.

## Friction Points

### 1. `--parent` vs `--for` inconsistency

| Command | Flag for parent |
|---------|-----------------|
| `arc new` | `--for PARENT` |
| `arc edit` | `--parent PARENT` |

I used `--parent` on `arc new` and got `unrecognized arguments`. Then checked help. The vocabulary should be consistent — either both use `--for` or both use `--parent`.

**Suggestion:** Unify on one term. `--for` is more semantic ("this action is *for* that outcome"), but `--parent` is more universal.

### 2. Outcome/action type is birth-immutable

Once an item is born as an outcome, it cannot become an action. The only path is archive + recreate. This loses:
- Creation timestamp
- Original ID (breaks external references)
- History

**Suggestion:** Add `arc convert`:
```bash
arc convert mise-PepuZa --to action --for mise-4mj
```
Would change type and set parent atomically. Could warn: "This changes the item's role. Proceed?"

### 3. `arc done` is semantically overloaded

`arc done` means both:
- "This work is complete" (success)
- "This was a mistake, archive it" (cleanup)

These feel different. The 14 outcomes I archived weren't *done* — they were *misclassified*.

**Suggestion:** Consider `arc archive` or `arc close` for the "remove from view but preserve" case. Or accept this is fine — GTD doesn't distinguish either.

### 4. No bulk operations

Reorganizing 14 items required 28 commands. Tedious, error-prone, context-expensive.

**Suggestion:** Consider bulk variants:
```bash
# Bulk reparent
arc edit mise-PepuZa mise-Lovobo mise-lodipa --parent mise-4mj

# Bulk done
arc done mise-PepuZa mise-Lovobo mise-lodipa

# Or a reorganize subcommand
arc reorg --from-file reorganization.yaml
```

### 5. Implicit outcome vs action creation (actually good)

`arc new "title"` → outcome
`arc new "title" --for parent` → action

This is elegant! The presence of `--for` determines type. No explicit `--type` flag needed. But it's non-obvious to a Claude encountering arc for the first time. I had to check `arc new --help` to discover this.

**Suggestion:** The SKILL.md could highlight this pattern more prominently in examples.

## What Worked Well

- **`arc edit --parent`** for existing actions was smooth
- **`arc done`** accepts multiple IDs via `&&` chaining
- **`arc list`** output is clean and shows hierarchy clearly
- **Brief fields (`--why`, `--what`, `--done`)** encourage good practices

## Token Cost

This reorganization took ~40 commands across restore → verify → archive → recreate → verify. A `arc convert` command would have reduced this to ~15 commands (just the conversions).

## Recommendation Priority

1. **`arc convert`** — highest value, enables fixing misclassifications without losing metadata
2. **Consistent `--for`/`--parent`** — low effort, reduces friction
3. **Bulk operations** — moderate effort, significant Claude ergonomics improvement

---

*Filed from mise-en-space reorganization session*
