---
name: review
description: "Orchestrates estate-wide backlog review — load FIRST, before any backlog triage. 5 phases (survey, verify, summarize, act, snapshot): opens at the top of the pyramid — jobs-grouped repo headlines, then lane-aware queue alignment and lane population where the operator runs a dispatch queue — then subagents verify briefs against code and nothing closes without approval. Invoke on '/review', 'review my bons', 'backlog review', 'queue reconciliation', 'weekly reconciliation', 'what needs closing', 'clean up bons', 'triage my backlog'. Requires bon skill loaded first."
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

**Third principle: the rite is core; the ceremony is an accent.** /review is the outer loop's close, and its scope is a dial — the same five phases run estate-wide (the default), on a few repos or one (`--repos`), or on one jobs-group (no survey flag exists for groups: run the full survey and narrow Phases 2–4 to that group's boards — the survey's `job` field carries the split). The pyramid document and the dispatch-queue lanes are the operator's personal ceremony riding that spine: the queue-population step (Phase 1, assembly step 4) is a **socket** — variation point `review.populate-queue`, pluggable per team — and a review with no dispatch queue runs the rite complete without it. Verified verdicts, landed repricings and the adjudicated summary are the rite's product everywhere; the populated lanes are the ceremony's product where the queue exists. Nothing downstream depends on a queue existing.

## When to Use

- Monthly or fortnightly backlog review (GTD review cadence)
- After a burst of work across multiple repos
- When bon item count is growing and needs pruning
- When starting a new focus period — shed stale commitments first

## When NOT to Use

- Single-repo triage — just read `bon list` directly (the scope dial's one-repo position means the full five phases on one repo; a quick look isn't a rite)
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
| `visibility_note` | Human sentence splitting the count into Dolt (visible anywhere) vs JSONL (visible only where cloned). **Read this to the user** — it's how a headline jump gets read as clones appearing, not work. |
| `dolt_open` / `jsonl_open` | The split behind `total_open`. `jsonl_open` is machine-dependent; `dolt_open` is not. |
| `unmapped_prefixes` | Prefixes with items but no repos-table row — usually orphaned boards of retired repos. |
| `duplicate_prefixes` | Two boards minting the same id-space (bon-kafono) — different origins sharing one prefix, or a JSONL board squatting on a Dolt-registered prefix. Same-repo clones are exempt. Surface for re-prefixing; never merge their items. |
| `local_path` | Clone under the scan roots — verifiable here. |
| `not_cloned_here: true` | No clone under the scan roots — surveyed, not verifiable here. Caveat: this really means "not under the scan roots"; `~/.dotfiles` is the known board that IS local anyway. |
| `origin_url` | Where a fresh clone would come from, when registered. |
| `open_child_count` (on outcomes) | Open children in the same board — closing this outcome would strand them (the kegewe trap). Non-zero means re-home or close children first. |
| `recent_dones` / `recent_done_count` | Items closed inside `window_days` (default 30), newest first. The list is capped at 10; the count is the TRUE total — trust the count, not the list length. Feeds the pyramid's Recent Progress lines. |
| `git` | Light motion signal for boards with a clone here: `commits_window` + `last_commit` (date and subject). Absent for uncloned boards and non-repos. |
| `job` | The board's jobs-group slug (Dolt: `repos.job` via `bon register --job`; JSONL: `.bon/job` marker). Drives the pyramid grouping. |
| `jobs_unassigned` (top-level) | Boards reporting items but carrying no job — surface these for assignment, never guess a group. |
| `repos_reported` (top-level) | Boards in the output. Includes boards with zero open items whose work all closed inside the window — a recent win is reportable even when nothing remains open. |

**If `dolt` is `"unreachable"`, stop and tell the user** — present the degraded scope honestly (JSONL boards only, every Dolt board missing) and offer to fix the server first. Never present a degraded survey as the estate.

**Present the pyramid, not count tables.** Assemble a DRAFT pyramid from the survey — jobs-grouped repo headlines with Recent Progress and Desired Outcomes at human grain, Cross-cutting Work first, and — where the operator runs a dispatch queue — the alignment block and the population step's annotation inputs. The full format spec, jobs-group display mapping, line-grain rules and ceremony mechanics are in `references/pyramid-format.md` — read it before assembling. In brief:

