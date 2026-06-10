# Bon Plugin System — A Worked Example

This walkthrough follows a real Claude Code session on the bon repo (31 March 2026).
It shows what Claude actually sees at each stage — hook outputs, skill instructions,
bon state transitions — not the scripts that produce them.

For the source scripts, see the plugin cache:
`~/.claude/plugins/cache/batterie/bon/<version>/`

---

## Phase 1: Session Start (Hooks)

When Claude Code starts, three things fire automatically before the user types anything.

### 1a. Health Check (`ensure-bon.sh`)

A SessionStart hook checks that the `bon` CLI is installed and in PATH.
If not, it prints a one-liner telling the user how to install it.
In a healthy session, this hook is silent — no output.

### 1b. Instruction Shard Symlink (`session-start.sh`)

A second SessionStart hook symlinks the instruction shard into `~/.claude/rules/bon.md`.
This makes bon's always-on rules available to every session without manual wiring.

The shard contains only behavioral overrides — not full skill instructions:

```
## Mandatory Skill Loading
When `.bon/` exists → invoke `Skill(open)` at session start and before bon CLI commands.

## Overrides
| Your Default | What I Need |
|-------------|-------------|
| Plan files  | Plans → Bon before execution. |
| TodoWrite   | Bon. Always. |
```

These rules load silently. Claude doesn't see a "shard loaded" message — the rules
just become part of its instruction set.

### 1c. Context Gathering (`open-context.sh`)

The main SessionStart hook gathers mechanical context and streams it to Claude.
Here's the real output from this session (trimmed — understanding.md alone is ~100 lines):

```
=== SESSION ===
Good morning. It's 31 Mar 2026, 11:00.

# Bon — Understanding

Bon is a CLI work tracker for Claude-human collaboration. JSONL by default,
optional Dolt backend, no daemon. ~2,300 lines of core source plus a 470-line
optional Dolt module. 384 tests. Designed primarily for AI agents — the
human-at-keyboard path exists but is secondary.

## The data model
[... two JSONL examples, field explanations, status/lifecycle rules ...]

## The architecture
[... cli.py pattern, storage dispatch, spec drift warning ...]

## Storage backends
[... JSONL vs Dolt, backend dispatch, Dolt in production ...]

## The invariants
[... unblock-on-done, single tactical per session, atomic writes ...]

## The landmines
[... bon wait destroys tactical, external consumers, KNOWN_VERBS ...]

## The brief's optional fields
[... --how design rationale ...]

## Script resolution in skills
[... find | head -1 bug, ls -td fix ...]

## The taste
[... legibility over abstraction, LLM-ergonomic first ...]

## The skills layer
[... /open, /close, /review, gate questions are load-bearing ...]

## Plugin resolution gotchas
[... directory name vs name: field, hook registration ...]

Last session (31m ago): Implement `bon new --json` stdin input, version bump to 0.13.0

# Handoff — 2026-03-31 (auto)

session_id: 98c67ef9-cb81-4228-9818-446ef199ef2b
purpose: Implement `bon new --json` stdin input, version bump to 0.13.0, and housekeeping

## Done
- **Closed bon-nufica** — garde-manger and todoist-gtd hook registrations already correct
- **Implemented `bon new --json` reading structured item from stdin**
- **Added 11 new tests**, all 419 pass
- **Bumped version 0.12.1 → 0.13.0**, committed and pushed

## Next
- **bon-gudiku** — rewrite system walkthrough as narrated /open→/close worked example

## Gotchas
- Auto-generated handoff — no reflective close was performed
- After version bumps, bon CLI can drift from plugin version

Outcomes we're working towards:
  ○ System walkthrough rewritten as narrated /open→/close worked example (bon-gudiku)

Nothing in progress — pick an action to start.

Suggested:
  - **bon-gudiku** — rewrite system walkthrough as narrated /open→/close worked example

Contributions pending (2):
  2026-03-31T093800.md
  2026-03-31T102900.md
```

