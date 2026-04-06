# Bon — Understanding

Bon is a CLI work tracker for Claude-human collaboration. JSONL by default, optional Dolt backend, no daemon. ~2,300 lines of core source plus a 470-line optional Dolt module. 418 tests. Designed primarily for AI agents — the human-at-keyboard path exists but is secondary.

## The data model

Two item types live in `.bon/items.jsonl` (or a shared Dolt database). An **outcome** is a desired result. An **action** is a concrete step toward an outcome.

```jsonl
{"id":"bon-jokeza","type":"outcome","title":"Draw-down suggests actions ranked by loaded context","brief":{"why":"...","what":"1. Add guidance... 2. Rank suggestions...","done":"After /open, Claude presents ready work with context-proximity reasoning"},"status":"open","order":6,"created_at":"2026-03-01T07:49:37Z","created_by":"spm1001"}
{"id":"bon-bebune","type":"action","title":"Raw-file health checks","brief":{"why":"...","what":"1. Read items.jsonl... 2. Flag malformed JSON...","done":"bon doctor on a bad file reports all issues with line numbers"},"status":"done","parent":"bon-mufene","order":1,"created_at":"2026-03-02T21:29:19Z","created_by":"spm1001","waiting_for":null,"tactical":{"steps":["Read items.jsonl line-by-line","Flag malformed JSON","Flag conflict markers","Flag duplicate IDs"],"current":4,"session":"/home/modha/Repos/bon"},"updated_at":"2026-03-02T21:32:24Z","updated_by":"stepped","done_at":"2026-03-02T21:32:24Z"}
```

Key fields: `brief` is mandatory — `{why, what, done}` required, `how` optional (approach/strategy). `parent` links an action to its outcome. `waiting_for` holds a **list** of blocker IDs (or `None`). `tactical` tracks step-by-step progress within a session (steps list, current index, session identity). `updated_by` records the verb of the last mutation ("stepped", "waited", "edited").

### Multi-blocker waiting_for

`waiting_for` is a list of strings, not a single string. `load_items()` normalises legacy single-string values to one-element lists via `_normalise_waiting_for()` in storage.py. In JSONL, stored as `"waiting_for": ["bon-abc", "bon-def"]`. In Dolt, lists are serialised as JSON array strings in the existing `VARCHAR(500)` column. `None` still means "not waiting." Empty list `[]` is normalised to `None` on save. Truthiness checks (`not item.get("waiting_for")`) work unchanged for both `None` and `[]`. The unblock-on-done cascade now removes the completed ID from all items' blocker lists and only fully unblocks when the list is empty (partial unblock). A parallel `wait_note` field stores optional context for why an item is blocked. External consumers that do exact string comparison (`waiting_for == "some-id"`) will break — they need to check membership in a list instead.

**Statuses are simple.** An item is `open` or `done`. "Waiting" isn't a status — it's an open item that has a non-null `waiting_for`. "Ready" means open with no blocker. "Active" means it has tactical steps in progress.

