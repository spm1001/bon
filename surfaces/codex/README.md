# Codex surface for Bon

The authored skill is `surfaces/codex/skills/bon/SKILL.md`. On Tube it is exposed as one explicit link at `~/.codex/skills/bon`; the source remains in this repository. Start a new Codex invocation to refresh skill discovery, then use `$bon` for opening, planning, board operations or closing. This does not register Claude's `/open` or `/close` commands in Codex.

This is a selective adaptation of Bon's installed workflow, not a copy of its Claude instruction shard. The installed Claude plugin examined was 1.85.3; the CLI and this source checkout were 1.85.2. The CLI identity and commands used by the skill were checked against the installed implementation.

Portable parts retained: outcome/action briefs, human-owned falsifiers, live-board orientation, staleness checks, guarded tactical steps, ledger/Candidates handling and the handoff parsing contract. Runtime-specific parts omitted: Claude session breadcrumbs, automatic prompt-step injection, transcript-derived closing helpers and capture hooks. Their absence is explicit so a successful CLI call is not mistaken for a complete lifecycle integration.

The Codex-on-Tube setup action is infra `iw-roveji`. Its evidence and cold-start continuation check live in `infra/machines/tube/codex`; the ongoing setup plan remains on that board.
