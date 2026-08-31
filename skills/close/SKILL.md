---
name: close
description: "Run before /exit, to reflect on this session and end it properly by figuring out what's best to (1) do now, with current context wisdom (2) file as a handoff for the next Claude as well as (3) capture for future Claudes in collective memory. Ends with a set of quick fixes and a commit. Invoke on 'wrap up', 'let's finish', 'close out', '/close'."
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Skill
---

# /close

Capture what matters while context is rich, then commit and exit.

## When to Use

- Session ending naturally (work complete)
- Context window nearing capacity
- User says "wrap up", "let's finish", "close out"
- Main session goals complete

## When NOT to Use

- Session was ephemeral and doesn't need handoff
- There are other tasks which relate to current context load
- There is still useful context runway left

## Structure

```
Orient        → find scripts, verify .bon, close-context.sh → context, HANDOFF_DIR, SESSION_ID
Reflect       → review session's work, propose Now/Bon plan → user reviews
Act           → execute, craft handoff, cold-read it, commit → overnight Claude reviews
```

---

## Orient

Find the close-context script and run it. This gives you the raw material for the rest of the process.

The scripts directory is a sibling of this skill's own tree: take the base directory the harness printed when this skill loaded (`…/bon/<version>/skills/close`) and replace `skills/close` with `scripts`. That copy is by construction the version this session actually loaded.

```bash
BON_SCRIPTS="<this skill's base directory, with skills/close → scripts>"
"$BON_SCRIPTS/close-context.sh"
```

If you have no base directory, fall back to the highest cached *version* — never mtime ordering (`ls -td`): `claude plugin update` touches older dirs after writing the new one, so mtime deterministically picks the stale copy right after a publish (bon-katuso, measured twice). And note the fallback's own limit: the highest cached version isn't always the loaded one, since user- and project-scope installs can pin different versions.

```bash
BON_SCRIPTS=$(ls -1d ~/.claude/plugins/cache/*/bon/*/scripts 2>/dev/null | grep -v '/skills/' | sort -V | tail -1)
```

If the script isn't found either way, diagnose with `find ~/.claude/plugins/cache -name "close-context.sh"`. If unfixable, gather context manually — but closure should always result in a handoff, even without the script.

The script outputs TIME, GIT, BON, LOCATION context, plus the values you'll need in Act: **HANDOFF_DIR**, **SESSION_ID** and **HANDOFF_FILE**. Six companion keys appear only when they apply, and each one changes what you do:

| Key | Meaning | What to do |
|---|---|---|
| `SESSION_ID_SOURCE=unavailable` (with `SESSION_ID_CUE`) | The harness gave no session id, so the filename carries a timestamp | Leave `session_id:` blank in the frontmatter and say so in the close summary. Never substitute an id you inferred — the suffix exists for transcript linkage, so a wrong one sends a future reader into a stranger's conversation |
| `HANDOFF_FILE_TAKEN=<name>` | The natural filename was already on disk; `HANDOFF_FILE` is suffixed | Normally just use the suffixed name — it means this session is closing twice today. Worth a sentence if you weren't expecting it |
| `HANDOFF_MIGRATED=<n>` (with `HANDOFF_MIGRATED_DEST`) | This repo still had handoffs in the retired `.bon/handoffs/`; the script moved them to the visible `handoffs/` (bon-sedoze) | **Stage the move in your commit** — `git mv` staged it for tracked files, but an untracked pile is now sitting as new files. Mention it in one line: their history just changed location |
| `HANDOFF_MIGRATE_INCOMPLETE=true` | At least one legacy handoff could not be moved | Those files are no longer read by anything. Say so plainly and move them by hand — don't let it pass as a detail |
| `BRIDGE_UNCLOSED=<file>` (with `BRIDGE_CUE`) | This repo holds an id-migration bridge doc with no dated close-out (bon-kefoba) | If the migration has landed, append one dated `Closed out YYYY-MM-DD` section saying what landed and leave the text above it alone — it is the record of what was true then. If it hasn't landed, say so in one line and move on. A bridge doc is the first thing a future reader consults about a retired id, so one still reading as in-flight sends them to do work already done |
| `HANDOFF_DIR_SOURCE=global-fallback` | No board was found, so the handoff goes to `~/.bon/handoffs` | It won't sync anywhere. Say so, and consider whether it belongs on a real board instead |
| `HANDOFF_DIR_SOURCE=ambiguous` (with `HANDOFF_CANDIDATE` lines, **no `HANDOFF_DIR`**) | Cwd is outside any board repo and several sibling repos sit below it — the script refuses to guess among them (bon-gojeni: recency picks whichever repo the last publish touched, not where you worked) | Placement is **work-based**: pick the candidate this session actually worked in (you know; the script can't), and write `HANDOFF_FILE` into that repo's visible `handoffs/` — the room you worked in if it has one, else the repo root. If the session's work matches none of the candidates, `~/.bon/handoffs` is the honest fallback — say so |

### Which mode are you in?

The rite adapts to what the session can reach — two independent axes (full spec: `docs/CONTRACT.md`):

- **Board visible?** Can you see the repo's `.bon/`, `handoffs/`, or `understanding.md` (via Read/Glob)?
- **Writer reachable?** Does `bon list` actually return — the CLI on PATH *and* a reachable backend?

| Board | Writer | Mode | What close does |
|-------|--------|------|-----------------|
| visible | reachable | **Full-fat** | The full path below — board mutations, handoff, commit |
| visible | unreachable | **Candidate mode** | Handoff carries board mutations as *candidates*; no `bon` calls, no commit (see Act) |
| absent | either | **Board-less** | Reflect and write a handoff from the vehicle's own memory; skip the board steps silently |

Writer-unreachability shows up generically as: no `bon` on PATH, `bon list` erroring on its backend, or no `.git` to commit into. The live case is Cowork's mounted sandbox — files are visible via Read, but its bash tool has no `bon`. Detect it by *trying* `bon list`; identify it by the signals, never by testing for "Cowork" by name.

### Board health: outcomes with no actions

Outcomes created mid-session often haven't been broken down yet — a long
mind-sweep session once produced six of them, each a title with no path to
done. Spot them while you still have the context to break them down:

```bash
bon list --json | python3 -c "
import json, sys
for o in json.load(sys.stdin)['outcomes']:
    if o['status'] == 'open' and not o['actions']:
        print(o['id'], '—', o['title'])
"
```

Carry anything that surfaces into the Reflect proposal: break it down now,
file a first action, or confirm it's intentionally still a sketch.

### New rooms: registered?

If this session created a **new room** — a new nested `CLAUDE.md` below the repo
root — check it's discoverable, so it doesn't become an unread twin. (The `notes`
egta room was minted beside its unread predecessor and the duplication surfaced
twelve days later.)

```bash
git status --porcelain | grep -E '(^A|^\?\?).*/CLAUDE\.md$'   # new room files this session
```

For each new room, confirm two things: it's listed in its parent room's index or
table (and would appear in `rooms.md`), and this session's handoff lands in the
room you actually worked in (see "Where does it go?"). Carry any gap into the
Reflect proposal as a "Now" fix while you still have the context.

Before continuing, check where you are: compare `pwd -P` with the Working directory in your system prompt. If they differ, `cd` back. If the session started in a folder called 'scratch' or 'chat' but the work belongs elsewhere, note the target repo — you'll route the handoff there in Act.

If CWD has no `.git/` directory but contains code files (`.py`, `.ts`, etc.), suggest: "This directory has code but isn't a repo — `/scaffold` can wrap proper structure around it (adopt mode)." Don't auto-invoke; just surface the option.

---

## Reflect

This is the heart of /close. You're reviewing the session — what to finish now and what to hand forward. You need to try and step back from what's happened and look at it with fresh eyes. Think about future Claudes and how you can help them best, by asking yourself these reflective questions:

1. **What did we miss?** — Things we should have done but didn't: docs we should have updated, decisions we should have documented, tests we should have written, assumptions we should have verified
2. **What could we have done better?** — Better can be many things, but for us it's about being more elegant, more maintainable, more robust, more consistent and yes, more creative.
3. **What could go wrong in future?** — Race conditions, silent failures, fragile dependencies, implicit knowledge not written down, non-obvious relationships between files
4. **Did the ground move under the cold-start docs?** — If this session changed architecture, substrate, constraints, or a tool's command surface, CLAUDE.md was written for the world before the change. Working sessions live in understanding.md and rarely re-read CLAUDE.md, so it drifts most at exactly these boundaries. Sweep the whole file (opening description, tables, counts, anti-patterns) against current reality. A mid-session "I updated CLAUDE.md" is usually a partial fix — the paragraph you touched is right while a table three sections down still describes the old world; trust the sweep, not the memory of the edit.

These questions work best when answered with genuine honesty — what you actually noticed, not what sounds thorough. Share your knowledge.

### Generate actions from your reflections

Now turn your reflections into a plan. Like Newton II, most of your observations will imply an equal and opposite action — name it. Here's what that inversion looks like in practice:

> **Reflection:** "We updated the handoff template but CLAUDE.md still describes the old format."
> → **Now:** Update CLAUDE.md (5 min, have the context)
>
> **Reflection:** "The /open skill expects contribution files that we've stopped writing."
> → **Later:** Update /open to read new handoff format (needs fresh session, different context load)
>
> **Reflection:** "The filename scheme changed but downstream scripts may parse the old format."
> → **Later:** Audit scripts for filename assumptions (needs a thorough trawl across repos)
>
> **Reflection:** "Collaborative editing via rmate works but Sublime doesn't auto-refresh remote files."
> → **User override: drop** — tafelmusik will supersede this approach
>
> **Reflection:** "When the skill assumes competence rather than assuming failure, instructions get shorter and behaviour gets better."
> → **For Claudes to come:** Skill register insight

The principle: you have context that the next Claude won't. Use it. Cabinet responsibility means leaving things better than you found them — it may be a long time until another Claude comes this way again.

### Triage before sorting

Before you sort, run each observation through a table. The table separates "what I noticed" from "what to do about it" — some observations warrant action, others are worth naming but not acting on.

| # | Reflection | Consequence | Remedy | When |
|---|-----------|-------------|--------|------|
| 1 | No input validation on POST endpoint | Malformed requests → 500 instead of 400; confusing for future Claudes debugging | Add guard, return 400 with message | Do now |
| 2 | Magic number in sync loop instead of shared constant | One side breaks silently if prefix changes | Extract constant to shared module | Do now |
| 3 | Auto-discovery silently picks first room when multiple active | User doesn't know where their comment went | Print selected room name | Do now |
| 4 | Resolve endpoint doesn't scope to room | Semantically misleading URL; subtle bugs when more surfaces consume it | Add WHERE clause to scope resolve | File as Bon |
| 5 | Sends session_id that server ignores | Dangling intent — but removing means re-adding later | Leave it; field is harmless and the intent is documented | Chill |

The three When values are **Do now**, **File as Bon**, and **Chill**. Every row gets one — no blank cells. "Chill" is the most interesting — it gives you permission to notice something without manufacturing work for it. An examined "no action needed" is a real conclusion, not an omission.

Present the table to the user grouped by timing — it's their review surface. They may promote or demote items.

**Consistency check:** Remedy and When should agree. If your Remedy names concrete work, When should be Do now or File as Bon. If you're uncertain, lean toward action — the user can always demote.

Now sort the remaining actions into three buckets:

1. **Now** — things it would be best for you to do before /exit because you have the context:
- Small completions (under 5 minutes)
- Quick fixes where something is broken — even if they are in other repos, or were pre-existing problems
- Closing off existing or superseded bon items with `--note`

2. **Later** — tasks for a future session, which should be nested under Outcomes per the Bon skill:
- Bigger things that need a fresh session — you know what needs doing, but it would need a different context load
- Refactoring of Bons where you see a different path forward given the session's learnings
- Things into which you have gained understanding which need further attention, even in other repos

3. **For Claudes to come** — what one thing did you learn or discover that should be contributed to the stock of future Claude understanding; an architectural insight, a taste judgment, a decision with real alternatives, a mistake not to be repeated, a trick you discovered which would save us significant time. A shard of wisdom gleaned.

### Personal half (variation point `close.personal`)

`close.personal` names a point inside this one rite — one /close for everyone; the personal half is a file this step reads, silently absent on most machines, never a second close. If the context script printed `ACCENT=<path>` (the operator's personal half, `~/.claude/mit-accent.md` — spec: `docs/ACCENT.md`), Read its `## close.personal` section and run it here, before proposing the close-out. The worked example is an operator whose accent reads their dispatch queue, checks the session against it, and — under write sanctions the accent itself records, in their words, with dates — ticks completed lines, adds clean-case successor lines, and rewords stale ones, always telling them in the close-out block, never asking first.

The four laws (docs/ACCENT.md) apply: no `ACCENT=` line or no `## close.personal` section → skip SILENTLY, the close is complete without it; this slot only, the spine is not overridable; a broken half is one plain line, never a banner; and NO write into the operator's own systems happens without the accent's own recorded sanction — an accent without written sanctions is read-only, however convenient the write would be.

**If an accent's sanctions include ticking queue lines, read each line's DESCRIPTION before you tick it** (bon-zevajo). A tick is atomic and takes the description with it, so a second work-item parked there dies with the line, silently — that is what happened on 2026-08-30 to the "also take the five" rider, which the operator then had to re-mint by hand. A description is the sanctioned home for a *steer* (how to do that line's work, which rightly shares its fate) and the wrong home for a second work-item, which needs a line of its own first. Nothing catches this for you: a rider carries no bon id, so any join keyed on cited ids is structurally blind to it, and a queue read that pulls only each line's content never sees descriptions at all.

### Cultivate the personal half

The accent grows only from observation, and this is the one place it grows (law 1's other half). If this session watched the operator do something rite-shaped and recurring BY HAND — a queue they always consult before picking work, a ranking they always impose, a path they always archive to — propose capturing it in their accent as part of the close-out: name the habit, the variation point it would fill, and the exact text you'd add. From observed habits only: never propose for an empty slot on a machine with no accent, never turn an absence into a nudge. Any write sanction enters the accent only in the operator's own words, opt-in, dated (law 4).

The file format, inlined here because minting a FIRST accent happens at this step (full spec: `docs/ACCENT.md` in the bon repo): `~/.claude/mit-accent.md`, four sections keyed by the personal variation-point ids — `## open.personal`, `## close.personal`, `## plan.personal`, `## review.personal` (ownership-named, settled 2026-08-30). Those four ids are the only keys the rites parse; everything inside a section — sub-headings, pet names, structure — is the operator's own prose, replaceable without touching core. (Step sockets like `review.populate-queue` are a different species: stage direction inside the spine, not accent keys.)

Propose these to the user:

> "Here's how I suggest we close out:
>
> **Things to do now:** [concrete list of remedies implied by your reflections]
>
> **Bons to file for next:** [list of future work with an explanation of what's at stake]
>
> **Empty outcomes:** [only when Orient flagged any — per outcome: break down now, file a first action, or confirm it's intentionally a sketch]
>
> **Personal half:** [whatever your accent's `close.personal` produced — its block, verbatim; omit this line entirely when no accent ran]
>
> **Insight to capture for the future:** [one dense paragraph to contribute]
>
> What do you think?"

Your job is to surface what you noticed and what's at stake. The user decides what's worth tracking — don't filter on their behalf.

Wait for approval or adjustment before doing anything.

---

## Act

**Candidate mode** (board visible, writer unreachable): work with Read/Write tools only. Skip the board closes in "Do the Now work" and skip "File the new bons" — instead record every intended board mutation as a **Candidate** in the handoff (format under "Craft the handoff"), and skip the commit. Now-fixes to plain files, the reflection, and the handoff itself all run unchanged. **Board-less mode**: skip the board steps silently and write a handoff from the vehicle's own memory. The rest of this section is the full-fat path.

### Do the "Now" work

Work through the list. Finish the quick fixes, close off completed Bon items - generally leave things how you'd like to find them.

**Closing something a fresh reader ought to check first?** `bon step --no-complete` on the final step finishes the tactical without closing the card, so the verdict can wait for the check instead of the check chasing the verdict — `bon step` otherwise auto-completes on the last step, which closes the card before anyone has read the work. `bon reopen` undoes a close that got ahead of itself.

### File the new bons

When filing bons, the `--why` should explain what's at stake — not just describe the work. Use `bon new --json` for anything with technical content. Capture enough detail in the `--how` that a future Claude could pick it up without your context load.

**File it, then do it** (bon-nalube). After filing, sweep the just-filed items once more: any that are small, in-context and surgery-free — a doc line you already know the wording of, a config tweak, a one-function fix in a file you have open — get executed NOW, in this session, before you exit, **and closed (`bon done` with a note) so the board and the handoff's Done section carry the split, not just the chat**. Filing an item you could knock out in five minutes hands a future session your context-load for free, and the human had to ask for exactly this after nearly every close before it became a House rule. Say which you knocked out and which you deliberately left, so the split is visible. A nudge, not a gate: your own judgment on "inapt for this context" stands — bigger surgery, a cold-context need, a decision that isn't yours, or anything the user explicitly demoted to file-only during review, all stay filed.

For cross-repo issues: file a bon in the relevant repo rather than making changes there. Cabinet responsibility means noticing and capturing, not committing in repos where you may not have the full picture.

### Craft the handoff

Now write the handoff. This is where your reflections become concrete - where you step back and capture what actually mattered. Write as if the reader will have none of your context and all of your responsibility.

Your handoff has two specific audiences.

1. There is the immediate next Claude to whom you are passing the baton. Point out where they should go next. Get them off to a flying start. It's your final message to them. 

2. Then there are the background processes which will run overnight to incorporate and index your learning and insight into the collective memory. The bits that will live on. 

**The `items:` line is the baton's address** (bon-jeweke): list the bon IDs this session actually worked — comma-separated, full IDs, ONE physical line (a wrapped list is invisible to a strict reader). Worked means closed, stepped, or materially advanced — never merely filed. `bon work` looks up the newest handoff citing the drawn item and surfaces it at draw-down, so the directional briefing reaches whoever picks up the thread, not just whoever opens next. An ID you omit is a thread whose next runner starts cold; an ID you pad in is a false "last session on this thread" claim.

#### Template

```markdown
# Handoff — {DATE}

session_id: {SESSION_ID}
purpose: {one line — what the session was for}
items: {bon IDs this session WORKED — closed, stepped, or materially advanced. One physical line, comma-separated, full IDs. NOT items merely filed at close: their brief carries its own origin, and listing them would brief the next runner on a thread no session has run. Omit the line when none}
format: fond-v1

## For the next Claude

### Done
- [What was accomplished, in verb form — include bon IDs when closing items]

### Reflection
[What worked, what didn't, process observations.
Include anything the user added or emphasised during review.]

### Uncertain
- [Optional — hypotheses you couldn't verify, questions still open.
Risks are known dangers; this is honest doubt. Omit when empty.]

### Risks
- [What could go wrong with what we did, what could they trip up on?]

### Opportunities
- [Actionable pointers ONLY: directions for next session, the next piece of the puzzle. Include bon IDs where relevant.
This list IS the baton — the next session's hook surfaces it under "From the last handoff's Opportunities", trimmed to each bullet's FIRST SENTENCE, so lead with the point.
Deliberate-inaction records ("left alone on purpose", "deliberately not created") and unverified caveats belong in Risks or Uncertain, not here — under a suggestion-shaped label they read as invitations to act (bon-dokahi).
Don't write a separate Suggested section; that duplication is format drift.]

## For Claudes to come

[Knowledge that transcends the next session, written to stand alone.
This is what /open synthesizes into understanding.md — repo, craft, and
architecture knowledge belongs here, including how Claude's own functional
patterns played out in this work. Lessons that belong in the always-on
guidance corpus (a trap keyed on its discriminating command, a
verification-family instance) split by what the edit IS (ratified 2026-08-13,
bon-vinije). A NEW row defers to intake: file a bon item on the corpus's own
board (the operator's guidance repo — their accent's `close.personal` section
names it where one exists) carrying the proposed row text, or a
handoff candidate when no writer is reachable — because intake is the
corpus's only valve (append-only, no eviction pass) and close-time is the
documented worst moment for residence judgement (completion drive, token
pressure, the warm glow). A MECHANICAL CORRECTION of an existing entry — a
vocabulary row, a dead link, a value that changed — goes straight in: the
judgement was made at the original intake, and deferring a correction just
leaves the corpus wrong for longer. If a lesson is genuinely both, split it
rather than double-filing.
The test: would future Claudes benefit from knowing this?
If nothing qualifies, omit this section — filler dilutes understanding.md over time.]
```

#### Candidates (candidate mode only)

In candidate mode you can't mint on the board, so the handoff carries your intended
mutations as **candidates** — provenance-tagged proposals a writer-bearing `/open`
mints. Add this block inside "For the next Claude":

```markdown
### Candidates

<!-- Board visible, writer unreachable — a writer-bearing /open mints or drops each; unminted = wish. -->
Provenance: {vehicle, e.g. Cowork} session {session_id} — {YYYY-MM-DD}

- **NEW** action under `bon-PARENT` — "Title"
  - why: … / what: … / done: …   (how: … — optional)
- **DONE** `bon-xxxx` — "one-line reason"
- **EDIT** `bon-yyyy` — --how: "new text"
```

One line per mutation, with enough detail to mint without your context. Two worked
examples predate this spec and rode an "Opportunities — bon candidates" prose list;
the dedicated `### Candidates` heading is the same idea, structured so the next open
mints reliably instead of re-deriving the convention. Format spec (and the worked
examples' citations): `docs/HANDOFF-CONTRACT.md`.

#### Where does it go?

Handoffs live in the room's **visible `handoffs/`**, falling back to the board root's — git-tracked so they sync across machines. `close-context.sh` resolves this via the shared `scripts/lib-handoff.sh` — the same walk the next `/open` reads from, so a handoff always lands where the next one looks. (`.bon/handoffs/` was a rung until bon-sedoze; a repo still carrying a pile there has it migrated to the visible dir on the first open or close.) `HANDOFF_DIR` is usually right, but placement is a judgment you make, not only a cwd heuristic:

**Placement is work-based, not launch-based.** You know the primary room you worked in better than any cwd walk does — name it, and the resolver places the handoff in that room's `handoffs/`. "Launched at root" (a `claude agents @repo`, a Cowork folder-pick) is the worst case, not the target: a root-launched session that spent itself in one room still files there. Substrate-wide sessions file at the repo root.

| Situation | Handoff destination |
|-----------|-------------------|
| Session worked mainly in one room | That room's `handoffs/` (name the room; the resolver places it) |
| Substrate-wide session | The repo root's `handoffs/` (HANDOFF_DIR) |
| Work clearly belongs to another repo | That repo's `handoffs/` |
| Started in scratch/workbench | Ask the user — default to the repo where the session's bon items live |
| Candidate mode (Cowork mount) | The mount's visible `handoffs/` for the room worked — Write tool, no commit |

For cross-repo handoffs, check the target `handoffs/` exists first.

#### Filename

Use HANDOFF_FILE from the script output verbatim — it generates `YYYY-MM-DD-HHMM-{session-id-8}.md` (date+time prefix so same-day siblings sort chronologically under `ls`, session ID suffix for transcript linkage), and it has already checked that nothing sits at that path. Don't recompute it: the id comes from the harness, and deriving one yourself from what's on disk is the bug this guarantee replaced.

#### Ledger line — in the same change as the handoff

Append your handoff's line to `LEDGER.md` in the directory you wrote the handoff to (bon-supuko; the notes convention, now core). This is what lets the next `/open` sweep EVERY unprocessed handoff instead of just the newest — without your line, an interleaved close's baton is silently dropped by latest-wins. Format, newest first under the header:

```markdown
- [ ] {DATE} [{filename}]({filename}) — {purpose line}
```

The unticked checkbox means "not yet processed by an /open"; the sweep ticks it to `- [x] … (processed YYYY-MM-DD)` after synthesising and minting. No `LEDGER.md` there yet? Create it with your line and this two-line header — creating it is how a repo adopts the sweep:

```markdown
# Handoffs ledger

One line per handoff, newest first. `- [ ]` = not yet processed by an /open sweep; every close appends its line in the same change that writes the handoff.
```

**Adoption backfill — mandatory when the dir already holds handoffs.** The sweep treats a file with no ledger line as unprocessed, so a fresh one-line ledger beside 80 historical handoffs floods the next /open with the entire archive (measured on a replica: 13 files emitted, the real baton buried). Latest-wins already served that history — backfill it TICKED, below your own unticked line:

```bash
for f in <handoff-dir>/*.md; do b=$(basename "$f"); [ "$b" = LEDGER.md ] && continue; \
  echo "- [x] ${b:0:10} [$b]($b) — pre-ledger history (processed at adoption $(date +%F))"; done
```

(Skip the file you just wrote — your unticked line above covers it.)

Candidate mode included — the ledger append is a Write-tool edit, no CLI needed, and the candidate-bearing handoffs are exactly the ones the sweep must not drop. A repo with its own richer ledger convention (prose-heavy lines, extra columns): keep its register, but lead the line with the checkbox so the sweep can see it.


### Cold eyes on the handoff (bon-dimadu)

Before committing, hand the finished handoff to one fresh-context subagent. Every other claim in this rite was checked by the session that made it; the handoff is written *after* all of that, so nothing has ever read the finished artefact cold — and its Opportunities section is the baton the next session's hook puts in front of whoever opens. Measured on 2026-08-30: one such read returned 19 findings on a single file, none of them fabrication.

**The bar is always** (Sameer, 2026-08-31), skippable only with a reason you state in the close summary — "the handoff is four lines and cites nothing" is a fine reason; "the session went smoothly" is not one, because a smooth session is exactly where an unchecked claim slides through.

Give the reader the whole file and a narrow brief. The measured failure class is specific, so name it rather than asking for scepticism in general:

> Read this handoff as the next Claude, who has none of the writing session's context and all of its responsibility. Three questions. (1) What here would mislead you — quote the sentence and say what you would wrongly believe. (2) What did that session evidently know that is missing — name the gap, not a wish. (3) Read each Opportunities bullet's FIRST SENTENCE ALONE: the session-start hook trims them to that, so a bullet whose first sentence misleads in isolation is broken however good the rest is. Also flag any finding stated without a verdict, and any next move stated without an owner. If nothing would mislead you, say so and list what you checked — an examined all-clear is a real answer, and inventing a finding to look useful is worse than none.

Two things make that prompt hard to rubber-stamp, and both are deliberate. It asks for artefacts a bare agreement cannot produce — a quoted sentence, a named gap, an owner — so "looks good" does not fit the shape of the ask. And it licences an honest all-clear, so the reader is never pushed into manufacturing findings to justify itself.

Then fold what lands. A finding you accept gets fixed in the file before the commit; one you reject gets a sentence in the close summary saying why, because "the cold reader raised X and I disagreed, for Y" is itself useful to the next session. Keep the reader on a peer-quality model — a cheaper verifier than the writer is the rubber stamp this step exists to avoid.

### Net board motion (bon-racafo)

Once the board work is done — the Now items, the new bons filed, anything knocked out and `bon done`'d — re-derive the tally and state it in one line:

```bash
# Pass the bare timestamp only — not the parenthesised gloss beside it.
"$BON_SCRIPTS/close-context.sh" --motion-only "<the timestamp the full run printed, e.g. 2026-08-31T11:48:00>"
```

Re-derive rather than reusing the Orient figures: this rite *mints and closes items after the context script ran*, so the earlier numbers are stale in exactly the direction that matters. The window is since the previous close, not since this session started — wider on purpose, because per-session windows leave motion nobody counts. Where you can see some of it wasn't yours, say so.

Then one line, using the script's numbers and naming the ids:

> Board motion since the last close: closed 3 (bon-a, bon-b, bon-c), minted 2 (bon-x, bon-y), 2 carried forward.

**Minting is capture, not debt.** A session that files five discoveries and closes two did its job — chasing them instead would have been the error. `MOTION_CARRIED` is the honest growth figure, since a card minted and closed within the window never touched the backlog. So there is no target here and nothing to optimise: the line exists so board growth is visible now rather than surfacing weeks later when a review ceremony trips over it (2026-08-30: 13 closed, 11 minted, one line that reframed the whole review conversation).

Report what the script printed. It computes from `bon log` precisely so the figure isn't yours to shade, and naming the ids makes what you *did* file auditable at a glance. Be clear about the limit, though: the tally counts board items, so a discovery you never filed at all has no id and leaves no gap — nothing here can see it. That one is guarded by the triage step above and by capturing generously, not by this line.

If the script prints `MOTION_ERROR` or `MOTION_TRUNCATED`, say that instead of a number you'd have to guess at.

### Commit and go

Stage relevant files (including the handoff), commit in modular commits with descriptive messages, and offer to push. Each commit cites the bon it serves — trailing `(bon-ID)` in the subject or body — when the work was tracked; untracked work commits without one. If nothing's dirty, just move on — not every session produces code changes.

**If the context script reported `HANDOFF_MIGRATED=<n>`:** this repo's handoffs have just moved out of the retired `.bon/handoffs/` into the visible `handoffs/`. Stage that move alongside your own changes — for tracked files `git mv` already staged the rename, but a repo that gitignored `.bon/` had an untracked pile, which now needs a plain `git add` of the new directory. Say it happened in one line; a reader seeing their handoff history change path deserves the reason.

**Candidate mode has no commit step.** There's no writer and usually no git in the sandbox — the handoff you wrote to the mount *is* the deliverable, and a writer-bearing session sweeps and mints its candidates at the next open. Leave it uncommitted; say so, so the next full-fat session knows to look.

**If the context script reported `WORKTREE_SESSION=true`:** this session's branch — commits and the handoff you just wrote — is deleted with the worktree. Push, merge, or open a PR before declaring the session closed; say what would be lost (`git log @{u}..HEAD` count) if the user wants to skip it. (JSONL-backed bons filed this session live in the worktree's copy too; Dolt-backed bons are safe — they write over the network.)

Then: "Type `/exit` to close."