The understanding.md is dumped **in full** — every section, every example. This is
deliberate: it's the incoming Claude's entire knowledge base for this codebase, loaded
once at session start. The above shows section headers only; the real output was ~100 lines.

This briefing has seven sections, all mechanical:

1. **Greeting** — time of day, date
2. **Understanding** — the full `understanding.md` document, unabridged (~100 lines)
3. **Handoff** — the most recent handoff file, in full (with "time ago" label)
4. **Outcomes** — top-level bon outcomes (just the `○` lines from `bon list`)
5. **Active work** — any in-progress tactical, or "nothing in progress"
6. **Suggested** — items from the handoff's "Next" section (Claude-to-Claude baton pass)
7. **Contributions** — unprocessed knowledge files waiting to be integrated

The understanding doc and handoff are the heavy context — together they can be 150+ lines.
Everything else is one-liners. Sections 4-7 are conditional: they only appear when there's
something to show.

---

## Phase 2: /open Skill (LLM-Mediated)

The instruction shard tells Claude: "When `.bon/` exists, invoke `Skill(open)` at
session start." The /open skill loads a full instruction set — the draw-down pattern,
the draw-up pattern, contribution processing, session lifecycle.

Claude's first job is the **LLM-mediated work the hook can't do:**

### 2a. Process Contributions

Two contribution files were pending. Claude read each, then rewrote `understanding.md`
to integrate the new knowledge — not append, rewrite:

- **Instruction shard pattern** — refined the existing explanation of `~/.claude/rules/`
  auto-loading, adding the distinction between `@context/` (hand-curated) and `rules/`
  (plugin-managed)
- **Plugin resolution gotchas** — new section about directory-name-based skill resolution
  and silent hook registration failures

After rewriting, Claude deleted the processed contribution files.

### 2b. Present Hierarchy

Claude ran `bon list`, captured it, and presented the full hierarchy as text:

```
○ System walkthrough rewritten as narrated /open→/close worked example (bon-gudiku)

○ Check garde-manger and todoist-gtd for missing hook registration (bon-nufica)
```

### 2c. Pick Direction

Claude assessed which items aligned with the loaded context. The handoff mentioned
gudiku; the contributions related to nufica. Claude suggested nufica based on
contextual momentum — but the user said "oh isn't nufica done?"

Claude checked (`bon show bon-nufica`), verified the plugins were already wired
correctly, and closed it: `bon done bon-nufica --note "Already completed in prior session"`.

---

## Phase 3: Work (Draw-Down → Execute → Step)

The session pivoted through a side quest (encoding a Passe plan as bons in a dummy repo
to test the `--how` field), which surfaced a real friction: shell escaping when creating
items with long brief fields. This led to the main work item.

### 3a. Plans Become Bons

Instead of entering plan mode, Claude created bon items:

```
bon new "bon new accepts JSON from stdin for escaping-free item creation" \
  --why "..." --how "..." --what "1. Add --json flag... 2. Add JSON stdin parsing... 
  3. Wire into existing flow... 4. Add tests... 5. Update README" --done "..."
```

This created an outcome (bon-tumira) with two actions under it.

### 3b. Draw-Down

Before touching code, Claude drew down on the first action:

```
$ bon work bon-bezifu

Approach: In argparse: add --json store_true, make title nargs='?' with default None.
In cmd_new: if args.json, read sys.stdin, json.loads, extract title/parent/brief fields.
...

→ 1. Modify argparse: --json flag, title becomes optional (nargs='?') [current]
  2. Add JSON stdin reading block at top of cmd_new
  3. Extract title, parent, brief.why, brief.how, brief.what, brief.done from parsed JSON
  4. Error on missing title or brief in JSON
  5. Route through existing require_brief_flags and parent validation
```

