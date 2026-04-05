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

The script outputs TIME, GIT, BON, LOCATION context, plus two values you'll need in Act: **HANDOFF_DIR** and **SESSION_ID**.

Before continuing, check where you are: compare `pwd -P` with the Working directory in your system prompt. If they differ, `cd` back. If the session started in a folder called 'scratch' or 'chat' but the work belongs elsewhere, note the target repo — you'll route the handoff there in Act.

If CWD has no `.git/` directory but contains code files (`.py`, `.ts`, etc.), suggest: "This directory has code but isn't a repo — `/scaffold` can wrap proper structure around it (adopt mode)." Don't auto-invoke; just surface the option.

---

## Reflect

This is the heart of /close. You're reviewing the session — what to finish now and what to hand forward. You need to try and step back from what's happened and look at it with fresh eyes. Think about future Claudes and how you can help them best, by asking yourself these reflective questions:

1. **What did we miss?** — Things we should have done but didn't: docs we should have updated, decisions we should have documented, tests we should have written, assumptions we should have verified
2. **What could we have done better?** — Better can be many things, but for us it's about being more elegant, more maintainable, more robust, more consistent and yes, more creative.
3. **What could go wrong in future?** — Race conditions, silent failures, fragile dependencies, implicit knowledge not written down, non-obvious relationships between files

Even if it's been a long slog of a session, here, at the finish line, please answer these questions deeply, honestly and openly, as if you'd been asked them directly by the user, or perhaps by a future Claude. Share your knowledge. 

### Generate actions from your reflections

Now turn your reflections into a plan. Like Newton II, most of your observations will imply an equal and opposite action — name it. Here's what that inversion looks like in practice:

> **Reflection:** "We updated the handoff template but the SPEC.md still describes the old format."
> → **Now:** Update SPEC.md (5 min, have the context)
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

The principle is: don't put off to another Claude something that you could do better because of your insight. Don't brush things off as 'some-other-Claude's problem. Doesn't matter if it's 'not a regression' —  it may be a long time until another Claude comes this way again, and we have cabinet responsibility to leave things better than we found them. 

### Triage before sorting

Before you sort, force each observation through a table. This prevents two failure modes: vague reflections without consequences (which can't be triaged) and reflexive action-generation without examining whether action is actually warranted.

| # | Reflection | Consequence | Remedy | When |
|---|-----------|-------------|--------|------|
| 1 | No input validation on POST endpoint | Malformed requests → 500 instead of 400; confusing for future Claudes debugging | Add guard, return 400 with message | Do now |
| 2 | Magic number in sync loop instead of shared constant | One side breaks silently if prefix changes | Extract constant to shared module | Do now |
| 3 | Auto-discovery silently picks first room when multiple active | User doesn't know where their comment went | Print selected room name | Do now |
| 4 | Resolve endpoint doesn't scope to room | Semantically misleading URL; subtle bugs when more surfaces consume it | Add WHERE clause to scope resolve | File as Bon |
| 5 | Sends session_id that server ignores | Dangling intent — but removing means re-adding later | Leave it; field is harmless and the intent is documented | Chill |

The three timing categories are **do now**, **file as bon**, and **on reflection, chill**. The third is the most important — it gives you permission to notice something without manufacturing work for it. "Chill" is an examined conclusion, not a lazy omission. Present the table to the user grouped by timing — it's their review surface. They may promote or demote items.

**Consistency check:** Your Remedy and When columns must agree. If Remedy names a concrete action (file a bon, add a guard, update docs), When must be Do now or File as Bon — not Chill. Chill means "examined and genuinely no action needed." A Remedy that describes work paired with a When of Chill is a contradiction — you've talked yourself out of your own recommendation between two columns. In practice, user corrections at this step are almost always upgrades (chill→bon, bon→do now), never downgrades. If you're uncertain, err toward action — the user can always demote, but items you default to Chill tend to disappear entirely.

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

Propose these to the user:

> "Here's how I suggest we close out:
>
> **Things to do now:** [concrete list of remedies implied by your reflections]
>
> **Bons to file for next:** [list of future work with an explanation of what's at stake]
>
> **Insight to capture for the future:** [one dense paragraph to contribute]
>
> What do you think?"

Your job is to surface what you noticed and what's at stake. The user decides what's worth tracking — don't filter on their behalf.

Wait for approval or adjustment before doing anything.

---

## Act

### Do the "Now" work

Work through the list. Finish the quick fixes, close off completed Bon items - generally leave things how you'd like to find them.

### File the new bons

When filing bons, the `--why` should say what goes wrong if nobody picks this up — not just describe the work. Use `bon new --json` for anything with technical content. Make sure to capture enough detail in the `--how` that a future Claude could pick it up and execute without your context load. The richer the better. 

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

### Risks
- [What could go wrong with what we did, what could they trip up on?]

### Opportunities
- [Directions for next session, what's the next piece of the puzzle? Include bon IDs where relevant]

## For Claudes to come

[Knowledge that transcends the next session, written to stand alone.
This is what /open synthesizes into understanding.md 
The test: would future Claudes benefit from knowing this?
If nothing qualifies, omit this section — filler dilutes understanding.md over time.]
```

#### Where does it go?

Handoffs live per-repo in `.bon/handoffs/`, git-tracked so they sync across machines. The script walks up from CWD to find the nearest `.bon/` — that's usually right, but not always:

| Situation | Handoff destination |
|-----------|-------------------|
| Normal session in a project | HANDOFF_DIR (the default) |
| Work clearly belongs to another repo | That repo's `.bon/handoffs/` |
| Started in scratch/workbench | Ask the user — default to the repo where the session's bon items live |

For cross-repo handoffs, check the target `.bon/handoffs/` exists first.

#### Filename

Use HANDOFF_FILE from the script output — it generates `YYYY-MM-DD-{session-id-8}.md` (date-prefixed for chronological `ls`, session ID suffix for transcript linkage).


### Commit and go

Stage relevant files (including the handoff), commit in modular commits with descriptive messages, and offer to push. If nothing's dirty, just move on — not every session produces code changes.

Then: "Type `/exit` to close."

