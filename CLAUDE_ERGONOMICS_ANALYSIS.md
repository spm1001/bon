# Bon Ergonomics for Claudes — Failure Mode Analysis

**Source:** 2,542 bon commands across 2,914 Claude Code sessions (tube: 193, kube: 2,721).
**Period:** 2026-02-18 to 2026-03-01.
**Failure rate:** 128 hard failures (5.0%), 117 anti-pattern violations (bon list via Bash).

---

## Failure Modes (ranked by combined frequency and impact)

### 1. `bon work` on Outcome — Type Confusion (10+ incidents, HIGH impact)

The single most repeated error across both machines. Claude tries `bon work` on an outcome instead of an action.

```
bon work mise-wemuve → Error: mise-wemuve is an outcome. Tactical steps are for actions.
bon work bds-pitivo → Error: bds-pitivo is an outcome. ...
bon work tgt-nepuwa → Error: tgt-nepuwa is an outcome. ...
bon work bon-biwulu → Error: bon-biwulu is an outcome. ...
bon work gdn-todejo → Error: gdn-todejo is an outcome. ...
bon work mise-kecigu → Error: mise-kecigu is an outcome. ...
```

Seen in 6 different projects. Claude either doesn't check the type first, or conflates "I want to work on this outcome" with `bon work <id>`.

**Bon's error message is actually good here** — it suggests creating an action or lists existing children. But the error still costs a round-trip every time.

**Root cause:** The mental model gap. Claude thinks "`bon work` = I'm working on this" when it actually means "initialize tactical steps for this action." Outcomes are containers, not workable units. The skill documents this, but the verb "work" has strong natural-language pull.

### 2. `bon step` Without Active Tactical (8 incidents, HIGH frequency)

Claude runs `bon step` when no steps are initialized:

```
bon step → Error: No steps in progress. Run `bon work <id>` first
```

Seen 5+ times on kube alone, across brisk-bear, passe, and other projects. Often happens when:
- A new session picks up work without running `bon work` first
- After `bon done` or `bon wait` cleared the tactical state
- After a session crash where tactical was in progress

**Root cause:** `bon step` is the most-used command (592 total) and feels like "advance." Claude reaches for it instinctively. The draw-down protocol (`show` → `work` → `step`) isn't reliably followed at session boundaries.

### 3. Invented Flags — CLI Hallucination (8 incidents, HIGH impact per incident)

Claude confidently uses flags that don't exist.

| What Claude typed | What exists | Seen on |
|---|---|---|
| `bon new ... --parent ID` | `--outcome ID` or `--for ID` | tube, kube |
| `bon done ID --resolution "text"` | `bon done ID` (no note flag) | tube |
| `bon new -t action -p gdn -o ID` | No short flags | tube |
| `bon add --parent ID "title"` | `bon new --outcome ID "title"` | kube |
| `bon --dir PATH done ID` | No `--dir` flag | kube |

**Two sub-patterns:**
- **`--parent` instead of `--outcome`** — the most common. Every CLI in Claude's training uses `--parent`.
- **Inventing entire commands** — `bon add` (doesn't exist), `bon --dir` (doesn't exist). These come from conflating bon with other tools.

**Cost:** 3 tool calls wasted per incident (error + help + retry).

### 4. Item Not Found — Stale/Wrong IDs (8 incidents, MEDIUM impact)

```
bon show passe-midija → Error: Item 'passe-midija' not found
bon show passe-zimoce → Error: Item 'passe-zimoce' not found
bon work bb-lonego    → Error: Item 'bb-lonego' not found
bon show bb-dewoli    → Error: Item 'bb-dewoli' not found
bon show bb-fiputo    → Error: Item 'bb-fiputo' not found
bon work bb-leseki    → Error: Item 'bb-leseki' not found
bon done trousse-kubufo → Error: Item 'trousse-kubufo' not found
```

Heavily concentrated in brisk-bear (5 incidents) — possibly items were archived or the session had stale context from a previous handoff.

**Root cause:** Claude references IDs from handoffs, previous sessions, or its own memory without verifying they still exist. The brisk-bear cluster suggests a systematic issue — IDs were mentioned in context but the items had been archived or the prefix changed.

### 5. JSON Pipe Failures — Shell Escaping + Schema Confusion (12 incidents, HIGH cost per cluster)

When piping `bon --json` through inline python, Claude fails in three distinct ways:

**a) Shell escaping (5 incidents — the `\!=` bug):**
```python
# Claude writes this in double-quoted heredoc:
if o['status'] \!= 'open': continue
# Bash interprets \! as history expansion escape
```
This exact bug appeared in **4 separate sessions** across tube and kube. Claude keeps making the same escaping error in double-quoted inline python.

**b) Wrong field names (3 incidents):**
```python
item['created']     # actual: item['created_at']
item.get('why')     # actual: item['brief']['why']
```