1. **Check the previous pyramid first** (paths from the accent's `review.draft-path` / `review.archive`; no accent → no prior locations, start fresh): diff the operator's working copy against the archived snapshot — their edits since last time are the freshest desire data; fold them forward, never regenerate over them.
2. **Draft** to the accent's `review.draft-path` (default `/tmp/estate-pyramid-<date>.md`): headline counts **Desired Outcomes, not items** (Parked boards excluded); Cross-cutting Work first with the ranked top-4; then each jobs-group's ✅/🚧 lists, one human-grain line per repo, small/dormant boards collapsed to a named tail line; Parked/Someday last.
3. **Alignment block**: the lanes ARE the join now — membership answers whose move it is, order answers what's next (where accomplis exists, invoke `accomplis:coaching` first for Todoist semantics). Render both directions from the annotation pass: queue → boards (every cited bon verified live) and boards → queue (the drift sweep — board motion with no queue line). No Todoist in this book at all (no accomplis, no queue project) → skip the block in one named line, a non-event rather than a fault. Todoist expected but unreachable → say the block is missing rather than omitting it silently.
4. **Queue population (socket: `review.populate-queue`)**: where the operator runs a dispatch queue, populating its lanes IS the ceremony's product — not a proposed top-N for hand adoption. Pre-annotate every queue line with board truth from the one survey pass, triage bucket-is-verdict, and write only inside announced write-windows **at adjudication** — drafting writes nothing; the STOP gate below holds until the operator is in the conversation. **A live ceremony has two writers on one queue** (the human dragging in the app, the session writing through the API), and the races are silent. Recipe, buckets and the write-window protocol: `references/pyramid-format.md` → Queue population. The queue is the one the operator's accent names (`review.queue`, docs/ACCENT.md); no accent naming a queue → no dispatch queue in this book — one plain line ("no dispatch queue in this book, so no lane population this review"), the rite complete without it, and NEVER map a task system the accent didn't name into the ceremony, however available accomplis makes it. The socket name stays stage direction, never rendered at the human.
5. **Boards in `jobs_unassigned`** get asked about, then persisted (`bon register --job` / `.bon/job`).

Alongside the pyramid, give the survey's one-line vitals: total open, `visibility_note` (a headline jump is usually clones appearing, not work), old-item flags, orphaned prefixes.

**Citation cross-check (orphans).** For boards with a local clone, run:

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/orphans.py --repo <clone-path>
```

The convention (bon-nenine, 2026-08-08): commits doing tracked work cite their bon as a trailing `(bon-ID)`. CITED-BUT-OPEN items are close-candidates to fold into Phases 2–4 — a commit already claims the work moved, so the question is desire, not truth. UNKNOWN-ID entries are typos to fix now. The coverage percentage is adoption telemetry for the convention itself — low numbers are expected on history that predates it (bon's own baseline was 14% organic).

**Sediment check (root handoff piles).** Root `handoffs/` piles silt up with room-specific files whenever room structure or placement conventions move ahead of the data — drift raises no incident for intake to key on, so this clocked rite is the surface positioned to see it (33 misplaced files sat at the notes root for 11 weeks until the 2026-08-22 curation, surfaced only by a direct question). Glance at the newest few root-pile files per surveyed clone: a `purpose:` line naming a room or another repo's work is a stray. Strays become a Phase 4 relocation proposal — never a silent move.

**STOP here.** Adjudicate the pyramid in conversational Q&A clusters (recommendation first — the operator's preferred shape), and wait for scope confirmation before verification. Their wordings apply verbatim; their edits fold back into the draft.

### Phase 2: Verify (the hard part)

Verification is LOCAL-ONLY: dispatch read-only subagents (Task tool, Opus) for repos with a `local_path`. Items in `not_cloned_here` repos are classified **NOT_VERIFIABLE_HERE** — with a note of where they could be verified (a machine holding the clone, or a fresh clone from `origin_url`) — unless the user asks you to clone or ssh. Never let distance quietly downgrade the standard to trusting the brief.

**Freshness gate (before dispatch) — a stale clone is worse than no clone.** A clone is a snapshot; verifying a brief against out-of-date code produces a *confident* wrong verdict (a false DONE/STALE), whereas NOT_VERIFIABLE_HERE at least announces its ignorance. So before dispatching a repo's subagent, bring its clone current or flag it:

```bash
git -C {local_path} fetch --quiet
behind=$(git -C {local_path} rev-list --count HEAD..@{u} 2>/dev/null || echo "?")
```

- `behind` = 0 → current; verify normally.
- `behind` > 0 and the working tree is clean → `git -C {local_path} pull --ff-only` (these clones are read/verify surfaces, so a fast-forward is safe and loses nothing — now you verify against fresh code).
- can't fast-forward (dirty, diverged, no upstream, or `behind` = `?`) → **flag it**: pass "clone is {behind} commits behind — verdicts provisional" into that repo's subagent prompt, and treat its DONE/STALE results as needing a human nod, not auto-closable.

Run the fetch pass once, up front, and tell the user which clones were refreshed and which are flagged before any verdicts land — a verdict from a silently-stale clone looks identical to one from a fresh clone, which is exactly the trap this closes.

**Result files (bg survival):** create a run directory first — `mktemp -d /tmp/bon-audit-$(date +%F)-XXXXXX` — and pass its path into every subagent prompt so each Writes its own result JSON there as it finishes. In-context-only results die if the session gets backgrounded mid-run. Date alone doesn't make the directory unique: two audits on one day would share it and interleave their results (the bon-potipe collision shape, one directory up).

**Parallelism strategy (rolling dispatch, not strict waves):**
- Repos with <5 open items: batch up to 3 repos per subagent
- Repos with 5+ items: one subagent per repo
- Keep ~5 subagents in flight and **refill a slot the moment one finishes** — don't wait for a whole wave to drain before launching the next batch. On the 2026-07-08 run (30 dispatches) rolling dispatch beat strict waves: strict waves leave every fast repo's slot idle while the slowest repo in the wave finishes. Give the user a rough dispatch total (≈{N} dispatches) rather than a wave count — with rolling refill the "wave" framing no longer maps to wall-clock.

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
- EXTERNAL_SURFACE: --done criteria live OFF the repo — a Google Doc/Drive file,
  Confluence page, a SaaS dashboard, an email thread, a deployed service. The item
  is clear, it's just not code-verifiable from here. Name the surface to check.
  (Distinct from UNCLEAR: UNCLEAR = you can't tell what "done" means; EXTERNAL_SURFACE
  = you know exactly, it just lives somewhere this repo can't see.)
- UNCLEAR: cannot determine programmatically, needs human judgment

For EVERY item, also write a `repricing` when the brief misprices what remains:
one or two sentences stating what is actually left, ready to land in the brief.
Null when the brief is accurately priced. Briefs rot toward pessimism — they say
pending after the thing shipped, blocked after the gate opened, five steps when
one remains — so expect repricings to outnumber every other verdict. Put the
evidence (commit, file:line, date) inside the repricing text itself: it will
stand alone in the brief as a dated correction.

Items to verify:
{json_items}

Write your result to {run_dir}/{repo_label}.json AS SOON as you finish
(do not hold it only in your reply), then also return it. Format:
[
  {{
    "id": "bon-xyz",
    "title": "item title",
    "classification": "DONE|STALE|ACTIVE|BLOCKED|EXTERNAL_SURFACE|UNCLEAR",
    "external_surface": "(only for EXTERNAL_SURFACE) where to check — e.g. 'Drive: <doc>', 'Confluence', 'Adalyser dashboard'",
    "reasoning": "one line explanation",
    "evidence": "what you checked that led to this conclusion",
    "repricing": "what actually remains, with evidence inline — or null if the brief is accurately priced"
  }}
]

IMPORTANT: You are READ-ONLY on the repo. Do not modify repo files or run
bon commands. The only file you create is your result JSON in {run_dir}.
```

**Critical constraint:** Subagents verify and classify only. All mutations happen in Phase 4.

### Phase 3: Summarize (Orient)

Collect subagent results and present a clear, actionable summary. **Output as text in your response, not via Bash** (Bash output collapses behind Ctrl+O).

**Expect repricing, not closure, to be the headline yield.** The 2026-08-08 pass measured 5 closures against 172 repricings across 243 items (2% vs 71%) — a brief is written at the moment of least knowledge about the work and rots toward pessimism from there. A run reporting few closures and many corrections succeeded; write the summary that way rather than apologising for it.

**The review has two orthogonal axes — keep them separate.** Verification (Phase 2) answered TRUTH: does each brief still match the code? Only the human can answer DESIRE: is the thing still wanted? A git-quiet board reads identically as "finished and in daily use" and "abandoned" — no substrate distinguishes them, so **never infer desire from staleness**. Truth is per-item and mechanical; desire triages at **repo/outcome level**.

**For big estates (100+ items), hold the desire conversation FIRST, at repo/outcome level, before any item tables.** On the 2026-07-08 run, leading with 145 item verdicts drowned the user ("I'm drowning"); pulling up to six repo-level questions resolved the whole doubt zone in one exchange. The Phase 1 pyramid and the operator's edits to it ARE the opening desire data — start from what their edit pass said, not from a blank sheet. So:

1. **Present the portfolio grouped by pulse** — per repo (and per outcome for the big boards): open-item count, `open_child_count` on outcomes, age flags, and a one-line "what this board is for". This is the *shape*, not verdicts.
2. **Ask the desire questions only the human can answer**, per repo/outcome: *still wanted? veil it? fold into a sibling? convert the promise to an action?* Six good repo-level questions beat 145 rows.
3. **Only after desire is settled**, drop into the item tables below for the boards that survived — that's where the truth-verdicts drive the actual closes.

**Triage vocabulary** (what a desire answer maps to):
- **VEIL** — close with a recorded no-regrets note + a reopening condition. An examined no-action, not done-work: `bon done <id> --note "veil: <why safe to drop> · revisit if <trigger>"`.
- **PARK** — still wanted, not now: `bon someday <id> "revisit condition"`. The OPEN counterpart of VEIL — the item leaves ready/orientation but stays a live desire with its condition recorded. Gentler than veil for work the human still wants.
- **FOLD** — merge into a living sibling outcome; close the absorbed one with a pointer to where it went.
- **CONVERT** — a task-shaped "outcome" that's really one step: `bon convert <id>` demotes it to an action. Honest shrinkage without losing the work.

**Falsifier pass (outcomes carrying `brief.badly`):** where an outcome has a
pre-registered falsifier, check the work against **that**, not only against
`--done`. It is the one criterion in the brief the implementing Claude did not
author and cannot quietly move — which makes it the sharpest tool in the review
and the direct antidote to a green that was satisfied by construction. Three
readings, and each is a real verdict:

- **Falsifier tripped** — the work met `--done` and the failure the human named
  happened anyway. This outranks any truth-verdict in the item tables. Surface it
  first; the outcome is not done, whatever its children say.
- **Falsifier holds** — say so explicitly. An examined "the named failure did not
  occur" is a much stronger close than a `--done` tick, and it is worth one line.
- **No falsifier on a big or ambiguous outcome** — a gap, not an error. Offer to
  ask for one now, in the human's own words. Never fill it in on their behalf,
  including retrospectively: a falsifier written by the implementer after the fact
  is `--done` in a hat with a time machine.

A VEIL's reopening condition and a falsifier are the same kind of object pointed
in opposite directions — one says what would make us pick this back up, the other
what would show we were wrong to start. When veiling an outcome that carries a
`--badly`, reuse its wording in the reopening condition rather than inventing a
fresh trigger; the human already told you what mattered.

**Someday re-check pass:** every review sweeps the parked list (`bon list --someday`, or the survey's `someday` field on items) and re-checks each revisit condition. Condition fired → `bon unsomeday <id>` and triage it live this round. Condition unreadable or stale → ask, don't guess. A parked item whose condition is never re-checked is the hitene failure (a cleared gate sat unnoticed seven weeks behind a title prefix) wearing a nicer costume.

For smaller estates (<100 items), the item tables below ARE the review surface — present them directly.

**Item tables (the backing detail — and the whole surface for small estates):**

```
## Audit Summary — {date}

Scanned {N} open items across {M} boards. {R} carry a repricing — queued for Phase 4 write-back.

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

### External Surface — Verify Off-Repo ({count})

Done-criteria that live on Drive/Confluence/a SaaS/an email — clear, just not in
code. Present as a clean checklist grouped by surface, so the user (or a
facteur/mise-armed session) can tick them in one pass instead of digging.

| Item | Title | Surface to check |
|------|-------|------------------|
| ... | ... | Drive doc / Confluence / dashboard / thread |

### Orphaned Prefixes ({count})

| Prefix | Open items | Triage options |
|--------|-----------|----------------|
| ... | ... | register from a clone / `bon move` the live ones / close as retired (Phase 4 orphan-close recipe) |

### Unclear — Needs Human ({count})

| Repo | Item | Title | Question |
|------|------|-------|----------|
| ... | ... | ... | ... |

Which items should I close, and shall I land the {R} repricings? (Say
"close all ready and land the repricings", name specific IDs, or move
items between categories. Repricings apply batched by repo — you skim a
sample, not every row; any that touch --done come back to you by name.)
```

(For big estates these tables are the *backing detail* — the desire conversation above is the review surface. Don't paste all of them at the user; surface a category on request or once desire has narrowed the boards in play.)

**STOP here.** This is a hard gate — no action without user approval.

### Phase 4: Act (Triage)

Execute the user's decisions.

**Closing discipline — bon resolves the board from your cwd.** Always `cd` into the target repo before `bon done`; running it from anywhere else acts on the wrong board (the filed-where-cd'd hazard).

**Re-check at the moment of action (bon-cenaje) — the board has moved since Phase 2.** Estate audits run for hours while live sessions work the same boards: on 2026-07-26 three items were closed by a concurrent session between verification and audit close (benign that time — `Already done`), and a `bon edit` in the same window would have clobbered the other session's text, since edits are last-writer-wins. So immediately before each `bon done`/`bon edit`, re-show the item and compare against what Phase 2 verified: status still open, and the fields you're about to touch unchanged. Moved state → skip the action and report it ("skipped {id}: closed/edited by another session since verification") rather than acting on a stale verdict — the same per-verdict principle as `bon step --expect`, one layer up. A skipped item is a recorded divergence; a clobbered one is silent.

**For items in repos with a `local_path`:**
```bash
cd {local_path}
bon done {id}
```

**For items in `not_cloned_here` repos** (in preference order):
1. ssh to a machine holding the clone and run `bon done` there
2. Defer with a note in the summary — closure waits for a session on the right machine
3. Clone fresh from `origin_url` only if the user wants it — cloning just to close items is usually overkill

**For orphan boards (a prefix with NO clone anywhere — a retired repo whose Dolt items linger; e.g. consomme/gm/tmig/day on 2026-07-08):**

Only inside the review venue, and only after the user confirms the board is retired (the desire axis — a git-quiet orphan can be a finished-and-*absorbed* tool, not a dead one). Reach it by a scratch reconnect to the shared Dolt DB — the real `bon` CLI keeps proper commit provenance, unlike raw SQL (which leaves the change uncommitted in Dolt's working set and skips the unblock cascade):

```bash
t=$(mktemp -d); cd "$t"
bon init --prefix <orphan-prefix> --backend dolt   # reconnects; now sees the orphan items
bon done <prefix-xxx> --note "board retired: <evidence>. audit <date>"
# test-litter → done THEN archive to remove entirely. archive needs done first, and an
# outcome won't archive until ITS actions are archived, so do children before parents:
#   bon done <child> --note "..."; bon archive <child>; bon archive <parent>
```

`bon init` writes ONE scratch row into the `repos` label table (`<prefix> → <tmpdir>, no origin`). Since you close every open item, that board then has zero open items and never surfaces in a survey again — the row is invisible. Tidy it anyway, in one committed DELETE at the end:

```bash
uv run --with pymysql - <<'PY'
import pymysql, tomllib; from pathlib import Path
cfg={"host":"127.0.0.1","port":3306,"database":"bon","user":"root","password":""}
p=Path.home()/".config/bon/dolt.toml"
if p.exists():
    fc=tomllib.load(open(p,"rb")); cfg.update({k:fc[k] for k in cfg if k in fc})
c=pymysql.connect(autocommit=True, **cfg); cur=c.cursor()
cur.execute("DELETE FROM repos WHERE prefix IN ('<p1>','<p2>')")   # the orphan prefixes
cur.execute("CALL DOLT_COMMIT('-A','-m','repos: remove scratch label rows from orphan-close')")
PY
```

If this dance (or the `ssh`-to-clone step above) starts to grate, that's the trigger to build **`bon --board <prefix>`** — act on any Dolt board by prefix with no cwd, no scratch dir, no label-row to tidy. Filed with that tripwire, not built speculatively: **bon-wezahu**.

**Commit strategy (JSONL boards only — Dolt boards have no file to commit):**
```bash
cd {local_path}
git add .bon/items.jsonl
git commit -m "bon: audit — close {count} completed/stale items"
```

Push per the estate's standing practice. Unpushed JSONL closures are invisible to other machines until pushed.

**Land the repricings — they are the audit's main product** (adjudicated 2026-08-09, bon-zewake; measured at 71% of yield against 2% closures on the 2026-08-08 run). A verifier-produced repricing is a bounded, already-written correction; applying it is closer to `bon done` than to rewriting a brief. Behind the same approval gate as closures — batched by repo, skimmed rather than read row-by-row — write each one back, per field:

- **`--why` / `--how`**: append one dated block to the end of the field — `CORRECTION {verified-date} ({source}): {repricing}`. One correction block per field: a later audit's block *replaces* it, and superseded text stays recoverable in Dolt/git history.
- **`--what`**: when the step list itself is what rotted, rewrite it — `bon work` turns these steps into a live tactical checklist, so a stale step gets executed, not just read.
- **`--done`**: propose changes to the user by name, item by item, and apply only what they approve. The done-criterion is the clause a Claude can satisfy by construction — the same reason the falsifier is human-authored.

Apply via `bon edit {id}` with JSON stdin (read-modify-write; use the subprocess arg-list form for scripted batches, and read one back to confirm the write landed). Composing fresh brief prose beyond what the verifier wrote is a different job — file it for its own session.

### Phase 5: Snapshot (Remember)

After all closures, re-run the survey and report the delta:

```bash
uv run --script ${CLAUDE_SKILL_DIR}/scripts/audit_survey.py
```

> Audit complete. Closed {N} items.
> Open items: {before} → {after} across {repos} boards.

**Where the ceremony populated the queue, the read-back closes the loop on the operator's artefact too** — one more line: `Queue: <workable lane> {X} in your order · <with-operator lane> {Y} · {Z} ticked, {W} minted.` And re-check the lanes against this run's OWN closures first: Phase 4 closes bons hours after the annotation pass, so a line refreshed at Phase 1 can be stale again by snapshot — re-touch it in one final announced write-window, or flag it by name in the read-back, rather than leaving a queue that cites bons this very ceremony closed.

**Then archive the run durably** — copy the run directory (before/after survey JSON, per-repo verification JSONs, the summary) to the accent's `review.archive` location, plus a snapshot of the final pyramid (and the reconciliation artefact when the run included one); no accent → the run directory itself is this run's record: leave it in place, name its path at close, and note that a /tmp run dir dies at reboot. The next audit diffs against it: what closed, what's still limping along, what reappeared — and the pyramid snapshot is what makes the operator's later edits detectable as edits.

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
| Composing new brief prose during audit | Unbounded rework | Apply verifier-written repricings (Phase 4, gated); fresh thinking gets its own session |
| Skipping Phase 5 snapshot | Loses the before/after delta | Always report the delta and archive the run |
| Bash output for summary | User can't see it (Ctrl+O collapse) | Output as text in response |

## Integration

| Skill | Relationship |
|-------|-------------|
| **bon** | Audit uses bon CLI for closures, and `bon register` maintains the repos mapping (labels + jobs-groups) the survey reads. Does not duplicate draw-down teaching. Assumes bon is loaded. |
| **accomplis:coaching** | Invoke before touching Todoist for the alignment block and queue population — it holds structure discovery and GTD semantics. The review renders the bon↔Todoist join and, at the ceremony with the operator present, populates the queue lanes inside announced write-windows (pyramid-format.md). Never an automatic sync — queue writes happen only in the ceremony, adjudicated line by line. |
| **close** | Audit's Phase 3→4 mirrors close's Decide→Act. But audit is estate-wide; close is single-session. |
| **open** | After review, /open re-orients to whatever's next. |

## References

- `references/pyramid-format.md` — The Phase 1 pyramid: document shape, jobs display mapping, alignment block, queue population (lanes, pre-annotation, write-windows), ceremony mechanics
- `references/verification-patterns.md` — How to verify different brief types
- `scripts/audit_survey.py` — Hybrid estate survey (Dolt-global + JSONL sweep) with recent wins, git signal, jobs grouping, age flags
- `scripts/orphans.py` — Per-clone citation cross-check: commits vs board (CITED-BUT-OPEN close-candidates, UNKNOWN-ID typos, coverage telemetry)
