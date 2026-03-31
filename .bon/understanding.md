# Bon — Understanding

Bon is a CLI work tracker for Claude-human collaboration. JSONL by default, optional Dolt backend, no daemon. ~2,300 lines of core source plus a 470-line optional Dolt module. 384 tests. Designed primarily for AI agents — the human-at-keyboard path exists but is secondary.

## The data model

Two item types live in `.bon/items.jsonl` (or a shared Dolt database). An **outcome** is a desired result. An **action** is a concrete step toward an outcome.

```jsonl
{"id":"bon-jokeza","type":"outcome","title":"Draw-down suggests actions ranked by loaded context","brief":{"why":"...","what":"1. Add guidance... 2. Rank suggestions...","done":"After /open, Claude presents ready work with context-proximity reasoning"},"status":"open","order":6,"created_at":"2026-03-01T07:49:37Z","created_by":"spm1001"}
{"id":"bon-bebune","type":"action","title":"Raw-file health checks","brief":{"why":"...","what":"1. Read items.jsonl... 2. Flag malformed JSON...","done":"bon doctor on a bad file reports all issues with line numbers"},"status":"done","parent":"bon-mufene","order":1,"created_at":"2026-03-02T21:29:19Z","created_by":"spm1001","waiting_for":null,"tactical":{"steps":["Read items.jsonl line-by-line","Flag malformed JSON","Flag conflict markers","Flag duplicate IDs"],"current":4,"session":"/home/modha/Repos/bon"},"updated_at":"2026-03-02T21:32:24Z","updated_by":"stepped","done_at":"2026-03-02T21:32:24Z"}
```

Key fields: `brief` is mandatory — `{why, what, done}` required, `how` optional (approach/strategy). `parent` links an action to its outcome. `waiting_for` holds the ID of a blocking item. `tactical` tracks step-by-step progress within a session (steps list, current index, session identity). `updated_by` records the verb of the last mutation ("stepped", "waited", "edited").

**Statuses are simple.** An item is `open` or `done`. "Waiting" isn't a status — it's an open item that has a non-null `waiting_for`. "Ready" means open with no blocker. "Active" means it has tactical steps in progress.

