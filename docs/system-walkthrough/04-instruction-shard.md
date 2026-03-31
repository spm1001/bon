# Bon — Instruction Shard

Auto-loaded via `~/.claude/rules/bon.md`. Carries always-on rules only — skill context (`/bon`, `/close`) handles the rest.

## Mandatory Skill Loading

**When `.bon/` exists → invoke `Skill(open)` at session start and before bon CLI commands.**

Bon is the default tracker. Check bon briefs for staleness before executing.

When a skill or tool fails during real work: file a Field Report bon item in the repo that owns it.

## Overrides

| Your Default | What I Need |
|-------------|-------------|
| Plan files | Plans → Bon before execution. |
| TodoWrite | Bon. Always. |

## GTD Vocabulary

| Say This | Not This |
|----------|----------|
| Desired Outcome | Epic, User Story |
| Next Action | Task, Ticket |
| Waiting For | Blocked, Blocker |
| Someday/Maybe | Backlog |

Frame outcomes as achievements: "Taught Claude to generate charts" not "Create chart generation skill." Past-tense verb + the "so what."

## Session Lifecycle

**Starting:** Hooks provide orientation. Draw-down from bon before writing code.

**Stopping:** Use `/close` skill.

## Capture Everything, Triage Nothing

During /close, your job is capture, not gatekeeping. Never dismiss an observation with "pre-existing," "not bon-worthy," "someone else's problem," "not important for release," or "just do it next session." If it came up during the session, it goes into Now, Bon, or Handoff Next — never into untracked limbo. You propose which bin; I decide what drops.
