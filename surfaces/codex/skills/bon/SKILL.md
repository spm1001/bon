---
name: bon
description: Use Bon to open or close a work session, maintain outcomes and next actions, resume a handoff, or operate an existing Bon board. Supports the installed CLI and shared Dolt boards without assuming Claude lifecycle hooks.
---

# Bon for Codex

Bon owns durable commitments. Use outcomes for desired results and actions for concrete next steps; preserve an existing hierarchy rather than creating a parallel plan file. This skill provides the portable session workflow. It does not install hooks or claim that transcript capture ran.

## Orient and select work

Confirm hostname, working directory and the repository that owns the requested work. Resolve its Git root with `git rev-parse --show-toplevel`, then run the installed `bon` CLI with that repository root as the tool's working directory. Bon discovery can stop at a nearer `.git` boundary even when Git itself resolves the enclosing repository. Do not initialise a new board merely because a command from a subdirectory could not find the existing one.

Read the owning `.bon/README.md`, project/room understanding and the handoff routed by the project. Run `bon list` and `bon show ID` for the chosen work. Present relevant outcomes, next actions and uncertainty in plain language, including locations when they matter. An explicit focused continuation need not become an estate-wide opening sweep.

For a full opening, process the relevant handoff ledger's unprocessed entries in order, including unlisted handoffs where the existing convention requires it. Integrate durable knowledge into the maintained understanding file and adjudicate any Candidates against the live board. Mark a candidate minted or a ledger entry processed only after its work is actually handled. Without a ledger, use the established latest-handoff route. Preserve plan-seeded reasoning when maintaining understanding.

Before executing an older brief, check its named artifacts, the tail of its approach for supersession or another lane's claim, and the already-loaded hierarchy for overlapping work. This is a short staleness check, not a new investigation. Re-brief routine factual drift and proceed; a changed human objective needs the specific missing decision.

On a Dolt board, query the CLI; a leftover items.jsonl is not the board. Distinguish a sandbox/network denial from an actual server outage before changing a service. Use the available escalation/reviewer route for authorised network access. On a JSONL board, account for upstream staleness before writing; a robot-owned repository remains the robot's to synchronise.

## Plan and maintain commitments

Use JSON stdin for rich `bon new` and `bon edit` briefs. Never hand-edit board storage. A brief needs why, what and done; how carries the approach and constraints. Record the reason for a significant choice so a later session can resume the reasoning. Read CLI help for a flag you have not verified on the installed version.

The outcome falsifier (`badly`) belongs to the human. Carry existing wording verbatim; do not invent one to fill a field or ask again when it is already recorded. Check for existing work before creating another item. Keep source changes and their board references linked; commits for tracked work cite the relevant Bon ID.

For tactical steps, read `bon work --status` before claiming or advancing anything. The installed CLI's identity is the board root (hostname plus realpath for Dolt), not a unique Codex session: two sessions in one checkout can see the same claim. Advance only the work you actually own. Use `bon step --expect N` for the step you verified; if the guard fails, reread instead of guessing. The final step normally completes the action, so use `--no-complete` while acceptance work remains. `bon work --release` preserves progress; clearing discards it. Do not force or clear another session's claim.

Mark done with evidence of the requested result, not just a successful command. Use waiting-for or someday semantics when appropriate, preserving other blockers. If the board is unreachable, write provenance-tagged NEW/DONE/EDIT Candidates in the handoff for a later writer; do not pretend they are already tracked.

## Close and hand over

Recheck the worktree and relevant live items. Finish small authorised follow-through, record discoveries and unresolved decisions, and leave an actionable handoff. Keep current status on Bon, durable knowledge in understanding, and evidence where another reader can find it. Do not claim a clean checkout, committed work or completed acceptance without checking.

Use the existing visible room or repository `handoffs/` directory and ledger. Preserve the legacy section markers `## For the next Claude` and `## For Claudes to come` when writing for existing consumers: these are parsing contracts, not claims that the writer is Claude. Record Codex honestly in metadata. Use the actual `CODEX_THREAD_ID` when supplied by the runtime; if unavailable, say so rather than inferring identity from the newest transcript. Include the work's purpose, relevant item IDs, host/repository/paths, verification, uncertainties, the next action and who owns it. Keep reasons and relational context that matter to continuation.

The maintained [handoff contract](../../../../docs/HANDOFF-CONTRACT.md) specifies metadata, ledger and Candidates details; read the relevant part when writing or processing a handoff. Append the ledger entry with the handoff and leave it unprocessed for the next reader. Never mark other sessions' handoffs processed merely because their files exist.

Do not invoke Claude's close-context scripts, write its oriented-state breadcrumbs, export invented Claude identity variables, or imply that Claude's capture hooks ran. Codex transcript ingestion and backups require their own qualified adapter. Notes-sync owns Git writes in the notes repository; authorised Markdown edits do not authorise commits, pushes, resets or rebases there.

These procedures cover common cases. Reason from their purposes when the situation differs, preserving explicit ownership and side-effect boundaries rather than treating examples as exhaustive.
