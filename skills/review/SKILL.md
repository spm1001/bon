---
name: review
description: "Orchestrates periodic estate-wide backlog review using 5-phase survey-verify-summarize-act-snapshot workflow that prevents closing items without codebase verification. Surveys open bon items across the WHOLE estate (Dolt-global query covers repos not cloned on this machine; filesystem sweep covers JSONL boards), dispatches parallel subagents to verify briefs against actual code where clones exist, classifies as done/stale/active/blocked/not-verifiable-here, and presents triage summary for user approval before closing. Load before backlog review sessions. Invoke on '/review', 'review my bons', 'backlog review', 'what needs closing', 'clean up bons', 'triage my backlog'. Requires bon skill loaded first."
allowed-tools:
  - "Bash(bon:*)"
  - "Bash(uv:*)"
  - Read
  - Write
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
---

# Audit

Estate-wide backlog review encoded as a repeatable 5-phase workflow. Replaces the manual process of scanning repos, reading briefs, checking codebase state, and deciding what to close.

**Core principle: Verify against code, not briefs.** A brief says what was planned. The codebase says what happened. Always check.

**Second principle: Survey everywhere, verify locally.** The survey sees every board in the shared Dolt database — including repos with no clone on this machine. Verification needs the actual working tree. When they diverge, say so explicitly: an item you can see but can't verify is NOT_VERIFIABLE_HERE, never trust-the-brief.

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
- **`uv` in PATH** — audit_survey.py runs via `uv run --script` (pymysql resolves automatically via PEP 723)
- **Dolt server reachable** for the estate-wide view. If it's down the survey falls back to JSONL-boards-only and says so loudly — consider fixing the server before reviewing.

## Workflow: 5 Phases

### Phase 1: Survey (Gather)

Run the audit survey to get structured data on all open items:

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/audit_survey.py
```

Or filter to specific repos:

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/audit_survey.py --repos trousse passe gueridon
```

**How it surveys (hybrid):** one global Dolt query is the primary index — it covers every Dolt-backed board in the estate, cloned here or not, including boards outside the scan roots (`~/.dotfiles`). The filesystem scan only reads JSONL boards. Repo labels come from Dolt's self-registering `repos` mapping table (`bon register`).

**Output fields that drive the later phases:**

| Field | Meaning |
|-------|---------|
| `dolt: "global"` | Full estate view. `"unreachable"` = JSONL boards only — a DEGRADED survey. |
| `unmapped_prefixes` | Prefixes with items but no repos-table row — usually orphaned boards of retired repos. |
| `local_path` | Clone under the scan roots — verifiable here. |
| `not_cloned_here: true` | No clone under the scan roots — surveyed, not verifiable here. Caveat: this really means "not under the scan roots"; `~/.dotfiles` is the known board that IS local anyway. |
| `origin_url` | Where a fresh clone would come from, when registered. |

**If `dolt` is `"unreachable"`, stop and tell the user** — present the degraded scope honestly (JSONL boards only, every Dolt board missing) and offer to fix the server first. Never present a degraded survey as the estate.

**Present the landscape to the user:**

> Scanned {N} open items across {M} boards ({K} verifiable here, {L} not cloned here).
> Top repos: {repo1} ({count}), {repo2} ({count}), ...
> {X} items flagged old (30d+), {Y} very old (60d+).
> Orphaned prefixes (no live repo mapping): {unmapped list with counts}.
>
> Which repos should I audit? (default: all with open items)

**STOP here.** Wait for user to confirm scope before proceeding.

### Phase 2: Verify (the hard part)

Verification is LOCAL-ONLY: dispatch read-only subagents (Task tool, Opus) for repos with a `local_path`. Items in `not_cloned_here` repos are classified **NOT_VERIFIABLE_HERE** — with a note of where they could be verified (a machine holding the clone, or a fresh clone from `origin_url`) — unless the user asks you to clone or ssh. Never let distance quietly downgrade the standard to trusting the brief.

**Result files (bg survival):** create a run directory first (`/tmp/bon-audit-$(date +%F)/`) and have every subagent Write its own result JSON there as it finishes. In-context-only results die if the session gets backgrounded mid-run.

**Parallelism strategy (expect waves):**
- Repos with <5 open items: batch up to 3 repos per subagent
- Repos with 5+ items: one subagent per repo
- Max 5 concurrent subagents — a large estate means multiple waves (28 dispatches ≈ 6 waves); tell the user the expected wave count up front

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

Write your result to {run_dir}/{repo_label}.json AS SOON as you finish
(do not hold it only in your reply), then also return it. Format:
[
  {{
    "id": "bon-xyz",
    "title": "item title",
    "classification": "DONE|STALE|ACTIVE|BLOCKED|UNCLEAR",
    "reasoning": "one line explanation",
    "evidence": "what you checked that led to this conclusion"
  }}
]