**Lifecycle:** Created open. Optionally blocked with `bon wait` (sets `waiting_for`). Worked on with `bon work` (creates tactical steps from the brief's `what` field). Steps advanced with `bon step`. Completed with `bon done` or by finishing the final step. Archived with `bon archive` (moves to `.bon/archive.jsonl` or Dolt archive table).

## The architecture

`cli.py` is the bulk of the codebase — every command is a standalone function that loads items, mutates the in-memory list, and writes back. `storage.py` handles I/O, validation, and backend dispatch. When `.bon/backend` contains "dolt", six storage functions dispatch to `dolt.py` via lazy import — cli.py doesn't know which backend is active. `display.py`, `ids.py`, and `queries.py` are small support modules.

The complexity isn't in the code — it's in the spec. `SPEC.md` is 55k words, though it has drifted from implementation in places. When behavior is unclear, check the spec but verify against the code.

Every command follows the same pattern: `check_initialized()` → `load_items()` → mutate → `save_items()`. No exceptions. No middleware.

## Storage backends

**JSONL** (default): `.bon/items.jsonl`, git-tracked, zero dependencies. The original and still the right choice for single-machine work.

**Dolt** (optional): MySQL-compatible database with git semantics. Items scoped by prefix — all projects share one database, filtered by `id LIKE prefix-%`. Requires `pymysql` (`pip install bon[dolt]`). Connection via env vars or `~/.config/bon/dolt.toml`. Each write produces a Dolt commit. Session identity includes hostname to prevent cross-machine conflicts.

Backend dispatch is at the function boundary in `storage.py`. Six functions dispatch: `load_items`, `save_items`, `load_archive`, `append_archive`, `remove_from_archive`, and `items_path` (which raises in Dolt mode — there's no file). The `.bon/` directory still exists in Dolt mode — it holds `backend`, `prefix`, and local-only files.

`bon migrate --to dolt` and `bon migrate --to jsonl` move items between backends. `bon init --backend dolt` creates a new Dolt-backed project.

**Dolt in production** requires more than dolt.py. The server runs as a systemd user service (`dolt-bon.service`), needs `loginctl enable-linger` for headless machines, and a non-root database user scoped to the bon database only (`bon@'%'`). Dolt 1.83.6 removed `--user`/`--password` flags from `sql-server` — users are managed via SQL after auto-created root@localhost on first start. The `dolt sql` local CLI bypasses server auth entirely (runs in-process against the data directory). For multi-machine access, the server binds to 0.0.0.0 and each client machine needs `~/.config/bon/dolt.toml` pointing to the server's Tailscale IP. The pymysql dependency must be included in all install paths: `uv tool install` with `[dolt]` extras, `setup.sh`, `update-all.sh`, and the `ensure-bon.sh` advisory hint.

## The invariants

**Unblock on done.** When any item is marked done, all items whose `waiting_for` points to it get unblocked automatically. This cascade lives in both `cmd_done` and `cmd_step` (auto-complete on final step). It's the only cross-item mutation. Breaking it breaks the dependency model.

**Single active tactical per session.** At most one action per session can have active tactical steps. Enforced at `bon work` time. Session identity is `os.path.realpath(os.getcwd())` in JSONL mode, `hostname:realpath` in Dolt mode. `_matches_session()` is the linchpin — `None` session means "only unscoped items," a real path means "this path OR unscoped."

**IDs are immutable and globally unique** across active and archived items. Pronounceable three-syllable format (`gabdur`, `mufene`). Mixed-case legacy IDs exist and must not be renamed.

**Atomic writes, deterministic order.** `save_items()` writes to `.tmp` then renames (JSONL) or truncate-and-reinsert within a transaction (Dolt). Sort by ID before writing produces stable diffs. With `merge=union` in `.gitattributes`, concurrent JSONL branches touching different items merge cleanly.

**Dedup on load and save.** Both deduplicate by ID, keeping the version with the most recent timestamp. This contract holds for both backends.

## The landmines

**`bon wait` destroys tactical state.** Waiting an action with steps in progress silently discards all tactical data. No confirmation. An agent that waits an action at 4/5 steps loses that progress permanently.

**External consumers read items.jsonl directly.** `bon-read.sh` uses raw JSONL with embedded Python. In Dolt mode it falls back to the CLI. Field names and structure are a contract that extends beyond this codebase.

**`items_path()` raises in Dolt mode.** Code that calls it must check `_get_backend()` first or use `load_items()`/`save_items()` which dispatch automatically.

**`KNOWN_VERBS` needs manual updates.** The frozenset in `storage.py` lists valid `updated_by` verbs. Adding a mutation command means adding its verb here.

**`error()` raises, doesn't print.** It raises `BonError`, caught in `main()`. Not print-and-exit.

**`cmd_work` argument parsing is fragile.** Uses `argparse.REMAINDER` with hand-rolled filtering of `--force` from positionals. Don't use it as a template.

**Auto-handoff quoting is fragile.** `auto-handoff.sh` embeds shell variables into a `nohup bash -c '...'` string via sed single-quote escaping. Single quotes in git commit messages or bon item titles break the inner script. The mechanical fallback only runs when the LLM path isn't *attempted* (no transcript or no ccconv), not when it's attempted and *fails*. Silent failure — no output, no error.

**The `.arc/` ghost.** Test infrastructure still uses the old name — `arc_dir` fixture, `run_arc()` helper, `arc-` prefixed fixtures. Not broken, but disorienting.

## The taste

**Legibility over abstraction.** No base classes, no registries. Each command is a self-contained function with the same boilerplate at the top. The repetition is deliberate.

**LLM-ergonomic first.** `--quiet` for agents to capture just the ID. `--json` for piping. `--parent` aliased to `--outcome` because Claude's training priors are stronger on `--parent`. `check_outcome_language()` coaches agents away from activity framing.

**Briefs are a forcing function.** `{why, how, what, done}` forces clear thinking. `how` is optional — captures approach/strategy/constraints when the work is complex enough to need it. Numbered items in `what` become extractable tactical steps, making the brief executable. `bon work` surfaces `how` as "Approach:" context above the step list. A bon brief with all four fields replaces a plan file — the plan IS the bon hierarchy.

**Dispatch, not hierarchy.** The Dolt backend was added without class hierarchies or strategy patterns. Six `if _get_backend() == "dolt"` branches at function boundaries. Simple, readable, easy to remove if the experiment fails. The truncate-and-reinsert write strategy (DELETE all prefix rows, INSERT all, DOLT_COMMIT) deliberately mirrors JSONL's "rewrite the whole file" semantics — keeping both backends' concurrency guarantees identical at the cost of per-item efficiency that doesn't matter at bon's scale.

## The skills layer

Bon ships two Claude Code skills plus a session-start hook. `/bon` handles session orientation, draw-down/draw-up discipline, and teaches the plan-to-bon transmutation (create bon items instead of plan files). `/close` handles end-of-session capture via GODAR framework. `open-context.sh` is the hook that provides mechanical context (understanding, handoff, outcomes) before the LLM-mediated `/bon` ritual kicks in.

**Skill gates shape Claude behavior at critical moments.** The /close skill's Decide phase gates what goes into bon vs handoff prose. A previous gate ("if this never gets done, what breaks?") biased Claudes toward deferring actionable work into handoff text. In a real 12-hour mind-sweep, this produced 6 outcomes with zero actions — the entire breakdown step was skipped. The fix: bon is the default for anything specific enough to write `--why`/`--what`/`--done`. "Handoff only" is restricted to genuinely non-actionable context (open questions, taste judgments, architectural tensions). The lesson: gate questions in skills are load-bearing. A permissive gate at close time compounds — work that should be tracked disappears into prose that no future Claude will parse.

**Scripts live in `scripts/`, skills in `skills/*/`.** Both ship in the plugin cache. Path resolution must exclude `skills/*/scripts/` when searching for top-level scripts — `find -path "*/bon/*/scripts"` matches both because `*` spans `/` in `-path`.

**`~/.claude/rules/*.md` auto-loads into every session.** Confirmed by test (magic-word shard). This means plugins can own instruction shards without `@include` wiring in the global CLAUDE.md. The pattern: a plugin's SessionStart hook symlinks its `instructions.md` into `~/.claude/rules/<plugin>.md`. Plugin updates change the cache path; next session's hook re-symlinks to the new version. The `~/.claude/` write restriction only applies to Claude's tool use (Write/Edit), not to subprocess hooks — so hook scripts can create symlinks without permission prompts. This is the mechanism behind Workstream 5 of the enrichment plan.

**The briefing's "Suggested" section is a baton pass, not a board view.** It pulls from the previous handoff's Next items — the outgoing Claude's curated picks — not from `bon list --ready`. The full ready list is available on demand, but the startup stream carries only what the last Claude recommended. Bon IDs appear naturally when the outgoing Claude referenced them in handoff Next, giving the incoming Claude a direct `bon work` handle. This is Claude-to-Claude communication; human readability is secondary. When Suggested is in context from the hook, don't re-run `bon list` to pick direction — it's redundant and burns tokens. `bon list` is for the full picture: hierarchy, status, mid-session transitions, or auditing completeness.
