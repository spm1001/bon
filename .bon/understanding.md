# Bon — Understanding

Bon is a CLI work tracker for Claude-human collaboration. JSONL-based, no dependencies beyond stdlib, no daemon. ~2,100 lines of source, 286 tests. Designed primarily for AI agents — the human-at-keyboard path exists but is secondary.

## The data model

Two item types live in `.bon/items.jsonl`. An **outcome** is a desired result. An **action** is a concrete step toward an outcome.

```jsonl
{"id":"bon-jokeza","type":"outcome","title":"Draw-down suggests actions ranked by loaded context","brief":{"why":"...","what":"1. Add guidance... 2. Rank suggestions...","done":"After /open, Claude presents ready work with context-proximity reasoning"},"status":"open","order":6,"created_at":"2026-03-01T07:49:37Z","created_by":"spm1001"}
{"id":"bon-bebune","type":"action","title":"Raw-file health checks","brief":{"why":"...","what":"1. Read items.jsonl... 2. Flag malformed JSON...","done":"bon doctor on a bad file reports all issues with line numbers"},"status":"done","parent":"bon-mufene","order":1,"created_at":"2026-03-02T21:29:19Z","created_by":"spm1001","waiting_for":null,"tactical":{"steps":["Read items.jsonl line-by-line","Flag malformed JSON","Flag conflict markers","Flag duplicate IDs"],"current":4,"session":"/home/modha/Repos/bon"},"updated_at":"2026-03-02T21:32:24Z","updated_by":"stepped","done_at":"2026-03-02T21:32:24Z"}
```

Key fields: `brief` is mandatory — `{why, what, done}`, all three non-empty. `parent` links an action to its outcome. `waiting_for` holds the ID of a blocking item. `tactical` tracks step-by-step progress within a session (steps list, current index, session CWD). `updated_by` records the verb of the last mutation ("stepped", "waited", "edited").

**Statuses are simple.** An item is `open` or `done`. "Waiting" isn't a status — it's an open item that has a non-null `waiting_for`. "Ready" means open with no blocker. "Active" means it has tactical steps in progress.

**Lifecycle:** Created open. Optionally blocked with `bon wait` (sets `waiting_for`). Worked on with `bon work` (creates tactical steps from the brief's `what` field). Steps advanced with `bon step`. Completed with `bon done` or by finishing the final step. Archived with `bon archive` (moves to `.bon/archive.jsonl`).

## The architecture

`cli.py` is 64% of the codebase — every command is a standalone function that loads the entire JSONL file, mutates the in-memory list, and writes the whole file back. `storage.py` handles I/O and validation. `display.py`, `ids.py`, and `queries.py` are small support modules.

The complexity isn't in the code — it's in the spec. `SPEC.md` is 55k words. The spec did the hard thinking; the code implements it. When behavior is unclear, the spec is authoritative. But note: the spec may have drifted from the implementation in places. Verify against the code for edge cases.

Every command follows the same pattern: `check_initialized()` → `load_items()` → mutate → `save_items()`. No exceptions. No middleware. Reading any single command function tells you everything about what that command does.

## The invariants

**Unblock on done.** When any item is marked done, all items whose `waiting_for` points to it get unblocked automatically. This cascade lives in both `cmd_done` and `cmd_step` (auto-complete on final step). It's the only cross-item mutation. Breaking it breaks the dependency model.

**Single active tactical per session.** At most one action per CWD can have active tactical steps. Enforced at `bon work` time. `_matches_session()` is the linchpin — `None` session means "only unscoped items," a real path means "this path OR unscoped." The `--force` flag overrides this when you deliberately want to switch.

**IDs are immutable and globally unique** across active and archived items. Pronounceable three-syllable format (`gabdur`, `mufene`). Mixed-case legacy IDs exist and must not be renamed.

**Atomic writes, deterministic order.** `save_items()` writes to `.tmp` then renames. Sort by ID before writing produces stable diffs. With `merge=union` in `.gitattributes`, concurrent branches touching different items merge cleanly. Same-item conflicts are intentional — they mean two sessions touched the same work.

**Dedup on load and save.** Both deduplicate by ID, keeping the version with the most recent timestamp. This makes union merges viable. The tradeoff: exact-same-second edits are a coin toss. Dedup prints to stderr but drops the older item without confirmation.

## The landmines

**`bon wait` destroys tactical state.** Waiting an action with steps in progress silently discards all tactical data. No confirmation. An agent that waits an action at 4/5 steps loses that progress permanently.

**External consumers read items.jsonl directly.** Trousse uses `jq` on the raw JSONL. Field names and structure are a contract that extends beyond this codebase. Don't rename fields.

**`KNOWN_VERBS` needs manual updates.** The frozenset in `storage.py` lists valid `updated_by` verbs. Adding a mutation command means adding its verb here. `bon doctor` validates against it, but nothing enforces sync.

**`error()` raises, doesn't print.** It raises `BonError`, caught in `main()`. Not print-and-exit. Better for control flow, but easy to misread.

**`cmd_work` argument parsing is fragile.** Uses `argparse.REMAINDER` with hand-rolled filtering of `--force` from positionals. The most duct-taped spot in the codebase. Don't use it as a template.

**The `.arc/` ghost.** Test infrastructure still uses the old name — `arc_dir` fixture, `run_arc()` helper, `arc-` prefixed fixtures. Not broken, but disorienting.

**`_reset_data_dir()` in conftest.** The autouse fixture that clears the cached data directory path between tests. Without it, the path from one test leaks into the next. If tests pass individually but fail together, check this first.

## The taste

**Legibility over abstraction.** No base classes, no registries. Each command is a self-contained function with the same boilerplate at the top. The repetition is deliberate — you can read any command in isolation.

**LLM-ergonomic first.** `--quiet` for agents to capture just the ID. `--json` for piping to `jq`. `--parent` aliased to `--outcome` because Claude's training priors are stronger on `--parent`. `check_outcome_language()` coaches agents away from activity framing ("Implement OAuth" → "Users can authenticate"). The tool bends to accommodate the model.

**Briefs are a forcing function.** `{why, what, done}` isn't metadata — it forces clear thinking. Numbered items in the `what` field become extractable tactical steps via `parse_steps_from_what()`, making the brief executable.

**Systemic over incremental.** When a pattern needs fixing, fix it everywhere at once. The `updated_by` verb system was added to all 10 mutation sites in one pass. The dedup mechanism was a general fix that made a specific bug irrelevant.

**The spec decides, the code implements.** Check SPEC.md before deciding behavior. The answer to "should it work this way?" is almost certainly already written down — though verify the spec still matches the code.
