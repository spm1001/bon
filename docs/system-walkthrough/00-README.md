# Bon Plugin System — End-to-End Walkthrough

This folder contains every artifact in the bon plugin system, numbered
in execution order. Read them sequentially to understand the full lifecycle.

## Session Start Sequence

1. `01-ensure-bon.sh` — Health check: is bon CLI installed?
2. `02-session-start.sh` — Symlinks instruction shard, runs open-context.sh
3. `03-open-context.sh` — Gathers mechanical context (understanding, handoff, bon state)
4. `04-instruction-shard.md` — Always-on rules loaded via ~/.claude/rules/bon.md
5. `05-skill-open.md` — /open skill: LLM-mediated session orientation

## During Session

6. `06-bon-tactical.sh` — UserPromptSubmit: injects current step into every prompt
7. `07-context-budget.sh` — UserPromptSubmit: warns when context window fills up
8. `08-skill-close.md` — /close skill: end-of-session capture (GODAR)
9. `09-skill-review.md` — /review skill: periodic cross-repo backlog triage

## Session End Sequence

10. `10-session-end.sh` — Triggers auto-handoff if /close didn't run
11. `11-auto-handoff.sh` — Generates handoff from git+bon+transcript

## Supporting Files

12. `12-plugin-json.json` — Plugin manifest: hooks, metadata, version
13. `13-understanding.md` — Living document: what a Claude needs to know about bon
