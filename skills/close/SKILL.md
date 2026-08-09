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
Act           → execute, craft handoff, commit → overnight Claude reviews
```

---

## Orient

Find the close-context script and run it. This gives you the raw material for the rest of the process.

```bash
BON_SCRIPTS=$(ls -td ~/.claude/plugins/cache/*/bon/*/scripts 2>/dev/null | grep -v '/skills/' | head -1)
"$BON_SCRIPTS/close-context.sh"
```

If the script isn't found, diagnose with `find ~/.claude/plugins/cache -name "close-context.sh"`. If unfixable, gather context manually — but closure should always result in a handoff, even without the script.

The script outputs TIME, GIT, BON, LOCATION context, plus the values you'll need in Act: **HANDOFF_DIR**, **SESSION_ID** and **HANDOFF_FILE**. Four companion keys appear only when they apply, and each one changes what you do:

| Key | Meaning | What to do |
|---|---|---|
| `SESSION_ID_SOURCE=unavailable` (with `SESSION_ID_CUE`) | The harness gave no session id, so the filename carries a timestamp | Leave `session_id:` blank in the frontmatter and say so in the close summary. Never substitute an id you inferred — the suffix exists for transcript linkage, so a wrong one sends a future reader into a stranger's conversation |
| `HANDOFF_FILE_TAKEN=<name>` | The natural filename was already on disk; `HANDOFF_FILE` is suffixed | Normally just use the suffixed name — it means this session is closing twice today. Worth a sentence if you weren't expecting it |
| `HANDOFF_GITIGNORED=true` (with `HANDOFF_ADD_CMD`) | The handoff lands under a gitignored `.bon/`, so a plain `git add` will refuse | Use `HANDOFF_ADD_CMD` verbatim at the commit step and say you had to |
| `HANDOFF_DIR_SOURCE=global-fallback` | No board was found, so the handoff goes to `~/.bon/handoffs` | It won't sync anywhere. Say so, and consider whether it belongs on a real board instead |

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

### Toolmaking tap — compass out

Before proposing the close-out, read Sameer's dispatch queue and check the session against it. Gate and failure mode as in /open's compass: skip only when `accomplis` is absent; unreachable renders as "not shown", never silence.

```bash
accomplis tasks --project "& Toolmaking" 2>/dev/null
```

Three checks, rendered as one 🧭 block inside the close-out proposal:

- **Tickable:** queue lines whose work this session completed — name them; he ticks by hand on his phone.
- **Propose-and-add (sanctioned, tell-after):** when a clean case exists — a queue line's bon closed with an obvious successor, or the session minted dispatch-shaped work he ranked — ADD the line (`accomplis add "Open <repo> → <desire> (<bon-id>)" --project "& Toolmaking"`) and TELL him in the block: "added: …". Never ask first; never add speculative lines — clean cases only, his grammar, his grain. (Norm: Sameer, 2026-08-09 review ceremony — "I'd like you to tell me, but doing it is fine"; recorded in bon-leturo's `--how`.)
- **Stalling:** a queue line pointing at a board with no motion for 30+ days — one nudge, max one.

The tap reads and, only in the propose-and-add case, writes single dispatch lines. It never edits or completes his tasks, never touches other projects — Todoist stays his book (the kuwivo treaty-table rule).

Propose these to the user:

> "Here's how I suggest we close out:
>
> **Things to do now:** [concrete list of remedies implied by your reflections]
>
> **Bons to file for next:** [list of future work with an explanation of what's at stake]
>
> **Empty outcomes:** [only when Orient flagged any — per outcome: break down now, file a first action, or confirm it's intentionally a sketch]
>
> **🧭 Toolmaking:** [tickable lines · lines added under the norm · the one stall nudge — or "unreachable, not shown"]
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

### File the new bons

When filing bons, the `--why` should explain what's at stake — not just describe the work. Use `bon new --json` for anything with technical content. Capture enough detail in the `--how` that a future Claude could pick it up without your context load.

For cross-repo issues: file a bon in the relevant repo rather than making changes there. Cabinet responsibility means noticing and capturing, not committing in repos where you may not have the full picture.

### Craft the handoff

Now write the handoff. This is where your reflections become concrete - where you step back and capture what actually mattered. Write as if the reader will have none of your context and all of your responsibility.

Your handoff has two specific audiences.

1. There is the immediate next Claude to whom you are passing the baton. Point out where they should go next. Get them off to a flying start. It's your final message to them. 

2. Then there are the background processes which will run overnight to incorporate and index your learning and insight into the collective memory. The bits that will live on. 

#### Template

```markdown
# Handoff — {DATE}

session_id: {SESSION_ID}
purpose: {one line — what the session was for}
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
verification-family instance) route differently: don't edit that corpus
mid-close — it's a live-config repo, one writer at a time. File a bon item
on the corpus's own board (in this estate: ~/.claude) carrying the proposed
row text, or a handoff candidate when no writer is reachable. If a lesson is
genuinely both, split it rather than double-filing.
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

One line per mutation, with enough detail to mint without your context. This is what
the two worked examples did (`~/notes/handoffs/2026-06-10-7c379a74.md`,
`2026-06-12-804b6ba8.md`) — their candidates rode an "Opportunities — bon candidates"
list in prose; the dedicated `### Candidates` heading is the same idea, structured so
the next open mints reliably instead of re-deriving the convention. Format spec:
`docs/HANDOFF-CONTRACT.md`.

#### Where does it go?

Handoffs live in the room's **visible `handoffs/`** (falling back to `.bon/handoffs/`), git-tracked so they sync across machines. `close-context.sh` resolves this via the shared `scripts/lib-handoff.sh` — the same walk the next `/open` reads from, so a handoff always lands where the next one looks. `HANDOFF_DIR` is usually right, but placement is a judgment you make, not only a cwd heuristic:

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

Use HANDOFF_FILE from the script output verbatim — it generates `YYYY-MM-DD-{session-id-8}.md` (date-prefixed for chronological `ls`, session ID suffix for transcript linkage), and it has already checked that nothing sits at that path. Don't recompute it: the id comes from the harness, and deriving one yourself from what's on disk is the bug this guarantee replaced.


### Commit and go

Stage relevant files (including the handoff), commit in modular commits with descriptive messages, and offer to push. Each commit cites the bon it serves — trailing `(bon-ID)` in the subject or body — when the work was tracked; untracked work commits without one. If nothing's dirty, just move on — not every session produces code changes.

**If the context script reported `HANDOFF_GITIGNORED=true`:** the repo ignores `.bon/` wholesale to keep volatile board state out of git, which catches the handoff too. A plain `git add` refuses and the handoff is written to disk but never syncs — so the next session on another machine cannot see it. Stage it with the `HANDOFF_ADD_CMD` the script printed (`git add -f -- <path>`), and check whether `understanding.md` needs the same treatment. Say that you had to force-add: it's a property of that repo worth surfacing, not a detail to absorb silently.

**Candidate mode has no commit step.** There's no writer and usually no git in the sandbox — the handoff you wrote to the mount *is* the deliverable, and a writer-bearing session sweeps and mints its candidates at the next open. Leave it uncommitted; say so, so the next full-fat session knows to look.

**If the context script reported `WORKTREE_SESSION=true`:** this session's branch — commits and the handoff you just wrote — is deleted with the worktree. Push, merge, or open a PR before declaring the session closed; say what would be lost (`git log @{u}..HEAD` count) if the user wants to skip it. (JSONL-backed bons filed this session live in the worktree's copy too; Dolt-backed bons are safe — they write over the network.)

Then: "Type `/exit` to close."