The `--how` field appeared as "Approach:" above the step list — strategy context before
touching code. The numbered items from `--what` became the tactical steps.

### 3c. The Tactical Hook

From this point, every user prompt triggered the `bon-tactical.sh` UserPromptSubmit hook.
Claude saw this injected into every message:

```
Active bon tactical:
Working: Add --json flag and stdin parsing to bon new (bon-bezifu)
✓ 1. Modify argparse: --json flag, title becomes optional (nargs='?')
→ 2. Add JSON stdin reading block at top of cmd_new [current]
  3. Extract title, parent, brief.why, brief.how, brief.what, brief.done
  4. Error on missing title or brief in JSON
  5. Route through existing require_brief_flags and parent validation

Work on the CURRENT step. Run 'bon step' when it's complete before moving on.
```

This kept Claude focused — one step at a time, with `bon step` advancing to the next.

### 3d. Step Through

After each piece of work, Claude ran `bon step`:

```
$ bon step
✓ 1. Modify argparse: --json flag, title becomes optional (nargs='?')
✓ 2. Add JSON stdin reading block at top of cmd_new
→ 3. Extract title, parent, brief.why, brief.how, brief.what, brief.done [current]
...
```

On the final step, `bon step` auto-completed the action:

```
$ bon step
✓ 5. Route through existing require_brief_flags and parent validation

Action bon-bezifu complete.
```

### 3e. Mid-Session Transition

After completing bon-bezifu (implementation), Claude moved to bon-kiraso (tests):

```
$ bon work bon-kiraso

→ 1. Test valid JSON creates outcome correctly [current]
  2. Test valid JSON with parent creates action
  3. Test missing required brief fields errors
  ...
```

Same pattern: draw-down, step through, auto-complete.

### 3f. Close the Outcome

With both actions done, Claude closed the outcome:

```
$ bon done bon-tumira --note "Implemented and tested — 11 new tests, 415 total passing"
Done: bon-tumira
```

---

## Phase 4: Session End

There are two paths for ending a session. Both produce a handoff file in `.bon/handoffs/`.

### Path A: /close Skill (Recommended)

When the user invokes `/close`, a 5-phase GODAR framework runs:

1. **Gather** — Claude collects everything that happened (bon state, git diff, observations)
2. **Orient** — Reflective analysis: what worked, what surprised, what's changed
3. **Decide** — Triage into Now (do before session ends), Bon (file as items), Handoff (prose for next Claude)
4. **Act** — Execute: close items, file new ones, write handoff, extract memories
5. **Review** — Final check: did anything get lost?

A /close handoff includes reflection and risk assessment:

```
# Handoff — 2026-03-31

session_id: 614fbc8f-e29f-4f33-8f52-47a79e9569ad
purpose: Fixed plugin wiring across batterie suite — skill renames, hook registration

## Done
- Completed skill directory renames: skills/bon→open, skills/audit→review
- Registered SessionStart hooks in plugin.json for 4 plugins
- Bumped versions: bon 0.12.1, batterie 0.1.6, trousse 0.4.1, mise 0.5.3, passe 0.5.1
- Verified all 5 plugins' instruction shards symlink correctly after restart

## Gotchas
- bon 0.12.1 cache is installed but skill names unverified at runtime
- garde-manger and todoist-gtd not checked for hook registration gaps

## Risks
- Desktop marketplace is stale — manifest changes only affect CLI marketplace
- PyMySQL installed unconditionally via [dolt] extras

## Next
- bon-gudiku: Rewrite system walkthrough as narrated /open→/close worked example
- bon-nufica: Check garde-manger and todoist-gtd for hook registration

## Reflection
**Claude observed:** Every bug this session was "two things that must agree got
out of sync, and nothing checked." Directory names vs frontmatter, hook scripts
vs plugin.json, CLI extras vs install commands.
**User noted:** The walkthrough should show what happens, not how.
```

### Path B: Auto-Handoff (Safety Net)

