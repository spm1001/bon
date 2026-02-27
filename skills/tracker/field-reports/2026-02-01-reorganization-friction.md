# Field Report: Bon Reorganization Friction

**Date:** 2026-02-01
**Context:** Reorganizing mise-en-space bon items — 15 outcomes needed to become actions with parents
**Claude:** Opus 4.5

## The Task

19 outcomes in `.bon/items.jsonl`, but 15 were actually actions masquerading as outcomes — created without `--for` when they should have had parents. Needed to:
1. Reparent 4 existing actions from one outcome to another
2. Close a milestone outcome
3. Convert 14 outcomes → actions under correct parents

## What Went Wrong First

My first instinct was to edit `items.jsonl` directly — change `"type": "outcome"` to `"type": "action"` and add `"parent": "..."`. The user rightly stopped me: **bypassing the CLI bypasses the tool's invariants**.

## The Correct Workflow (Discovered)

```bash
# For existing actions: --parent works
bon edit mise-lft --parent mise-jy3  ✓

# For misclassified outcomes: archive and recreate
bon done mise-PepuZa                 # Archive the mistake
bon new "Wire pre-exfil..." --for mise-4mj  # Recreate correctly
```

This required 14× `bon done` + 14× `bon new` — verbose but semantically correct.

## Friction Points

### 1. `--parent` vs `--for` inconsistency

| Command | Flag for parent |
|---------|-----------------|
| `bon new` | `--for PARENT` |
| `bon edit` | `--parent PARENT` |

I used `--parent` on `bon new` and got `unrecognized arguments`. Then checked help. The vocabulary should be consistent — either both use `--for` or both use `--parent`.

**Suggestion:** Unify on one term. `--for` is more semantic ("this action is *for* that outcome"), but `--parent` is more universal.

### 2. Outcome/action type is birth-immutable

Once an item is born as an outcome, it cannot become an action. The only path is archive + recreate. This loses:
- Creation timestamp
- Original ID (breaks external references)
- History

**Suggestion:** Add `bon convert`:
```bash
bon convert mise-PepuZa --to action --for mise-4mj
```
Would change type and set parent atomically. Could warn: "This changes the item's role. Proceed?"

### 3. `bon done` is semantically overloaded

`bon done` means both:
- "This work is complete" (success)
- "This was a mistake, archive it" (cleanup)

These feel different. The 14 outcomes I archived weren't *done* — they were *misclassified*.

**Suggestion:** Consider `bon archive` or `bon close` for the "remove from view but preserve" case. Or accept this is fine — GTD doesn't distinguish either.

### 4. No bulk operations

Reorganizing 14 items required 28 commands. Tedious, error-prone, context-expensive.

**Suggestion:** Consider bulk variants:
```bash
# Bulk reparent
bon edit mise-PepuZa mise-Lovobo mise-lodipa --parent mise-4mj

# Bulk done
bon done mise-PepuZa mise-Lovobo mise-lodipa

# Or a reorganize subcommand
bon reorg --from-file reorganization.yaml
```

### 5. Implicit outcome vs action creation (actually good)

`bon new "title"` → outcome
`bon new "title" --for parent` → action

This is elegant! The presence of `--for` determines type. No explicit `--type` flag needed. But it's non-obvious to a Claude encountering bon for the first time. I had to check `bon new --help` to discover this.

**Suggestion:** The SKILL.md could highlight this pattern more prominently in examples.

## What Worked Well

- **`bon edit --parent`** for existing actions was smooth
- **`bon done`** accepts multiple IDs via `&&` chaining
- **`bon list`** output is clean and shows hierarchy clearly
- **Brief fields (`--why`, `--what`, `--done`)** encourage good practices

## Token Cost

This reorganization took ~40 commands across restore → verify → archive → recreate → verify. A `bon convert` command would have reduced this to ~15 commands (just the conversions).

## Recommendation Priority

1. **`bon convert`** — highest value, enables fixing misclassifications without losing metadata
2. **Consistent `--for`/`--parent`** — low effort, reduces friction
3. **Bulk operations** — moderate effort, significant Claude ergonomics improvement

---

*Filed from mise-en-space reorganization session*
