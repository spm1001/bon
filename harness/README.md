# Arc Harness — Structural Enforcement for Arc Sessions

**Middleware, not instructions.** Code that runs, not prose that suggests.

The arc harness is a [Pi](https://github.com/badlogic/pi-mono) extension that
replaces honour-system CLAUDE.md instructions with structural enforcement. It
gates tool execution, injects state after compaction, validates turns, and
renders the session state machine as a persistent visible display.

## The Problem

Arc's workflow patterns — draw-down, tactical steps, checkpoints, handoffs —
are documented in CLAUDE.md and SKILL.md. The model follows them ~80% of the
time. The other 20% is spent nagging. TodoWrite instructions get ignored.
Checkpointing gets skipped. Skills don't get read before relevant work starts.

**The difference:** "please update the task graph" (vibes) vs a harness that
structurally won't proceed without a valid state transition (gates).

## The Design: Centre Pompidou

The state machine is the UI, not hidden behind it. Both Claude and the human
see where in the workflow they are, what obligations are pending, what gates are
coming next. The building shows its own pipes.

```
  +- SESSION: arc-47 "Refactor measurement pipeline" --------------------
  |  *OPEN -> *LOADED -> [WORKING] -> CHECKPOINT -> CLOSING
  |
  |  Working: Refactor measurement pipeline (step 3/7)
  |  Skills: [core-fluency] [xlsx]  Tokens: [========--] 68%
  |  Arc: 3/7 actions done, 2 outcomes open
  |  Next gate: checkpoint at 75%
  |
  |  Pending:
  |  - Complete: Add CLI command -> then run arc step
  +----------------------------------------------------------------------
```

## State Machine

```
INIT ──> CONTEXT_LOADED ──> WORKING ──> CHECKPOINT ──> CLOSING
 |                            |    ^        |              |
 |     load arc state,        |    |   save state,        |
 |     inject context         |    |   resume              |
 |                            |    |                       |
 |                        arc step advances            validate
 |                        tactical pointer             handoff
 v
(no .arc/ = harness is silent)
```

### Phases

| Phase | Entry condition | What happens |
|-------|----------------|--------------|
| **INIT** | Session start | Extension loads, checks for `.arc/` |
| **CONTEXT_LOADED** | `.arc/` found | Arc state loaded, ready items injected into context |
| **WORKING** | Action picked + draw-down | Tactical steps active, per-turn validation |
| **CHECKPOINT** | Token budget threshold | State saved, obligations validated |
| **CLOSING** | Session end | Handoff validation, obligation check |

### Gates

Gates are structural — the harness enforces them through event hooks, not
instructions.

| Gate | Mechanism | What it prevents |
|------|-----------|-----------------|
| **Arc context** | `before_agent_start` → loads state, injects | Working without seeing what's ready |
| **Skill** | `tool_call` → checks skill read before tool use | Using tools without relevant skill loaded |
| **Draw-down** | `turn_end` → tracks `arc work` calls | Starting work without tactical steps |
| **Step** | `turn_end` → checks `arc step` after completions | Motoring through without checkpoints |
| **Checkpoint** | `turn_end` → token budget check | Running out of context without saving |
| **Close** | `session_shutdown` → validates handoff | Ending without proper handoff |

### Enforcement Mapping to Pi Events

| Pi Event | Enforcement |
|----------|-------------|
| `session_start` | Reconstruct state, load Arc, show widget |
| `before_agent_start` | Inject Arc context, refresh state |
| `context` | Add harness state to messages (survives compaction) |
| `tool_call` | Skill gates, track Arc CLI usage |
| `turn_start` | Token counter increment |
| `turn_end` | Validate obligations, refresh state, update widget |
| `session_compact` | Re-inject state from extension memory |
| `session_shutdown` | Handoff validation |

## Installation

### Project-local (recommended)

Copy the extension to your project's `.pi/extensions/`:

```bash
cp harness/arc-harness.ts .pi/extensions/arc-harness.ts
```

### Global

Copy to global extensions directory:

```bash
cp harness/arc-harness.ts ~/.pi/agent/extensions/arc-harness.ts
```

### Quick test

```bash
pi -e harness/arc-harness.ts
```

### Requirements

- [Pi](https://github.com/badlogic/pi-mono) coding agent
- `arc` CLI in PATH (or `uv run arc` available)
- `.arc/` directory in project root

## Commands

The harness registers three slash commands and one LLM tool:

| Command | Description |
|---------|-------------|
| `/harness` | Full-screen Rogers display of current state |
| `/obligations` | Show pending obligations |
| `/gate` | Check gate status (skills, draw-down, checkpoint) |
| `harness_status` (LLM tool) | Programmatic state query for the model |

## Configuration

### Skill Gates

Map tool patterns to required skill files. In the extension source:

```typescript
const DEFAULT_SKILL_GATES: Record<string, string[]> = {
  "create_spreadsheet": ["skills/xlsx.md"],
  "write_docx": ["skills/docx.md"],
};
```

When the LLM calls a tool matching a pattern, the harness checks whether the
corresponding skill file has been read this session. If not, it emits a warning.

### Checkpoint Threshold

Default: 75% of token budget. Change `DEFAULT_CHECKPOINT_THRESHOLD` in the source.

### Token Budget Estimate

The harness estimates tokens at ~4000 per turn (rough heuristic). The token
bar in the Rogers display uses this estimate against a 200k context window.
Adjust `TOKEN_BUDGET` and `TOKEN_PER_TURN_ESTIMATE` for your model.

## How It Works

### Context Injection (Survives Compaction)

On every LLM call, the harness injects current state via the `context` event:

```xml
<arc-harness>
=== ARC HARNESS STATE (auto-injected, do not remove) ===
Phase: working
Turn: 12
Working on: arc-zokte — Add OAuth callback endpoint
Tactical: step 3/5
Current step: Add CLI command
Token budget: ~48%

Pending obligations:
  - Complete: Add CLI command -> then run arc step
=== END HARNESS STATE ===
</arc-harness>
```

This means the model **always** knows its position in the workflow, even after
compaction wipes the conversation history. The extension remembers; the model
doesn't have to.

### Widget (Rogers Display)

A persistent TUI widget renders the state machine after every turn. Both human
and Claude see the same display: phase, obligations, token budget, gates.

### Tool Registration

The `harness_status` tool gives the LLM a way to explicitly query state.
This is the "good freedom" principle: the harness supports the model, doesn't
cage it. A model that can see "I'm on step 4/7, next gate is checkpoint" can
focus on actual work instead of spending cognitive budget on process management.

## Design Principles

### Good Freedom

The harness should support the Claude, not cage it. A Claude that can see
"I'm on task 4/7, skills loaded, next gate is tests" can focus on actual work
instead of spending cognitive budget on process management. The harness carries
procedural memory so the model uses context for the problem.

### Pipes Are Visible

The state machine is the UI. Both parties navigate by it. No hidden state,
no invisible enforcement. When a gate trips, both human and Claude see why.

### Middleware > Instructions

The harness is middleware in the agent loop, not prose in a markdown file.
It runs at the code level: Pi events fire, the harness executes, state is
enforced. The model never gets the choice to skip.

### Minimal Overhead

When there's no `.arc/` directory, the harness is completely silent — no output,
no state, no widget. Zero overhead outside Arc projects.

## Architecture Decision Record

**Considered:**

1. **Pi extension** — hooks into agent loop, UI primitives, state management
2. **Claude Code hooks** — `UserPromptSubmit` shell scripts, limited to context injection
3. **Standalone supervisor daemon** — monitors session externally
4. **PydanticAI-style framework** — typed validation and retry patterns

**Chose: Pi extension** because:

- Pi's event model maps 1:1 to every enforcement mechanism needed
- Widget/status/custom UI primitives enable the Rogers display
- State persists in extension memory across compaction
- Tool call interception enables skill gates
- Already in Sameer's workflow (`.pi/extensions/` in pi-mono fork)
- Single TypeScript file, no build step, hot-reloadable via `/reload`

Claude Code hooks can only inject context before user messages — no tool call
interception, no post-turn validation, no UI widgets. The standalone daemon
adds deployment complexity without additional capabilities. PydanticAI's
patterns are useful (validation, retry, gating) but designed for programmatic
agents, not interactive sessions.
