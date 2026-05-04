# Bon — Instruction Shard

Auto-loaded via `~/.claude/rules/bon.md`. Carries always-on rules only — skill context (`/open`, `/close`) handles the rest.

## Skill Loading

When `.bon/` exists, invoke `Skill(open)` at session start and before bon CLI commands — it provides context that makes the rest of the session better.

Bon is the default tracker. Check bon briefs for staleness before executing.

When a skill or tool fails during real work: file a Field Report bon item in the repo that owns it.

## Overrides

| Your Default | What I Need |
|-------------|-------------|
| EnterPlanMode for complex tasks | `bon:plan` — thinking expressed as understanding.md + bon hierarchy |
| Plan files | Plans → Bon before execution |
| TodoWrite for work tracking | Bon for anything that persists across sessions. TodoWrite is fine for ephemeral in-session checklists. |

## GTD Vocabulary

| Say This | Not This |
|----------|----------|
| Desired Outcome | Epic, User Story |
| Next Action | Task, Ticket |
| Waiting For | Blocked, Blocker |
| Someday/Maybe | Backlog |

Frame outcomes as achievements: "Taught Claude to generate charts" not "Create chart generation skill." Past-tense verb + the "so what."

## Dolt Backend

Some repos use Dolt instead of JSONL. The `bon` CLI handles both transparently. If bon commands fail with "Cannot connect," the Dolt server may be down:

```bash
systemctl --user start dolt-bon.service   # on hezza
```

If a repo has both `.bon/backend=dolt` and a stale `items.jsonl`, the JSONL file is a pre-migration ghost — bon ignores it.

## Discoverability

`bon show ID --json` and `bon list --json` already pretty-print (indent=2). Pipe direct — no need to wrap in `python3 -m json.tool` or `json.dumps(d, indent=2)`.

## Session Lifecycle

**Starting:** Hooks provide orientation. Draw-down from bon before writing code.

**Stopping:** Use `/close` skill.

## Capture Generously

During /close, lean toward capturing rather than filtering. If something came up during the session — even if it seems minor, pre-existing, or someone else's domain — put it into Now, Bon, or Handoff Next. You propose which bin; Sameer decides what drops. The cost of capturing something unnecessary is low; the cost of losing a useful observation is high.
