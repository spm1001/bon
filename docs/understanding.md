# Bon — Understanding

Bon is a 2,100-line CLI work tracker built for Claude-human collaboration. JSONL-based, no dependencies beyond stdlib, no daemon. It was spec'd and built in a single evening (25 Jan 2026), then hardened over six weeks through four phases: core implementation, multi-Claude safety, a rename from "Arc" to "Bon" (kitchen metaphor), and two rounds of empirically-driven ergonomics work informed by analysis of 2,542 real Claude commands across 2,914 sessions. 89 commits. 286 tests at a 2:1 test-to-source ratio. The backlog is nearly clean — 21 of 23 items done.

## The real architecture

`cli.py` is 64% of the codebase. Every command is a standalone function that loads the entire JSONL file, mutates the in-memory list, and writes the whole file back. No update-in-place, no event log, no ORM. `storage.py` handles I/O and validation. Everything else (`display.py`, `ids.py`, `queries.py`) is small support. `queries.py` is 14 lines — two list comprehensions in their own module, left over from an abstraction that never arrived.

The complexity isn't in the code — it's in the spec. `SPEC.md` is 55k words, 25x longer than the non-CLI modules combined. The spec did the hard thinking; the code just implements it. This is deliberate and load-bearing. When behavior is unclear, the spec is authoritative.

## The invariants that matter

**Unblock on done.** When any item is marked done, all items whose `waiting_for` points to it get unblocked automatically. This cascade lives in both `cmd_done` and `cmd_step` (auto-complete on final step). It's the only cross-item mutation. Breaking it breaks the dependency model.

**Single active tactical per session.** Enforced at `bon work` time by CWD matching. At most one action in a given working directory can have active tactical steps. `_matches_session()` is the quiet linchpin — `None` session means "only unscoped items," a real path means "match this path OR unscoped." This backward-compatibility rule handles pre-session legacy data.

**IDs are immutable and globally unique.** `generate_unique_id` checks both active and archived pools. Three CV syllables from a curated consonant set (no q, x, y), producing pronounceable IDs like `gabdur`. Mixed-case legacy IDs (`huHida`) exist and must not be renamed.

**Atomic writes, deterministic order.** `save_items()` writes to `.tmp` then renames. Sort by ID before writing produces stable diffs. Together with `merge=union` in `.gitattributes`, this makes concurrent branches that touch different items merge cleanly. Same-item edits still conflict — intentionally, because that means two sessions touched the same work.

**Dedup on save.** Both `load_items()` and `save_items()` deduplicate by ID, keeping the version with the most recent timestamp across four fields (`done_at > archived_at > updated_at > created_at`). This is the mechanism that makes union merges viable. The tradeoff: if two branches edit the same item at the exact same second, last-writer-wins is a coin toss. Dedup is silent — it prints to stderr but drops the older item without confirmation.

## The landmines

**`bon wait` destroys tactical state.** Waiting an action with steps in progress silently discards all tactical data (`item.pop("tactical")`). No confirmation prompt. An agent that waits an action with 4/5 steps done loses that progress permanently. The spec says "long blocks warrant re-planning" but the data loss is invisible.

**`error()` raises, doesn't print.** `error()` raises `BonError`, caught 1,300 lines away in `main()`. Not the `print-to-stderr-and-exit` pattern most CLI tools use. Better for control flow, but a new contributor will misread it on first encounter.

**The `.arc/` ghost.** The rename from Arc to Bon changed the directory name and CLI command but not the test infrastructure. `conftest.py` still calls its fixture `arc_dir`. The test helper is `run_arc()`. Fixtures use `arc-` prefix. Not broken, but creates persistent naming dissonance.

**External consumers.** Trousse reads `items.jsonl` directly with `jq`. Field names, types, and structure are part of a contract that extends beyond bon's own codebase. Schema changes need to account for this.

**`KNOWN_VERBS` is manually maintained.** The frozenset in `storage.py` lists valid `updated_by` verbs. When new mutation commands are added, this set needs manual updating. `bon doctor` validates against it, but nothing enforces the set stays in sync with the commands that write verbs.

**`cmd_work` argument parsing.** Uses `argparse.REMAINDER` to capture a mix of ID, step strings, and `--force`, then manually filters `--force` out of positionals. This hand-rolled parsing is the most fragile spot in the codebase. `REMAINDER` is famously tricky in argparse.

## The taste

**Legibility over abstraction.** No base classes, no registries, no plugins. Each command is a function you can read top-to-bottom without chasing indirection. The repetition (`check_initialized(); items = load_items(); prefix = load_prefix()`) is deliberate — every command is self-contained.

**LLM-ergonomic first.** The tool is designed for AI agents, not humans. `get_creator()` appends `-tty` when stdin is a TTY — the unusual case is a human typing. `--quiet` exists so agents capture just the ID. `--json` exists for piping to `jq`. `--parent` was aliased to `--outcome` because Claude's training data makes `--parent` the strongest prior. `check_outcome_language()` catches "Implement OAuth" and nudges toward "Users can authenticate" — coaching the agent away from activity framing.

**Briefs are a forcing function.** Every item requires `{why, what, done}`, all three non-empty. This isn't metadata — it forces clear thinking at creation time. `parse_steps_from_what()` closes the loop by extracting tactical steps from the `what` field, making the brief executable.

**Systemic fixes over point fixes.** The dedup-in-save pattern is the clearest example: fix the general mechanism and specific bugs become non-issues. This taste extends to how features are added — the `updated_by` verb system was added to all 10 mutation sites at once, not incrementally.

## What's in play

Two outcomes remain open. Both are stretch goals — the core tool is stable and in daily use.

**bon-jokeza: Context-ranked draw-down.** When a Claude session starts, rank ready actions by what's already in the context window rather than listing in bon order. Prose-only changes to two SKILL.md files. No code. Could be done quickly, but the design thinking matters more than the implementation.

**bon-vimewu: Cross-repo tactical flow.** Bon tacticals are CWD-scoped, so switching repos silently breaks `bon step`. Needs a project registry concept — a way to resolve IDs globally with CWD mismatch warnings. Medium difficulty, needs architectural planning. Research is complete but no design has been committed to.

## What a fresh Claude should know

The test suite runs in under 5 seconds (excluding `pytest` startup). Run it before committing. The `_reset_data_dir()` autouse fixture in conftest is critical — without it, the cached absolute path leaks between tests. When adding a command: handler in `cli.py`, subparser in `main()`, test file in `tests/`, update README command table. Check the spec first — the answer to "should it work this way?" is almost certainly already written down.