IMPORTANT: You are READ-ONLY on the repo. Do not modify repo files or run
bon commands. The only file you create is your result JSON in {run_dir}.
```

**Critical constraint:** Subagents verify and classify only. All mutations happen in Phase 4.

### Phase 3: Summarize (Orient)

Collect subagent results and present a clear, actionable summary. **Output as text in your response, not via Bash** (Bash output collapses behind Ctrl+O).

Format:

```
## Audit Summary — {date}

Scanned {N} open items across {M} boards.

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

### Not Verifiable Here ({count})

| Repo | Items | Where verifiable |
|------|-------|------------------|
| ... | ... | machine/clone hint, or origin_url |

### Orphaned Prefixes ({count})

| Prefix | Open items | Triage options |
|--------|-----------|----------------|
| ... | ... | register from a clone / bon move the live ones / close as retired |

### Unclear — Needs Human ({count})

| Repo | Item | Title | Question |
|------|------|-------|----------|
| ... | ... | ... | ... |

Which items should I close? (Say "close all ready", name specific IDs,
or move items between categories.)
```

**For big estates (100+ items), lead with the outcome-level rollup**, not the item tables: desired outcomes per repo with open-child counts, childless outcomes, standalone-action share. Nine portfolio fronts beat 586 item verdicts as the human review surface — the item tables back it up underneath.

**STOP here.** This is a hard gate — no action without user approval.

### Phase 4: Act (Triage)

Execute the user's decisions.

**Closing discipline — bon resolves the board from your cwd.** Always `cd` into the target repo before `bon done`; running it from anywhere else acts on the wrong board (the filed-where-cd'd hazard).

**For items in repos with a `local_path`:**
```bash
cd {local_path}
bon done {id}
```

**For items in `not_cloned_here` repos** (in preference order):
1. ssh to a machine holding the clone and run `bon done` there
2. Defer with a note in the summary — closure waits for a session on the right machine
3. Clone fresh from `origin_url` only if the user wants it — cloning just to close items is usually overkill

**Commit strategy (JSONL boards only — Dolt boards have no file to commit):**
```bash
cd {local_path}
git add .bon/items.jsonl
git commit -m "bon: audit — close {count} completed/stale items"
```

Push per the estate's standing practice. Unpushed JSONL closures are invisible to other machines until pushed.

**For stale items the user wants updated:** Note for a future session. Audit is triage, not rework.

### Phase 5: Snapshot (Remember)

After all closures, re-run the survey and report the delta:

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/audit_survey.py
```

> Audit complete. Closed {N} items.
> Open items: {before} → {after} across {repos} boards.

**Then archive the run durably** — copy the run directory (before/after survey JSON, per-repo verification JSONs, the summary) to `~/notes/raw/claude/bon-audit-{date}/`. The next audit diffs against it: what closed, what's still limping along, what reappeared.

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Closing without verification | Work may not be done | Always verify against codebase in Phase 2 |
| Trusting briefs at face value | Codebase may have diverged | Verify, especially items >30 days old |
| Trust-the-brief for uncloned repos | Distance is not verification | Classify NOT_VERIFIABLE_HERE; verify where the code lives |
| Presenting a degraded survey as the estate | `dolt: unreachable` output is JSONL-only | Name the degradation; offer to fix the server first |
| Closing items from the wrong cwd | bon resolves the board by cwd | `cd` into the target clone (or ssh) before `bon done` |
| In-context-only subagent results | A bg'd session loses them | Subagents Write result files as they finish |
| Auto-closing stale items | Stale brief ≠ stale intent | Flag stale, let human decide |
| Mixing audit with active work | Context thrashing | Audit is a dedicated session activity |
| Editing briefs during audit | Scope creep | Note needed updates, do them later |
| Skipping Phase 5 snapshot | Loses the before/after delta | Always report the delta and archive the run |
| Bash output for summary | User can't see it (Ctrl+O collapse) | Output as text in response |

## Integration

| Skill | Relationship |
|-------|-------------|
| **bon** | Audit uses bon CLI for closures, and `bon register` maintains the repos mapping the survey labels come from. Does not duplicate draw-down teaching. Assumes bon is loaded. |
| **close** | Audit's Phase 3→4 mirrors close's Decide→Act. But audit is estate-wide; close is single-session. |
| **open** | After review, /open re-orients to whatever's next. |

## References

- `references/verification-patterns.md` — How to verify different brief types
- `scripts/audit_survey.py` — Hybrid estate survey (Dolt-global + JSONL sweep) with JSON output and age flags
