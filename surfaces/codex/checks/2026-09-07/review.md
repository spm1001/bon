# Converter backlog review result

## Proposed user response

No backlog item is fully finished. The parser change is present; two briefs need correction, and the documentation is the next workable action.

| Item | Finding | Proposed disposition |
|---|---|---|
| Format flag replaces text flag (fixture-hobufu) | ACTIVE, partly implemented: converter.py:3 accepts --format, but README.md:2 still says --text. | Keep open. Remove the already-implemented parser step from the remaining checklist; update and check the usage example. Preserve “Parser and README use --format.” |
| Large files stay within memory (fixture-sojewo) | BLOCKED by the operator's explicit hold in queue.json, although the board has no recorded wait. No memory target is agreed. | Correct the brief to put that decision before implementation; keep this separate and held. The operator must supply the target before any corresponding done-criterion amendment. |
| Reliable supported interface (fixture-karubo) | ACTIVE: both children remain open and the supplied code only parses arguments. Passing conversions and examples are not demonstrated. | Keep open; its current brief describes the desired result adequately. No falsifier has been supplied. |

I recommend correcting the two action briefs and then completing the format documentation. Its example must match the parser: merely substituting --format for --text while retaining input.txt would still be wrong, because this parser accepts only text or json as the option value and declares no input-file positional argument.

The local steering line stays untouched. Its description also contains a separate downstream-consumer migration reminder, which must survive even when the format work later closes. No external dispatch queue is configured, so no lane population applies.

This is a bounded file-based self-check; independent review is unavailable, and the fixture has no upstream. None of the three items was closed, no briefs or completion criteria were changed, and no conversion execution is claimed. The pending record is at review-record/2026-09-07-review/.

Approve the two proposed brief corrections and documentation-first sequence, leaving the large-file action held until you supply its memory target?

The approval gate comes from [Bon review SKILL.md](/home/modha/repos/spm1001/bon/skills/review/SKILL.md): “This is a hard gate — no action without user approval.” It applies to the proposed brief mutations; they remain unapplied pending your adjudication.

## Execution and source delivery

Execution host: tube. Initial launch directory: /home/modha. Selected repository and sole board: /tmp/bon-ziwuda-cases/review, local JSONL with prefix fixture and sync off. Runtime CODEX_THREAD_ID was supplied as 01a07d39-a784-7263-890d-c4eb5ed3c8c4. Git began clean on main at 9796cfb with no remote or upstream. No tactical steps were active; this does not establish unique conversation ownership of the checkout.

The shared AGENTS instructions and fixture task boundaries were present in starting context. The Bon adapter was explicitly read from /home/modha/.codex/skills/bon/SKILL.md and resolved to /home/modha/repos/spm1001/bon/surfaces/codex/skills/bon/SKILL.md. The source review rite, accent contract, pyramid format and verification patterns were subsequently read from that Bon source checkout. No Claude hook or automatic routing delivery was assumed.

The task explicitly selected this one fixture and requested a bounded file-based check; this supplied review scope and authority for that check. It did not approve any board corrections. The source rite's remaining action/adjudication gate is unresolved: this record is a pending review, not a completed adjudicated five-phase rite. No user response or approval was invented.

## Reads and read-only checks

- Skill/source reads: adapter SKILL.md; source skills/review/SKILL.md; docs/ACCENT.md; skills/review/references/pyramid-format.md; skills/review/references/verification-patterns.md.
- Fixture contents read: AGENTS.md, accent.md, understanding.md, handoffs/LEDGER.md, handoffs/prior.md, README.md, converter.py, queue.json, case.json, .bon/items.jsonl, .bon/prefix, .bon/sync, .bon/README.md. The whole small accent file was initially displayed; only review.personal was applied. This exceeded the adapter's requested section-only read, and is recorded rather than concealed; no real personal accent was accessed.
- Fixture inventory: directory listing and rg --files including .bon and handoffs, excluding Git object contents. No existing review archive/pyramid was present before this run.
- CLI reads from the selected repository: bon --help, bon work --status, bon list, bon show for all three fixture items, bon list --someday. No tactical claim was created or cleared.
- Git/runtime reads: hostname, pwd, command -v bon, git status --short, git log, git remote -v, git branch -vv, UTC time and supplied CODEX_THREAD_ID only. Git history has a single initial fixture commit, no Bon citations and no evidence of separate implementation commits.
- Manual scoped survey replaced global survey/net-motion helpers, which could inspect other boards or contact a network. No survey of other repositories, network access, integrations, real boards, real personal files, or other agents occurred.
- Handoff material was read as review evidence. Its ledger remains unprocessed; review did not claim to run a separate full opening or knowledge-intake rite.

## Mutations and state

Created only result.md and review-record/2026-09-07-review/ with items-before.jsonl, survey-before.json, verification.json, pyramid-draft.md, survey-after.json and summary.md. These are review records required by the task and fixture review.personal section. No board, queue, source, README, accent, handoff or Git history was changed.

Before/after: 3 open → 3 open; 0 closed, 0 repricings applied, 0 items minted, 0 queue writes. Two proposed repricings await adjudication. The after snapshot records the pause state and does not imply Phase 4 happened. Record files remain in this /tmp fixture and may disappear on reboot.

Next move belongs to the user: adjudicate the corrections and next-work proposal; supply the memory target before large-file work starts. Before any later approved mutation, re-show each item and compare against this run's saved brief; skip and report concurrent changes instead of overwriting them.
