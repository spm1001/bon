# Plan case execution

Synthetic user request: “Help me plan the large-file work for the converter. I have not chosen the memory budget yet.”

## User-facing response

I’m using the Bon skill to plan this work. This is Tube, launched from `/home/modha`, with the selected repository and local JSONL board at `/tmp/bon-ziwuda-cases/plan`. I explicitly read the project instructions, routed understanding, prior handoff, local board and configured fixture accent; no automatic Claude delivery is assumed.

The existing hierarchy already fits, and your plan accent says to use it:

- Reports convert reliably through the supported interface (`fixture-talowe`) — 0 of 2 actions complete.
  - The format flag replaces the text flag (`fixture-vusifo`) — open; README still uses the old option.
  - Large files convert without retaining the entire report in memory (`fixture-ziteju`) — open; its acceptance criterion refers to a memory bound that has not been chosen.

The local queue has one **With operator** line matching this converter’s interface action. Its description explicitly holds the large-file redesign for your memory target and retains a separate downstream-consumer migration reminder. I left that line intact. No tactical claim is active.

I’ve updated [understanding.md](/tmp/bon-ziwuda-cases/plan/understanding.md) with the proposed architectural frame for review. The supplied converter currently contains only an argument parser; it has no conversion pipeline or tests to extend. We need the input structure, expected output and representative large input before choosing parsing and buffering details. The memory budget remains explicitly undecided.

My proposed sequence is to establish the representative conversion and how we measure peak process memory, then implement bounded reading, transformation and writing, and finally check output correctness and memory as input size grows. We should account for very large individual records as well as accumulated buffers. I would refine the existing large-file action under the current outcome once that frame is agreed; the interface documentation and downstream migration remain separate.

The [Plan rite](/home/modha/repos/spm1001/bon/skills/plan/SKILL.md) requires “Present the understanding.md update to the user before proceeding” and assigns the falsifier to you. This is that review point; no new outcome, action or implementation has been committed.

`fixture-talowe` — Reports convert reliably through the supported interface — still has no human-authored falsifier.

What memory ceiling should this target—or which machine and representative workload should we use to choose it—and what would tell you this went wrong even if its completion checks passed?

## Reads and commands

- Read installed `/home/modha/.codex/skills/bon/SKILL.md`, resolved to `/home/modha/repos/spm1001/bon/surfaces/codex/skills/bon/SKILL.md`.
- Read maintained `skills/plan/SKILL.md`, the applicable `skills/open/SKILL.md`, `docs/ACCENT.md` and `docs/HANDOFF-CONTRACT.md` from the Bon source checkout. Reused these source instructions across the two independent cases; no fixture facts or IDs crossed cases.
- Read this fixture’s `AGENTS.md`, `case.json`, `README.md`, `understanding.md`, `converter.py`, `handoffs/LEDGER.md`, `handoffs/prior.md`, `.bon/items.jsonl`, `.bon/sync`, `queue.json`.
- Extracted only `plan.personal` from this fixture’s accent before orienting; it instructs reuse of the existing converter outcome. Later extracted `open.personal` for the opening requirement. Deviation: its section extraction occurred after the queue read; no extra queue behaviour was inferred.
- Listed this fixture’s files with `rg --files --hidden -g '!.git/**'`; no tests, CLAUDE.md, rooms.md, nested room routes, legacy handoffs or additional handoffs were present.
- Ran `git status --short`, `git remote -v`, `bon list` captured to `hierarchy-capture.txt`, read the capture, and ran `bon work --status`.
- Ran `bon show fixture-talowe` and `bon show fixture-ziteju` to read the live outcome/action briefs and confirm overlap before proposing changes.
- Host and runtime metadata observed in the same execution session: Tube, actual CODEX_THREAD_ID `01a07d39-8247-7901-b4f7-7a44c487e4fe`. No separate case identity fabricated.
- No upstream exists; no fetch attempted because networking is prohibited. No external account, integration or real board was accessed.
- Ran `git diff --stat` and `git status --short` after local changes.

## Mutations

- Rewrote this fixture’s `understanding.md` with integrated handoff knowledge and the Phase 2 architectural frame, marking the implementation approach as proposed and preserving the unresolved budget and falsifier.
- Ticked the single prior handoff ledger line processed on 2026-09-07 after integrating its durable knowledge. No Candidates existed.
- Created `hierarchy-capture.txt` and this `result.md` inside the fixture.
- No Bon item added or edited; existing outcome reused as proposal context. No fabricated numeric budget or --badly value. Board, tactical state, queue, parser, README and prior handoff unchanged. No Git commit or publication.

## Stop condition

Stopped at the human review/decision point after a concrete architectural frame and proposal. Memory budget, representative workload and human falsifier remain unanswered. Phases 3–5 and implementation are not represented as complete. No user answer invented.
