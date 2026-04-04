---
name: close
description: "Run before /exit, to reflect on this session and figure out what's best to (1) get done now, with current context wisdom (2) file as a handoff for the next Claude as well as (3) what wisdom to capture for future Claudes in collective memory. Ends with a commit."
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

---

## Reflect

This is the heart of /close. You're reviewing the session — what to finish now and what to hand forward. You need to try and step back from what's happened and look at it with fresh eyes. Think about future Claudes and how you can help them best, by asking yourself these reflective questions:

1. **What did we miss?** — Things we should have done but didn't: docs we should have updated, decisions we should have documented, tests we should have written, assumptions we should have verified
2. **What could we have done better?** — Better can be many things, but for us it's about being more elegant, more maintainable, more robust, more consistent and yes, more creative.
3. **What could go wrong in future?** — Race conditions, silent failures, fragile dependencies, implicit knowledge not written down, non-obvious relationships between files

Even if it's been a long slog of a session, here, at the finish line, please answer these questions deeply, honestly and openly, as if you'd been asked them directly by the user, or perhaps by a future Claude. Share your knowledge. 

### Propose a plan

The principle here is always to do today what you could do better than another Claude tomorrow that lacks your context. Please don't brush things off as problems for another Claude or another repo. Doesn't matter if it's 'not a regression' - we have cabinet responsibility.

Look at everything that's emerged from your reflection and sort it into these buckets:

1. **Now** — things it would be best for you to do before /exit because you have the context:
- Small completions (under 5 minutes)
- Quick fixes where something is broken - even if they are in other repos, or were pre-existing problems
- Closing off existing or superseded bon items with `--note`

2. **Later** — tasks for a future session - which should be nested under Outcomes per the Bon skill
- Bigger things that need a fresh session - you know what needs doing, but it would need a different context load
- Refactoring of Bons where you see a different path forward given the session's learnings
- Things into which you have gained understanding which need further attention, even in other repos

3. **For Claudes to come** - what one thing did you learn or discover that should be contributed to the stock of future Claude understanding; an architectural insight, a taste judgment, a decision with real alternatives, a mistake not to be repeated, a trick you discovered which would save us significant time. A shard of wisdom gleaned.

Propose these to the user:

> "Here's how I suggest we close out:
>
> **Things to do now:** [concrete list]
>
> **Bons to file for next:** [each with what's at stake]
> 
> **Insight to capture for the future:** [Write a short prose fragment - one dense paragraph]
>
> What do you think?"

Be systematic: for each reflection, ask yourself whether there's a concrete action. If the answer is yes, it goes in Now or Later — don't leave it as an observation without a follow-through. Your job is to surface what you noticed and what's at stake. The user decides what's worth tracking — don't filter on their behalf.

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

