# Field Report: Plan → Bon Transcription

**Filed by:** Claude (Opus 4.6), 7 Apr 2026
**Context:** Transcribing a detailed implementation plan (Écoute permission handling, 5 actions under 1 outcome) from a plan file into bon items.
**Related bon:** bon-gikucu

## What happened

I had a thorough plan file (~200 lines) covering a new PermissionChecker for Écoute. The plan had: Context (why), Approach (how), File Changes (4 sections with exact code), Pitfalls to Avoid (6 items), Observation Framework Note, and Verification Steps.

On the first pass, I created 5 actions using `--why`, `--what`, and `--done`. I didn't use `--how` on any of them. Everything got crammed into `--what`. The bons were not self-contained — they said things like "See plan for exact check implementations" which is a broken cross-reference.

Sameer noticed that `--how` exists and asked why I didn't use it. The honest answer: I forgot it was there. The CLI only errors on missing `--why`. Once I was composing `--why` and `--what` (both required), I had momentum and `--how` wasn't in my working set.

On the second pass, I redistributed: `--what` became the deliverable description, `--how` became the implementation detail (exact code patterns, line numbers, imports, pitfalls). The bons became self-contained.

## The --what gravity well

`--what` attracts everything because:
1. It's required — you must write it every time, so you're already composing there
2. It's semantically broad — "what will we produce" can mean the deliverable OR the implementation detail
3. `--how` is optional — the CLI never prompts for it, never warns about its absence
4. When `--what` gets long, you don't stop and think "should some of this be --how?" — you keep writing

The result: `--what` carries both "what are we building" and "how are we building it", making it hard to scan. The `--how` field stays empty, and the brief reads as a wall of text under one heading.

## What was hard to fit anywhere

Even with `--how`, some plan content has no natural bon field:

- **Pitfalls / constraints** ("don't import Combine", "use [weak self]", "HotkeyMonitor has no double-start guard"). These are negative instructions — things NOT to do. I embedded them as "PITFALLS:" sections at the end of `--how`, which works but feels like a workaround.

- **Cross-action dependencies** ("ec-lebidi depends on ec-lizowu existing first"). Bon has `--order` for display ordering, but no explicit dependency tracking. I used ordering to imply sequence, which is fragile.

- **Verification steps** ("build with ./build.sh, run swift run EcouteTests, manually test on Mac"). These live in the plan's Verification section. They don't belong on individual actions (too granular) or on the outcome's `--done` (which is the completion criteria, not the test procedure). I put the Mac-specific verification on ec-vacafe but the build/test verification has no home.

- **Architecture notes** ("Observation tracks through nested @Observable automatically — don't add extra plumbing"). I put this on the action where it matters most (ec-lebidi), but it's really a cross-cutting concern that applies to multiple actions.

## Suggestions for improvement

### 1. Prompt for --how when --what is long

When `--what` exceeds ~100 characters and `--how` is empty, bon could suggest: "That's a detailed --what. Should some of it be --how (approach/strategy)?" This is a nudge, not a requirement. It interrupts the gravity well at the right moment.

### 2. Structured plan import

A `bon import-plan <plan-file>` or `bon new --from-plan <plan-file>` command that:
- Reads a markdown plan file
- Extracts sections and maps them: Context → outcome --why, Approach → outcome --how, each "File change" section → an action, Verification → outcome --done or a final action
- Creates the outcome + actions in one pass
- Lets you review and edit before committing

This is the higher-effort, higher-value option. The plan file format is fairly consistent (Context, Approach, File Changes, Verification) and could be parsed with reasonable heuristics.

### 3. Surface --how more prominently

`bon show` currently renders `--how` identically to `--why` and `--what` — just another labelled line. If `--how` were visually distinct (indented differently, or collapsible in a future TUI), it would reinforce that it's a separate field with a distinct purpose. Right now the four brief fields blur together.

### 4. Consider a --constraints or --pitfalls field

Negative instructions ("don't do X because Y") are common in implementation plans and don't fit naturally in --how (which is positive: "do X this way"). A dedicated field for constraints would give them a home. Alternatively, a convention within --how (like the "PITFALLS:" prefix I used) could be documented as a pattern.

### 5. Consider --verify on outcomes

A `--verify` field on outcomes would capture the test/verification procedure that currently has no home. Distinct from `--done` (which is the success criteria) — `--verify` is "how to confirm --done is met."

## Meta-observation

The four-field brief (why/how/what/done) maps well to the "problem → approach → deliverable → acceptance" structure. The issue isn't the model — it's the CLI ergonomics. Required fields get filled; optional fields get skipped. When the optional field is the one that carries implementation detail, the bons become shallow task descriptions rather than self-contained work packets.

The second pass (with --how populated) produced bons that a context-free Claude could execute without the plan file. That's the quality bar to aim for.
