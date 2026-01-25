# Orchestration Pattern: Building Arc

**Date:** 2026-01-25
**Branch:** `experiment/orch-v1`
**Outcome:** All 4 phases complete, 112 tests, pattern validated

---

## The Pattern

OuterClaude orchestrates, InnerClaudes implement. Hands stay clean.

```
OuterClaude (orchestrator)
    │
    ├─→ InnerClaude: Implement command + tests
    │   └─ Returns: "done" or questions
    │
    ├─→ InnerClaude (Opus): Review implementation
    │   └─ Returns: PASS/FAIL + findings
    │
    └─→ InnerClaude: Fix reviewer findings
        └─ Returns: "fixed"
```

### Task Chunking

**Right size:** One command + its tests per agent.

Examples:
- "Implement `arc init` with storage layer" ✓
- "Implement `arc new` with ID generation" ✓
- "Implement all Phase 1 commands" ✗ (too large)
- "Add one test" ✗ (too small)

### Prompt Style

**Prescriptive, not descriptive.** Include exact code to write.

```
❌ "Implement arc wait per the spec"
✓ "Add this function to cli.py: [exact code]"
```

This eliminated ambiguity. Every InnerClaude task succeeded first try.

### Verification Loop

1. InnerClaude returns "done"
2. OuterClaude runs `pytest`
3. Green → accept, Red → spawn fix agent
4. Opus reviewer audits after each phase
5. Findings become fix tasks

---

## What Worked

### 1. Fixture-First Development

Created test fixtures before implementing commands. The fixtures (from SPEC.md) became the source of truth. Snapshot tests matched expected output byte-for-byte.

### 2. Parallel Agent Spawning

Independent tasks ran in parallel:
- `arc wait` and `arc unwait` spawned together
- `arc status` and `arc help` spawned together

Reduced wall-clock time significantly.

### 3. Opus as Reviewer

Dedicated review agent found real issues:
- Phase 1: Dead code in `queries.py`, missing test
- Phase 2: Missing reorder-down test, parent validation tests
- Phase 3: `--jsonl` ignoring filters (spec deviation)

The fix-after-review loop caught bugs that tests missed.

### 4. Arc Dogfooding (Phase 4)

Used arc itself to track Phase 4:
```bash
arc new "Phase 4: Skill" --why "..." --what "..." --done "..."
arc new "Write SKILL.md" --for arc-gasoPe ...
arc wait arc-CuzaMi arc-HuZuDe  # review waits for implementation
```

Subagents used `arc show` to read assignments, `arc done` to complete. The unblock mechanism worked automatically.

---

## What Could Improve

### 1. No Iteration Needed

Every implementation task succeeded first try. This suggests either:
- Prompts were detailed enough (good)
- Tasks were too simple to stress-test iteration (uncertain)

A more complex project would test the "fix/redirect" loop more thoroughly.

### 2. Prompt Verbosity

Full code in prompts is verbose but effective. For larger features, might need:
- Reference spec sections by line number
- Trust agent to read and synthesize
- Accept more iteration

### 3. Context Efficiency

At session end: ~75% context used for 4 phases + reviews. The pattern is token-efficient because:
- Subagents don't consume orchestrator context
- Results come back as summaries
- Orchestrator stays lean (tracking + verification)

---

## The Numbers

| Phase | Commands | Tests Added | Subagents |
|-------|----------|-------------|-----------|
| 1 | init, new, list, show, done | 68 | 6 impl + 1 review + 1 fix |
| 2 | wait, unwait, edit | 26 | 3 impl + 1 review + 1 fix |
| 3 | status, help, flags | 18 | 3 impl + 1 review + 1 fix |
| 4 | skill | — | 1 impl + 1 review |

**Total:** 10 commands, 112 tests, ~15 subagent invocations

---

## Reproducing the Pattern

### For a new project:

1. **Write spec first** — Source of truth with expected outputs
2. **Create fixtures** — Test data before implementation
3. **Chunk by command** — One command + tests per agent
4. **Prescriptive prompts** — Include exact code
5. **Verify with pytest** — Green means accept
6. **Opus review per phase** — Catches what tests miss
7. **Fix via subagent** — Keep orchestrator hands clean

### Session structure:

```
Start:
  - Create TodoWrite tasks from plan
  - Set up dependencies

Per task:
  - Spawn implementation agent
  - Verify with pytest
  - Mark complete

Per phase:
  - Opus review
  - Spawn fix agent if needed
  - Commit and push

End:
  - Final verification
  - Update NOTES.md
  - Handoff
```

---

## Open Questions

1. **Failure modes:** What happens when an agent returns broken code? (Didn't occur)
2. **Scaling:** Does the pattern work for 50+ commands?
3. **Complexity:** How does `arc edit` (subprocess, validation, reorder) compare to truly complex features?
4. **Cross-session:** Can a fresh Claude resume mid-phase using arc + handoff?

---

## Conclusion

The orchestration pattern worked well for arc. Key insight: **prescriptive prompts + verification tests + dedicated reviewer** creates a reliable loop where the orchestrator maintains context while subagents do implementation.

The pattern is ready to apply to other projects. Start with detailed spec, chunk by feature, verify with tests, review with Opus.
