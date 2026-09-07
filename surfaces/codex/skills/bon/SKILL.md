---
name: bon
description: Use Bon for opening, planning, closing, backlog review, or work on an existing Bon board. Runs the maintained Bon rites with explicit Codex runtime substitutions, preserving their reflection, user review, personal routing and durable follow-through.
---

# Bon in Codex

Bon has one set of rites. This file adapts their execution to Codex; it does not replace them with a shorter workflow. Preserve the actions and the human review surfaces even when the tool names and runtime mechanics differ. Use the user's current instructions and existing authorization throughout.

## Read the matching rite

Resolve this installed skill's real filesystem path first. Its Bon repository root is four parents above the skill directory. The source links below are relative to that directory; resolve them from the real path, not the process working directory. Read the matching original skill before acting, and follow its phases with the substitutions below. Reuse a rite already read in this session unless it changes. Do not load all four for a simple command.

| User's intent | Maintained procedure | Result to preserve |
|---|---|---|
| Open, resume, choose work, operate a board | [Open](../../../../skills/open/SKILL.md) | Routed knowledge and candidate synthesis, visible hierarchy, personal queue glance where configured, deliberate direction and guarded draw-down |
| Plan multi-session work | [Plan](../../../../skills/plan/SKILL.md) | Architectural framing, outcomes that narrate the desired change, rich actions, human-owned falsifier, verification against existing work |
| Close, wrap up, finish the session | [Close](../../../../skills/close/SKILL.md) | Reflection and proposals for review, personal reconciliation, approved Now work, durable future commitments and knowledge, checked handoff and completion report |
| Review or triage the backlog | [Review](../../../../skills/review/SKILL.md) | Survey, independent verification, proposed verdicts/repricings, human adjudication, applied decisions and before/after record |

`/open`, `/close`, `/plan` and `/review` in a user message express these intents; this skill does not register native slash commands. Routine board edits do not require a new full opening when the project is already oriented. A focused continuation can stay focused, but absence of a hook is not a reason to omit the relevant opening actions.

If the linked source is missing, locate the owning Bon checkout or installed Bon package. Report a missing source if it cannot be found; do not quietly reconstruct the rite from memory. This surface is installed with its source checkout, not as a standalone copied SKILL.md.

## Translate the runtime, preserve the work

The original rites were written for Claude. Apply these substitutions wherever they name Claude tools, hooks or metadata. They are execution differences, not permission to skip a phase.

- **Files and commands:** use the available filesystem and execution tools. Set each command's working directory explicitly to the owning repository root; a previous `cd` does not persist. Use `uv` for Python workflows. For a source rite's `${CLAUDE_SKILL_DIR}`, substitute that original rite's resolved directory, not this adapter's directory. Read referenced supporting files only for the stage being executed.
- **Source delivery:** distinguish instructions in the starting context from files read later. Explicitly read project routing and the selected room's material. Do not assume `@import`, on-Read injection or SessionStart delivered it.
- **Opening context:** after selecting the project or room, run `bash <resolved Bon root>/scripts/open-context.sh --read-only <selected directory>`. This reuses Bon's collector without its legacy migration or Claude cache writes. It reports host, launch/selected/repository/board paths, the nearest handoff scope and ledger, pending handoffs, knowledge/routing pointers and board-read status. Wider handoff directories are labelled separately; use `--scope board` for an intentional broader opening, not automatically for a focused room continuation. Read the reported source files and full live hierarchy as the Open rite requires; previews are not complete reads or completed synthesis. A failed board read is explicit, not an empty board. Check Git state and actual runtime session identity separately. This is an assistant-invoked command, not a registered startup hook.
- **Closing context:** derive the required observations through ordinary read-only calls. Do not execute the default (non-read-only) `open-context.sh` or the Claude `close-context.sh`, whose runtime and side-effect assumptions have not been qualified for Codex. Existing small CLI/survey helpers may be reused after checking their entrypoint and inputs. Missing helper output means derive its information directly, not omit its purpose.
- **Identity and arrival:** use the runtime's actual `CODEX_THREAD_ID` when supplied; otherwise say identity is unavailable. Never infer it from the newest transcript or export a fabricated Claude ID. Give a brief host/repository/board/location view in conversation in place of Claude's oriented-state breadcrumb. Do not write Claude statusline/session files.
- **Tactical progress:** manually read `bon work --status` before claiming and when returning to tracked work. The CLI identity is board-root based (hostname plus realpath on Dolt), not a unique Codex conversation: another session in the same checkout can share the visible claim. Read the brief, staleness evidence and routed baton; advance only work you own with `bon step --expect N`. A failed guard calls for a reread. Use `--no-complete` while acceptance remains. Release preserves progress; clear discards it. Do not clear someone else's claim.
- **User review:** present concrete proposals and preserve the original point where the user can promote, demote, amend or drop them. Prior approval still counts: do not re-ask for already authorized work or turn small agreed fixes into additional permission rounds. A new proposed commitment is not an accepted one. When user judgement is still needed, say which decision remains and wait for it; elapsed time does not settle it.
- **Independent reviewers:** where the source rite asks for a verifier or cold reader, use an available subagent with the bounded task, appropriate capability, and the source's evidence/coverage discipline. Translate the role's task rather than inventing unavailable model or harness settings. If that facility is unavailable or prohibited, do a bounded self-check and explicitly report independent review as unavailable; never label it a cold read. A partial report is not a completed review.

