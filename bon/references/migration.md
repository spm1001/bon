# Migrating from Beads

Migration is a two-phase process — the tool extracts structure, you write proper briefs.

## Phase 1: Generate Draft Manifest

```bash
# From exported JSONL
bon migrate --from-beads beads-export.jsonl --draft > manifest.yaml

# Or directly from .beads/ directory
bon migrate --from-beads .beads/ --draft > manifest.yaml
```

This produces a YAML manifest with:
- **Structure preserved:** epics → outcomes, tasks → actions, parent relationships
- **`_beads` context:** raw description/design/acceptance_criteria/notes for reference
- **Empty `brief` placeholders:** you must fill why/what/done

**Orphan handling options:**
```bash
# Default: orphans excluded, listed in orphans_excluded section
bon migrate --from-beads .beads/ --draft

# Promote orphans to outcomes (empty children)
bon migrate --from-beads .beads/ --draft --promote-orphans

# Assign orphans to a specific parent outcome
bon migrate --from-beads .beads/ --draft --orphan-parent proj-abc
```

**Field reports don't migrate.** Field reports (Claude-to-Claude knowledge transfer) aren't actionable work — they belong in skill docs, not a work tracker. Close them in beads rather than migrating.

## Phase 2: Complete Briefs and Import

Review `manifest.yaml`. For each item, use `_beads` context to write proper briefs:

```yaml
- id: proj-abc
  title: User Authentication
  _beads:
    description: Add OAuth to the app
    design: Use passport.js with JWT
    notes: "COMPLETED: research. NEXT: implement"
  brief:
    why: Users need secure, frictionless login    # ← Fill this
    what: OAuth2 flow with Google/GitHub options  # ← Fill this
    done: Users can login, tokens refresh correctly  # ← Fill this
```

Then import:

```bash
bon migrate --from-draft manifest.yaml
```

**Validation enforced:**
- All briefs must be complete (why/what/done non-empty)
- `.bon/` must not already exist
- `_beads` context is stripped on import

## Why This Pattern?

Beads fields don't map cleanly to bon's opinionated brief structure. Rather than auto-generating weak briefs, the manifest pattern forces you to think about each item's why/what/done — resulting in items that future Claudes can actually execute.
