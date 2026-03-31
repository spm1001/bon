# Verification Patterns

Reference for audit subagents verifying bon items against actual codebase state.

## By Brief Content Type

| Brief Pattern | Verification Method | Tools |
|--------------|---------------------|-------|
| References specific files/paths | Check existence, not deleted/renamed | `Glob`, `ls` |
| References functions/classes | Grep for definition in codebase | `Grep` |
| Describes implementation steps | Check git log for related commits since `created_at` | `git log --since` |
| Defines done criteria with tests | Check test file exists, optionally run | `Grep`, `Bash` |
| References config/endpoints | Check config files for the setting | `Grep`, `Read` |
| References external deps | Note as unverifiable — classify UNCLEAR | — |
| Recurring task (Todoist, cron) | Cannot verify runtime — classify UNCLEAR | — |

## Classification Criteria

| Classification | When to use |
|---------------|-------------|
| **DONE** | `--done` criteria verifiably met in current codebase |
| **STALE** | Brief references things that no longer exist, or codebase has diverged significantly from what's described |
| **ACTIVE** | Brief is current, work not yet done |
| **BLOCKED** | Has `waiting_for` set, or depends on external factor |
| **UNCLEAR** | Cannot determine programmatically — needs human judgment |

## Common Verification Sequences

### "Add X to file Y"
1. Check if Y exists (`Glob`)
2. Grep for X in Y
3. If both exist → likely DONE
4. If Y exists but X absent → ACTIVE
5. If Y doesn't exist → check git log for rename/deletion → STALE if deleted

### "Create module/file Z"
1. Check if Z exists in expected location
2. If exists and non-trivial → DONE
3. If exists but is a stub → ACTIVE (partially done)

### "Fix bug where..."
1. Grep for the error pattern or buggy code
2. Check git log for fix-related commits since `created_at`
3. If the buggy pattern is gone and fix commits exist → DONE
4. If the buggy pattern still exists → ACTIVE

### "Refactor X from A to B"
1. Grep for old pattern A
2. Grep for new pattern B
3. If A absent and B present → DONE
4. If both present → partially done, ACTIVE
5. If A present and B absent → ACTIVE

## Anti-Patterns (Things That Look Done But Aren't)

| Looks like | Actually |
|-----------|----------|
| File exists | But it's a stub or placeholder |
| Tests exist | But they're skipped (`@pytest.mark.skip`) |
| Config entry present | But commented out or set to default |
| Commit message mentions the work | But the commit was reverted |
| Function exists | But it's unreachable / never called |

## When to Classify UNCLEAR

- Brief references runtime behavior (API responses, user flows)
- Brief requires testing on a specific device
- Brief depends on external service state
- Brief references work in another repo not being audited
- Brief is vague enough that verification is ambiguous