## The personal half is explicit, not hook-dependent

At the selected rite's personal variation point, check the user-configured accent path. If none was supplied, check the established `~/.claude/mit-accent.md` directly; its directory name is a legacy location, not a requirement to run Claude. Extract and read the relevant `## open.personal`, `## close.personal`, `## plan.personal` or `## review.personal` section before following any of its file or integration routes. Read additional sections only when the selected one explicitly relies on them; do not print the whole accent as a shortcut. Do not create a parallel Codex accent or import the rest of the Claude corpus.

Follow [the accent contract](../../../../docs/ACCENT.md): absent means silently complete without it; an unreadable or failing configured half gets one plain line, not a false empty result. The accent fills its designated stage. Honor its recorded user sanctions within their scope and the current session's authorization; confirm the account before integration work. Do not reinterpret tell-after sanctions as ask-first solely because this is Codex. Conversely, tool availability does not extend a sanction to another project or account.

For a dispatch queue, preserve lane/order semantics and read task descriptions before acting: they can contain holds or a second work item. Report the actual permitted reconciliation, or that it could not be shown. A queue read is not a queue write, and neither is evidence that a board item is complete.

## Closing is reflection followed by action

Read and run the original Close rite; this section highlights the observed omission, not an alternative abbreviated close.

Before declaring the session closed, bring the user the source rite's table: **Reflection → Consequence → Remedy → When**, grouped by **Do now**, **File as Bon**, and **Chill**. Include genuine observations from the work, changed assumptions and cold-start documentation, not a quota of invented improvements. Give concrete destinations for later work and the insight worth keeping. Run the configured personal read-back at its proper point. The user can change each proposed disposition.

Execute the accepted remedies. File durable, actionable commitments on their owning existing boards, checking for overlap first; then finish the small approved work that still fits the context and mark it done with evidence. Respect a project whose content or human tasks have a different owner; do not force those into its substrate Bon board. Keep unresolved judgement and examined no-action conclusions as such, without converting either into a silent task or a false completion. Already-authorized Now work can proceed without another approval round.

Write and check the handoff using the original cold-read discipline. Re-derive board motion after mutations, using `bon log` and the relevant previous-close window; increase the log limit if needed to cover that window. State closed, minted and carried-forward items with IDs, distinguish others' work, and disclose an incomplete window instead of inventing a tally. If a script depends on Claude transcript formats, this CLI/manual derivation replaces the script. Report personal queue actions, review findings folded/rejected (or an explicit unavailable review), Git publication state and the owner of the next move. Do not tell the user that a handoff file alone completes the rite.

## Durable records and boundaries

Use the installed Bon CLI, JSON stdin for rich new/edit briefs, and the existing board hierarchy. A brief needs why, what and done; how preserves approach, constraints and significant rejected alternatives. The outcome falsifier belongs to the human: carry existing words verbatim and leave it absent when unanswered. Do not make one up.

On a full opening, process the routed unprocessed handoffs and unlisted handoffs required by that project's convention in order; integrate into its maintained knowledge and adjudicate Candidates before marking processed. Preserve plan-seeded understanding. Missing automatic context does not change this. Do not initialize a second board because discovery failed from a nested directory.

Follow [the handoff contract](../../../../docs/HANDOFF-CONTRACT.md) and the owning project's placement rules. Preserve `## For the next Claude` and `## For Claudes to come` as parsing contracts while naming Codex honestly as author. Use only actually worked IDs in `items:`. A project with generated ledgers/room indexes owns how those are updated; do not hand-edit generator output. A project with governed concept pages instead of understanding.md gets knowledge integrated there, not a competing file. Leave the new handoff unswept for its next reader.

Detect visibility, writer access and Git ownership separately. Use the live CLI for Dolt; leftover JSONL is not the board. Distinguish sandbox denial from a server or host fault before changing infrastructure. With no writer, use provenance-tagged Candidates and do not call them minted. With a writer but robot-owned Git, make authorized board/Markdown changes while leaving synchronization to its owner. In particular, notes-sync's repository is not for agent commits, pushes, resets or rebases.

Transcript ingestion, backup and automatic capture need a qualified Codex adapter. If the environment provides one, verify its actual receipt before claiming it ran. Otherwise preserve the manual handoff and report the missing capture separately; do not invoke Claude capture scripts or imply that the shared parsing headers prove ingestion. Preserve useful actions even where an automatic mechanism is unavailable.