**c) Empty stdin from swallowed errors (4 incidents):**
```bash
bon list --json 2>/dev/null | python3 -c "..."
# bon errored, stderr suppressed, stdout empty, python gets EOF
```

**One session had 5 consecutive failures** before abandoning JSON entirely.

**Root cause:** No JSON schema documented. Shell escaping in inline python is a known Claude weakness (the `\!=` pattern recurs across sessions suggesting it's in the model weights, not random).

### 6. bon list via Bash — The Invisible Output (117 incidents, SYSTEMIC)

| Machine | bon list via Bash | Total bon commands | Rate |
|---|---|---|---|
| Tube | 33 | 958 | 3.4% |
| Kube | 84 | 1,584 | 5.3% |
| **Total** | **117** | **2,542** | **4.6%** |

Despite the skill explicitly saying "NEVER run bon list via Bash", this is the most frequent anti-pattern. Output gets collapsed behind Ctrl+O in Claude Code, invisible to the user.

**Root cause:** Deep training bias toward CLI tools. The "read a file and reformat" alternative requires 2 steps vs 1. The skill instruction competes with the strongest tool-use prior Claude has.

### 7. Parallel bon new Cascade Failure (7 incidents in 1 session, HIGH waste)

One session on kube tried to create 8 actions in parallel with `bon new`. The first failed (missing `--why`), and the remaining 7 all returned `<tool_use_error>Sibling tool call errored</tool_use_error>`.

**Root cause:** `bon new` failures are not idempotent — when one parallel call fails in CC's tool execution model, sibling calls are cancelled. Filing multiple bon items needs to be sequential, or the briefs need to be perfect on first attempt.

### 8. Cross-Directory / Not Initialized (4 incidents, LOW frequency)

```
cd ~/.claude && bon new "..." → Error: Not initialized. Run `bon init` first.
bon init --prefix gdn (in already-initialized repo) → Error: .bon/ already exists.
bon --dir /Users/modha/Repos/dotfiles done df-luruzo → error: invalid choice
```

The macOS path on a Linux machine is particularly telling — Claude carried context from a different machine's handoff.

### 9. Convert Type Confusion (2 incidents)

```
bon edit mise-vufuzu --parent mise-cetoha → Error: Cannot set --outcome on an outcome
bon convert mise-vufuzu --outcome mise-cetoha → Error: Parent must be an outcome, got action
```

Claude tried to reparent an outcome under an action. Two attempts, two different commands, both failing because the target was the wrong type.

---

## Combined Numbers

| Command | Count (tube+kube) | Failures | Rate |
|---|---|---|---|
| `bon step` | 592 | 8 | 1.4% |
| `bon show` | 492 | 9 | 1.8% |
| `bon new` | 419 | 11 | 2.6% |
| `bon work` | 255 | 12 | 4.7% |
| `bon done` | 215 | 2 | 0.9% |
| `bon edit` | 183 | 2 | 1.1% |
| `bon list` | 117 | 6 | 5.1% |
| `bon wait` | 15 | 0 | 0% |
| `bon convert` | 16 | 2 | 12.5% |
| `bon init` | 4 | 1 | 25% |
| Other | 4 | 0 | 0% |

**`bon work` is the most error-prone high-volume command** at 4.7% — almost entirely from the outcome/action confusion.

**`bon step` is no longer zero-failure** — kube revealed 8 failures, all "no steps in progress." Still the best rate for its volume.

**`bon done` and `bon edit` are remarkably clean** — high volume, very few errors.

---

## Failure Mode Summary Table

| # | Failure mode | Incidents | Projects affected | Root cause | Fix category |
|---|---|---|---|---|---|
| 1 | `bon work` on outcome | 10+ | 6 | Mental model gap: "work" ≠ "activate tactical" | CLI + Skill |
| 2 | `bon step` without tactical | 8 | 3 | Session boundary amnesia | Skill + Hook |
| 3 | Invented flags | 8 | 4 | Training priors (--parent, -t, -p) | CLI + Skill |
| 4 | Stale/wrong IDs | 8 | 3 | Handoff references to archived items | Skill |
| 5 | JSON pipe failures | 12 | 2 | No schema docs + shell escaping weakness | Skill + CLI |
| 6 | bon list via Bash | 117 | all | Training bias toward CLI | Skill (hard) |
| 7 | Parallel bon new cascade | 7 | 1 | CC sibling tool cancellation | Skill |
| 8 | Cross-directory / not init | 4 | 3 | cd breaks implicit scope | CLI |
| 9 | Convert type confusion | 2 | 1 | Unclear type constraints | CLI |

---

## Improvement Recommendations

### A. CLI Changes (in bon codebase)

| # | Change | Addresses | Effort | Impact |
|---|---|---|---|---|
| A1 | **Alias `--parent` to `--outcome`** in `bon new` and `bon edit` | #3 invented flags | Trivial | Kills most common flag error |
| A2 | **`bon work` on outcome auto-suggests**: list children, offer to create one | #1 type confusion | Small | Kills most frequent overall error |
| A3 | **`bon step` when no tactical**: show last-worked action, suggest `bon work <id>` | #2 step amnesia | Small | Recovers from session boundary |
| A4 | **Add `--note` flag to `bon done`** | #3 invented flags | Small | Claude clearly wants to annotate completions |
| A5 | **`bon work` error shows which action has active steps** | #1 tactical collision | Trivial | Already partially implemented |
| A6 | **Did-you-mean on `bon add`, `bon tracking`, `bon search`** | #3 invented commands | Medium | Catches command hallucination |
| A7 | **`bon new` missing-brief error shows what was provided** | #7 cascade | Trivial | "Brief required. Missing: --why. Got: --what, --done" |

### B. SKILL.md / Documentation Changes

| # | Change | Addresses | Effort | Impact |
|---|---|---|---|---|
| B1 | **Document JSON schema** with field examples | #5 JSON confusion | Small | Kills 12-incident cluster |
| B2 | **"Common mistakes" section**: `--parent` → `--outcome`, `bon add` → `bon new`, `-t`/`-p` don't exist | #3 invented flags | Trivial | Preventive |
| B3 | **"bon new must be sequential"** — warn against parallel creation | #7 cascade | Trivial | Prevents 7-call waste |
| B4 | **Reinforce "show before work"** protocol with type-check | #1 type confusion | Trivial | Procedural guard |
| B5 | **Add "verify ID exists before acting"** when using handoff IDs | #4 stale IDs | Trivial | Prevents not-found errors |
| B6 | **Shell escaping warning**: "Use heredoc for inline python, never double-quoted strings with `!=`" | #5 shell escaping | Trivial | Kills the \!= recurrence |

### C. Workflow / Hook Changes

| # | Change | Addresses | Effort | Impact |
|---|---|---|---|---|
| C1 | **Session-start hook shows active tactical** if one exists | #2 step amnesia | Small | New session knows to `bon step`, not `bon work` |
| C2 | **`bon list` wrapper in skill**: "Read bon.txt and output as text" with concrete code example | #6 list via Bash | Small | Makes the right thing easier than the wrong thing |

---

## Priority Ordering

### Tier 1 — Highest leverage, lowest effort

1. **A1** — alias `--parent` → `--outcome` (trivial, kills most common flag error)
2. **B2** — common mistakes section in SKILL.md (trivial, prevents all invented flags)
3. **B1** — document JSON schema (small, kills expensive 12-incident cluster)
4. **B6** — shell escaping warning (trivial, kills recurring `\!=` bug)
5. **B3** — warn against parallel bon new (trivial, prevents cascade waste)

### Tier 2 — Good ROI

6. **A2** — `bon work` on outcome auto-suggests children (small, kills #1 error)
7. **A3** — `bon step` with no tactical suggests last-worked action (small, kills #2 error)
8. **B4** — "show before work" protocol (trivial, procedural guard)
9. **B5** — verify IDs before acting (trivial, prevents not-found)

### Tier 3 — Nice to have

10. **A4** — `--note` on done (Claude wants this but it's not blocking)
11. **C1** — session-start hook shows active tactical
12. **A6** — did-you-mean suggestions
13. **A7** — better missing-brief error message

---

## Observations

### What bon gets right

- **`bon done` almost never fails** (0.9%) — clean, simple, one argument.
- **`bon edit` is solid** (1.1%) — despite being the most complex flag surface.
- **Error messages are genuinely helpful** — the "outcome, not action" error suggests alternatives. The "no steps" error tells you what to run. These save Claude from *additional* round-trips even when the first call fails.
- **The `--for` alias on `--outcome`** already caught some Claude attempts — having two names for the same flag was prescient.

### What Claude is telling us it wants

1. **A way to annotate completions** — `--resolution`, `--note` on done. Claude keeps trying to record *why* something was completed.
2. **`--parent` to work** — this is the strongest training prior. Fighting it is expensive; aliasing it is free.
3. **To work on outcomes directly** — the "work on this thing" intent doesn't map to bon's action-only tactical model. The error is architecturally correct but UX-hostile.
4. **To create multiple items at once** — the parallel bon new pattern is Claude trying to be efficient. Bon's sequential nature needs documenting, or batch creation needs supporting.

### The `\!=` pattern deserves special attention

The `\!=` shell escaping error appeared in **4 separate sessions** across both machines. It's not random — it's in the model weights. Claude uses `\!=` in double-quoted inline python because `!` has special meaning in bash. The fix (use heredoc `<< 'PYEOF'`) is simple, but Claude keeps rediscovering it. This needs a prominent warning in the skill.

---

## Raw Data

| Source | Sessions | Bon commands | Failures | bon list via Bash |
|---|---|---|---|---|
| Tube | 193 | 958 | 24 | 33 |
| Kube | 2,721 | 1,584 | 104 | 84 |
| **Total** | **2,914** | **2,542** | **128** | **117** |

Extraction scripts and full output saved in session tool-results.