When a session ends without /close — the user types `/exit`, the context window fills up,
or the connection drops — the `session-end.sh` hook fires. It calls `auto-handoff.sh`,
which has three tiers:

**Tier 1: LLM-mediated** (best quality). If a session transcript exists and `claude` CLI
is available, the script converts the transcript to readable text (via `ccconv`), then
spawns a background Claude in print mode:

```bash
echo "$PROMPT" | claude -p --bare --model opus
```

This background Opus reads the conversation, git commits, and open bon items, then writes
a structured handoff. It runs via `nohup` after the main session has already exited — the
user never sees it. The `--bare` flag ensures no hooks or plugins fire (which would be
recursive).

**Tier 2: Mechanical fallback**. If `ccconv` or `claude` aren't available, or the LLM
call fails, the script falls back to pure shell: git log subjects become the Done section,
`bon list --ready` becomes the Next section, and a fixed gotcha line notes the mechanical
generation.

**Tier 3: Skip**. If /close already wrote a handoff for this session ID, `auto-handoff.sh`
exits silently — no double-handoff.

You can tell the tiers apart. This is a tier-1 handoff (from the session where we built
`bon new --json`) — note the specific, contextual descriptions that could only come from
reading the transcript:

```
# Handoff — 2026-03-31 (auto)

session_id: 98c67ef9-cb81-4228-9818-446ef199ef2b
purpose: Implement `bon new --json` stdin input, version bump to 0.13.0, and housekeeping

## Done
- **Closed bon-nufica** — garde-manger and todoist-gtd hook registrations were already
  correct; no work needed, outcome closed as already done
- **Encoded Passe plan as bons in a dummy repo** — two outcomes with seven actions,
  demonstrating `--how` field for architecture decisions and CDP call sequences
- **Implemented `bon new --json` reading structured item from stdin** — ~20 lines added
  to `cmd_new` in `bon/cli.py`
- **Added 11 new tests** in `tests/test_new.py`
- **All 419 tests pass** (415 unit + 4 Dolt integration)
- **Bumped version 0.12.1 → 0.13.0** in `plugin.json`
- **Committed and pushed** — commit `cec4d23`
- **Reinstalled bon CLI to 0.13.0** — version was drifting at 0.12.1

## Next
- **bon-gudiku** — rewrite system walkthrough as narrated /open→/close worked example

## Gotchas
- Auto-generated handoff — no reflective close was performed
- After version bumps, bon CLI can drift from plugin version and needs explicit reinstall
- `bon new --json` is symmetrical with `bon show --json` — future Claudes encoding plans
  should use JSON heredoc piped to `bon new --json` to avoid shell-quoting pain
```

A tier-2 mechanical fallback would look sparser — just git commit subjects as bullet
points, no contextual descriptions, no gotchas beyond the fixed "(auto)" line.

The "(auto)" marker in the header is the tell. The next Claude gets continuity either
way — but /close produces richer context (reflection, risks, taste judgments).

---

## The Full Lifecycle, Summarised

```
Session Start                          Session End
─────────────                          ───────────
ensure-bon.sh ─── health check         session-end.sh ─── auto-handoff
session-start.sh ─ shard symlink                          (safety net)
open-context.sh ── briefing stream           OR
      │                                /close skill ────── GODAR framework
      ▼                                      │
/open skill (LLM)                            ▼
  ├─ Process contributions             .bon/handoffs/xxx.md
  ├─ Present hierarchy                 (persists for next session)
  └─ Pick direction
      │
      ▼
Draw-down: bon show → bon work → bon step → bon step → ...
      │                    ▲
      │                    │ bon-tactical.sh
      │                    │ (injected every prompt)
      ▼
bon done → next action or /close
```

Each session reads the previous session's handoff. Each handoff carries forward
what the next Claude needs to know. The understanding document accumulates knowledge
across sessions via contributions. The cycle repeats.
