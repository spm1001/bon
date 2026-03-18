---
name: audit
description: Orchestrates periodic cross-repo backlog review using 5-phase survey-verify-summarize-act-snapshot workflow that prevents closing items without codebase verification. Scans open bon items across all repos, dispatches parallel subagents to verify briefs against actual code, classifies as done/stale/active/blocked, and presents triage summary for user approval before closing. MANDATORY for backlog review sessions. Invoke on '/audit', 'audit my bons', 'backlog review', 'what needs closing', 'what's stale', 'clean up bons', 'triage my backlog'. Requires bon skill loaded first. (user)
---

# Audit

Cross-repo backlog review encoded as a repeatable 5-phase workflow. Replaces the manual process of scanning repos, reading briefs, checking codebase state, and deciding what to close.

**Core principle: Verify against code, not briefs.** A brief says what was planned. The codebase says what happened. Always check.

## When to Use

- Monthly or fortnightly backlog review (GTD review cadence)
- After a burst of work across multiple repos
- When bon item count is growing and needs pruning
- When starting a new focus period — shed stale commitments first

## When NOT to Use

- Single-repo triage — just read `bon list` directly
- Active session work — use bon draw-down instead
- First encounter with a repo's items — read briefs with `bon show` first

## Prerequisites

- **Bon skill must be loaded** — audit uses `bon done` for closures
- **`uv` in PATH** — audit_survey.py runs via `uv run --script`

## Workflow: 5 Phases

### Phase 1: Survey (Gather)

Run the audit survey to get structured data on all open items:

```bash
uv run --script ~/.claude/skills/audit/scripts/audit_survey.py
```

Or filter to specific repos:

```bash
uv run --script ~/.claude/skills/audit/scripts/audit_survey.py --repos trousse passe gueridon
```

**Output:** JSON with full briefs, created_at timestamps, and age flags (`old` = 30d+, `very_old` = 60d+).

**Present the landscape to the user:**

> Scanned {N} open items across {M} repos.
> Top repos: {repo1} ({count}), {repo2} ({count}), ...
> {X} items flagged as old (30d+), {Y} as very old (60d+).
>
> Which repos should I audit? (default: all with open items)

**STOP here.** Wait for user to confirm scope before proceeding.

### Phase 2: Verify (the hard part)

For each repo in scope, dispatch a **read-only subagent** (Task tool, Opus) to verify items against the actual codebase.

**Parallelism strategy:**
- Repos with <5 open items: batch up to 3 repos per subagent
- Repos with 5+ items: one subagent per repo
- Max 5 concurrent subagents

**Subagent prompt template:**

```
You are auditing bon items in the repo at {repo_path}.

For each item below, verify whether the work described has been done,
is stale (references things that no longer exist), or is still active.

Verification methods — check these in order:
1. File/path existence: do referenced files still exist?
2. Code grep: are referenced functions/classes/patterns present?
3. Git log: any related commits since {created_at}?
4. Done criteria: can you verify the --done conditions are met?

See references/verification-patterns.md for detailed patterns.

Classify each item:
- DONE: --done criteria verifiably met
- STALE: brief references things that no longer exist or codebase has diverged
- ACTIVE: brief is current, work not yet done
- BLOCKED: has waiting_for set or depends on external factor
- UNCLEAR: cannot determine programmatically, needs human judgment

Items to verify:
{json_items}

Return a JSON array:
[
  {{
    "id": "bon-xyz",
    "title": "item title",
    "classification": "DONE|STALE|ACTIVE|BLOCKED|UNCLEAR",
    "reasoning": "one line explanation",
    "evidence": "what you checked that led to this conclusion"
  }}
]

IMPORTANT: You are READ-ONLY. Do not modify any files or run bon commands.
```

**Critical constraint:** Subagents verify and classify only. All mutations happen in Phase 4.

### Phase 3: Summarize (Orient)

Collect subagent results and present a clear, actionable summary. **Output as text in your response, not via Bash** (Bash output collapses behind Ctrl+O).

Format:

```
## Audit Summary — {date}

Scanned {N} open items across {M} repos.

### Ready to Close ({count})

| Repo | Item | Title | Reasoning |
|------|------|-------|-----------|
| ... | ... | ... | ... |

### Stale — Brief Outdated ({count})

| Repo | Item | Title | Reasoning |
|------|------|-------|-----------|
| ... | ... | ... | ... |

### Active — Still Relevant ({count})

| Repo | Item | Title |
|------|------|-------|
| ... | ... | ... |

### Blocked ({count})

| Repo | Item | Title | Waiting For |
|------|------|-------|-------------|
| ... | ... | ... | ... |

### Unclear — Needs Human ({count})

| Repo | Item | Title | Question |
|------|------|-------|----------|
| ... | ... | ... | ... |

Which items should I close? (Say "close all ready", name specific IDs,
or move items between categories.)
```

**STOP here.** This is a hard gate — no action without user approval.

### Phase 4: Act (Triage)

Execute the user's decisions:

**For items approved for closure:**
```bash
cd {repo_path}
bon done {id}
```

**Commit strategy:** After all closures in a repo:
```bash
cd {repo_path}
git add .bon/items.jsonl
git commit -m "bon: audit — close {count} completed/stale items"
```

Do NOT push unless user explicitly asks.

**For stale items the user wants updated:** Note for a future session. Audit is triage, not rework.

### Phase 5: Snapshot (Remember)

After all closures, re-run the survey and report the delta:

```bash
uv run --script ~/.claude/skills/audit/scripts/audit_survey.py
```

> Audit complete. Closed {N} items.
> Open items: {before} → {after} across {repos} repos.

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Closing without verification | Work may not be done | Always verify against codebase in Phase 2 |
| Trusting briefs at face value | Codebase may have diverged | Verify, especially items >30 days old |
| Auto-closing stale items | Stale brief ≠ stale intent | Flag stale, let human decide |
| Mixing audit with active work | Context thrashing | Audit is a dedicated session activity |
| Editing briefs during audit | Scope creep | Note needed updates, do them later |
| Skipping Phase 5 snapshot | Loses the before/after delta | Always report the delta |
| Bash output for summary | User can't see it (Ctrl+O collapse) | Output as text in response |

## Integration

| Skill | Relationship |
|-------|-------------|
| **bon** | Audit uses bon CLI for closures. Does not duplicate draw-down teaching. Assumes bon is loaded. |
| **close** | Audit's Phase 3→4 mirrors close's Decide→Act. But audit is cross-repo; close is single-session. |
| **open** | After audit, /open re-orients to whatever's next. |

## References

- `references/verification-patterns.md` — How to verify different brief types
- `scripts/audit_survey.py` — Cross-repo survey with JSON output and age flags