**Lifecycle:** Created open. Optionally blocked with `bon wait` (sets `waiting_for`). Worked on with `bon work` (creates tactical steps from the brief's `what` field). Steps advanced with `bon step`. Completed with `bon done` or by finishing the final step. Archived with `bon archive` (moves to `.bon/archive.jsonl` or Dolt archive table).

## The architecture

`cli.py` is the bulk of the codebase — every command is a standalone function that loads items, mutates the in-memory list, and writes back. `storage.py` handles I/O, validation, and backend dispatch. When `.bon/backend` contains "dolt", six storage functions dispatch to `dolt.py` via lazy import — cli.py doesn't know which backend is active. `display.py`, `ids.py`, and `queries.py` are small support modules.

The complexity isn't in the code — it's in the spec. `SPEC.md` is 55k words, though it has drifted from implementation in places. When behavior is unclear, check the spec but verify against the code.

Every command follows the same pattern: `check_initialized()` → `load_items()` → mutate → `save_items()`. No exceptions. No middleware.

## Storage backends

**Dolt is the universal backend.** As of April 2026, all 20 repos share a single Dolt database on hezza. JSONL support remains in the code (and `bon migrate --to jsonl` works for rollback), but no repo uses it in production. Every `.bon/` directory has a `backend` file containing "dolt".

**How Dolt works:** MySQL-compatible database with git semantics. Items scoped by prefix — all projects share one database, filtered by `id LIKE prefix-%`. Each write produces a Dolt commit. Requires `pymysql` (`pip install bon[dolt]`). Connection via env vars or `~/.config/bon/dolt.toml`.

Backend dispatch is at the function boundary in `storage.py`. Six functions dispatch: `load_items`, `save_items`, `load_archive`, `append_archive`, `remove_from_archive`, and `items_path` (which raises in Dolt mode — there's no file). The `.bon/` directory still exists in Dolt mode — it holds `backend`, `prefix`, and local-only files.

`bon migrate --to dolt` now verifies Dolt connectivity before switching the backend file (via `verify_dolt_connection()` in dolt.py). This prevents stranded data when Dolt is unreachable. `bon migrate --to jsonl` rolls back.

**Dolt in production:** The server runs as a systemd user service (`dolt-bon.service`), needs `loginctl enable-linger` for headless machines, and a non-root database user scoped to the bon database only (`bon@'%'`). Dolt 1.83.6 removed `--user`/`--password` flags from `sql-server` — users are managed via SQL after auto-created root@localhost on first start. The `dolt sql` local CLI bypasses server auth entirely (runs in-process against the data directory). For multi-machine access, the server binds to 0.0.0.0 and each client machine needs `~/.config/bon/dolt.toml` pointing to the server's Tailscale IP. The pymysql dependency must be included in all install paths: `uv tool install` with `[dolt]` extras, `setup.sh`, `update-all.sh`, and the `ensure-bon.sh` advisory hint.

**Scripts and hooks are Dolt-aware.** `bon-read.sh`, `bon-tactical.sh`, `open-context.sh`, and `ensure-bon.sh` all check `.bon/backend` and dispatch to the CLI for Dolt repos. Cross-repo consumers (`garde-manger/adapters/bon.py`, `trousse/scripts/bon-survey.py`, `bon/skills/review/scripts/audit_survey.py`) also detect backend and use `bon list --jsonl` for Dolt repos. The instruction shard documents Dolt recovery (`systemctl --user start dolt-bon.service`).

**The migration lesson: blast radius is in the consumers.** The Dolt code change was straightforward. The real work was finding four scripts across three repos that read `items.jsonl` directly and would have silently produced empty results after migration. The fix pattern is uniform (check `.bon/backend`, dispatch to CLI for Dolt, keep direct reads for JSONL), but discovery requires knowing every consumer exists — and they're scattered. Before any storage migration, grep for the old filename across ALL repos. Infrastructure transitions have two phases: Phase 1 is making the new thing work; Phase 2 is making everything else aware the old thing is gone. Phase 2 is where reliability lives.

**Ghost files.** After migration, `.bon/items.jsonl.pre-dolt` backup files exist in each repo. These are rollback insurance — no script reads them. `open-context.sh` warns if a stale `items.jsonl` (not `.pre-dolt`) exists alongside `backend=dolt`.

## The invariants

**Unblock on done.** When any item is marked done, all items whose `waiting_for` contains it get that ID removed from their blocker list. Full unblock happens only when the list becomes empty. This cascade lives in both `cmd_done` and `cmd_step` (auto-complete on final step). Breaking it breaks the dependency model.

**Single active tactical per session.** At most one action per session can have active tactical steps. Enforced at `bon work` time. Session identity is `os.path.realpath(os.getcwd())` in JSONL mode, `hostname:realpath` in Dolt mode. `_matches_session()` is the linchpin — `None` session means "only unscoped items," a real path means "this path OR unscoped."

**IDs are immutable and globally unique** across active and archived items. Pronounceable three-syllable format (`gabdur`, `mufene`). Mixed-case legacy IDs exist and must not be renamed.

**Atomic writes, deterministic order.** `save_items()` writes to `.tmp` then renames (JSONL) or truncate-and-reinsert within a transaction (Dolt). Sort by ID before writing produces stable diffs. With `merge=union` in `.gitattributes`, concurrent JSONL branches touching different items merge cleanly.

**Dedup on load and save.** Both deduplicate by ID, keeping the version with the most recent timestamp. This contract holds for both backends.

## The landmines

**`bon wait` destroys tactical state.** Waiting an action with steps in progress silently discards all tactical data. No confirmation. An agent that waits an action at 4/5 steps loses that progress permanently.

**External consumers read items.jsonl directly.** `bon-read.sh` uses raw JSONL with embedded Python. In Dolt mode it falls back to the CLI. Field names and structure are a contract that extends beyond this codebase. The `waiting_for` change from string to list is a breaking change for external consumers doing exact string comparison.

**`items_path()` raises in Dolt mode.** Code that calls it must check `_get_backend()` first or use `load_items()`/`save_items()` which dispatch automatically.

**`.pre-dolt` backup files don't mean migration failed.** `bon migrate --to dolt` leaves `.bon/items.jsonl.pre-dolt` as a safety backup. A subagent reading this file and inferring "Dolt migration is broken" nearly caused the working backend to be overwritten with stale JSONL. The backup's existence is normal. To verify backend health: run `bon list` and check the exit code. Don't infer state from artefacts when you can query the live system.

**`KNOWN_VERBS` needs manual updates.** The frozenset in `storage.py` lists valid `updated_by` verbs. Adding a mutation command means adding its verb here.

**`error()` raises, doesn't print.** It raises `BonError`, caught in `main()`. Not print-and-exit.

**`cmd_work` argument parsing is fragile.** Uses `argparse.REMAINDER` with hand-rolled filtering of `--force` from positionals. Don't use it as a template.

**The `.arc/` ghost.** Test infrastructure still uses the old name — `arc_dir` fixture, `run_arc()` helper, `arc-` prefixed fixtures. Not broken, but disorienting.

## The brief's optional fields

**`--how` is a self-contained string field**, not a linked document reference. Design is deliberate — bon items should replace plan files entirely, not reference external documents. `_normalize_brief()` in `display.py` ensures JSON output always includes `how: null` for items without it, without polluting stored JSONL. `OPTIONAL_BRIEF_FIELDS` dict in `storage.py` is the single point where optional-vs-required is declared.

## Handoff resolution

Handoff resolution uses a three-tier strategy: walk up from CWD for `.bon/handoffs/`, scan down for the child repo with the most recent git commit (covering container dirs like `~/Repos`), then fall back to `~/.bon/handoffs/` as a global catch-all. The legacy `~/.claude/handoffs/` path is fully eliminated. The scan-down heuristic uses "most recent commit timestamp" rather than "most commits in N hours" because at close time the session's repo typically has the single freshest commit. The scan-down filters to git repos only via `git rev-parse --git-dir`. The global `~/.bon/` directory is safe from `check_initialized()` because it looks for `.bon/items.jsonl`, which won't exist there.

## Script resolution in skills

**`find | head -1` is wrong for locating scripts across cached plugin versions.** It picks whichever version comes first in filesystem order, not the latest. The fix is `ls -td` (sort by modification time, newest first). Any script-finding pattern in skills should use this approach. This is the root cause behind bon-venasi (close skill picks stale scripts).

## Emotional register as instructional design

Instructional text is emotional regulation. The CSO scoring rubric awarded 10/25 points for MANDATORY — the highest score for the strongest threat-register word — which incentivised every skill in the ecosystem to open with a shouted command. Anthropic's research shows these patterns causally increase corner-cutting in model behaviour, even when the output looks composed. The fix is reforming the scoring system, not just softening individual files. The `register-principles.md` reference document in skill-forge captures the full framework.

**Surface-level lint is necessary but insufficient.** The register lint tool (`lint_skill.py`'s `check_register()`) checks ALL CAPS density, negation ratio, and opening tone. These catch the obvious patterns but miss subtler stress generators: threat framing ("broken scripts mean lost handoffs"), constraint density (seven-row mistake tables), conditional punishment ("if you skip this, future Claude can't prioritise"), and urgency stacking (bold + table + bold). The amp-close skill passed lint at 50% negation ratio, suggesting thresholds may be miscalibrated. The deeper question is document posture — does the text assume competence and provide context, or assume failure risk and provide guardrails? These produce measurably different model behaviour but aren't greppable. bon-kaviru tracks approach design for posture-level analysis.

## The taste

**Legibility over abstraction.** No base classes, no registries. Each command is a self-contained function with the same boilerplate at the top. The repetition is deliberate.

**LLM-ergonomic first.** `--quiet` for agents to capture just the ID. `--json` for piping. `--parent` aliased to `--outcome` because Claude's training priors are stronger on `--parent`. `check_outcome_language()` coaches agents away from activity framing. **Skill prose cannot override Claude's procedural priors** — four iterations of increasingly forceful skill guidance failed to make test Claudes pipe JSON to `bon new` instead of using flags. The fix was making JSON-from-stdin the CLI default (change the tool, not the instructions). This principle applies broadly: when the "right" invocation differs from what Claude learned in training, change the CLI's default behavior rather than fighting the prior with documentation.

**Briefs are a forcing function.** `{why, how, what, done}` forces clear thinking. `how` is optional — captures approach/strategy/constraints when the work is complex enough to need it. Numbered items in `what` become extractable tactical steps, making the brief executable. `bon work` surfaces `how` as "Approach:" context above the step list. A bon brief with all four fields replaces a plan file — the plan IS the bon hierarchy.

**Dispatch, not hierarchy.** The Dolt backend was added without class hierarchies or strategy patterns. Six `if _get_backend() == "dolt"` branches at function boundaries. Simple, readable, easy to remove if the experiment fails. The truncate-and-reinsert write strategy (DELETE all prefix rows, INSERT all, DOLT_COMMIT) deliberately mirrors JSONL's "rewrite the whole file" semantics — keeping both backends' concurrency guarantees identical at the cost of per-item efficiency that doesn't matter at bon's scale.

## The skills layer

Bon ships three Claude Code skills plus a session-start hook. `/open` handles session orientation — synthesizing knowledge from the previous handoff's "For Claudes to come" zone into understanding.md, draw-down/draw-up discipline, and the plan-to-bon transmutation. `/close` handles end-of-session reflection and produces a two-zone handoff: "For the next Claude" (operational context — done, risks, opportunities) and "For Claudes to come" (durable knowledge for understanding.md synthesis). `/review` orchestrates periodic backlog review. `open-context.sh` is the hook that provides mechanical context (understanding, handoff, outcomes) before the LLM-mediated `/open` ritual kicks in.

**Three temporal rhythms govern the session lifecycle.** Rapid-cycle (~30 /close+/open pairs per day) carries operational context via Gotchas/Next in the handoff's "For the next Claude" zone. Overnight composting carries durable insight — Learned sections flow into understanding.md, Done sections feed garde-manger extraction. Anthropic's background system (autoDream) consolidates MEMORY.md from session transcripts, carrying typed observations (feedback/project/reference). The handoff's two-zone structure maps directly to the first two rhythms. We don't need to write to MEMORY.md explicitly — a rich handoff in the session transcript feeds Anthropic's system naturally.

**Skill gates shape Claude behavior at critical moments.** The /close skill's Reflect phase gates what goes into bon vs handoff prose. A previous gate ("if this never gets done, what breaks?") biased Claudes toward deferring actionable work into handoff text. In a real 12-hour mind-sweep, this produced 6 outcomes with zero actions — the entire breakdown step was skipped. The fix: bon is the default for anything specific enough to write `--why`/`--what`/`--done`. "Handoff only" is restricted to genuinely non-actionable context (open questions, taste judgments, architectural tensions). The lesson: gate questions in skills are load-bearing. A permissive gate at close time compounds — work that should be tracked disappears into prose that no future Claude will parse.

**Scripts live in `scripts/`, skills in `skills/*/`.** Both ship in the plugin cache. Path resolution must exclude `skills/*/scripts/` when searching for top-level scripts — `find -path "*/bon/*/scripts"` matches both because `*` spans `/` in `-path`.

**`~/.claude/rules/*.md` auto-loads into every session.** Confirmed by test (magic-word shard). This means plugins can own instruction shards without `@include` wiring in the global CLAUDE.md. The pattern: a plugin's SessionStart hook symlinks its `instructions.md` into `~/.claude/rules/<plugin>.md`, using BASH_SOURCE-relative resolution so version updates auto-propagate. The `~/.claude/` write restriction only applies to Claude's tool use (Write/Edit), not to subprocess hooks — so hook scripts can create symlinks without permission prompts.

**Instruction shards separate always-on rules from skill context.** Shards in `~/.claude/rules/` carry only gates and overrides (e.g. "use bon not TodoWrite", "passe fetch not WebFetch"). Full instructions live in SKILL.md and load when the skill is invoked — no duplication. The `@context/` include mechanism and `rules/` auto-load are complementary: `@context` is hand-curated composition controlled by CLAUDE.md, `rules/` is plugin-managed auto-load controlled by directory contents.

**Rules files support path-scoping via YAML frontmatter.** Without frontmatter, rules are unconditional (always loaded). With a `paths:` field, rules only activate when Claude is working on files matching those glob patterns. Syntax: `---\npaths:\n  - "src/**"\n---`. Batterie instruction shards are unconditional (behavioral overrides apply everywhere), but path-scoped rules are available for file-type-specific instructions.

## Plugin resolution gotchas

**Claude Code resolves plugin skills by directory name, not the SKILL.md `name:` field.** Renaming the `name:` without renaming the directory means the old invocation path stays active and the new one never registers. Similarly, hook scripts in `hooks/` are inert unless registered in `plugin.json` under the `"hooks"` key — the runtime doesn't scan directories. Both are silent failures: no error, just nothing happens. A version bump is required after fixing either, because `claude plugin update` compares versions, not content — same version means "already up to date" even if files changed.

**The publish pipeline is sequential and unforgiving.** Edit source → commit → push to GitHub → `claude plugin marketplace update` → `claude plugin update` → CLI reinstall (`uv cache clean + uv tool install --force --reinstall`) → full session restart (`/exit` then `claude`). Reloading plugins mid-session doesn't trigger SessionStart hooks or refresh already-loaded SKILL.md content. The marketplace index fetches from GitHub at update time — pushing IS publishing — but the version in `plugin.json` must change or `update` reports "already up to date" even when files differ. Every step is a potential silent failure point.

**The briefing's "Suggested" section is a baton pass, not a board view.** It pulls from the previous handoff's Opportunities (fond-v1) or Next items (legacy) — the outgoing Claude's curated picks — not from `bon list --ready`. The full ready list is available on demand, but the startup stream carries only what the last Claude recommended. Bon IDs appear naturally when the outgoing Claude referenced them in handoff Opportunities, giving the incoming Claude a direct `bon work` handle. This is Claude-to-Claude communication; human readability is secondary. When Suggested is in context from the hook, don't re-run `bon list` to pick direction — it's redundant and burns tokens. `bon list` is for the full picture: hierarchy, status, mid-session transitions, or auditing completeness.
