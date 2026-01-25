# Orchestration Experiment v1

## Approach

OuterClaude spawns InnerClaude Task agents for command-sized chunks.
Medium leash: review after each, decide proceed/fix/redirect.

**Scope:** Full Phase 1 (Tasks 1-6)

## Log

### Session 1: 2026-01-25

**Tasks completed:** All 8 (scaffold → commit)

**Time:** ~1 session

**Tests:** 67 passing

### Orchestration Observations

**What worked well:**

1. **Task chunking at command level** — Each InnerClaude got one command + its tests. This was the right granularity. Agents completed tasks cleanly without scope creep.

2. **Spec as context** — Having the full SPEC.md meant I could pass exact expected outputs to InnerClaudes. The snapshot tests match spec verbatim.

3. **Fixture-first approach** — Creating fixtures before implementing commands forced clarity. Tests became the spec.

4. **TodoWrite for tracking** — Kept progress visible. Dependencies helped sequence (storage before commands).

5. **Prompts with full code** — Rather than describing what to build, I included the exact code the InnerClaude should write. This eliminated ambiguity and reduced iteration.

**What could improve:**

1. **No iteration needed** — Every InnerClaude task succeeded on first try. This suggests either:
   - The prompts were detailed enough (good)
   - The tasks were too simple to stress-test the pattern (uncertain)
   - Phase 2 will be a better test of the "fix/redirect" loop

2. **Prompt size** — Full code in prompts is verbose. For more complex features, may need to reference spec sections instead. But it worked well here.

3. **Test coverage** — 67 tests feels comprehensive, but didn't test interactive mode (prompts). That's Phase 2 territory.

### Pattern Assessment

**Confidence level:** Medium-high

The pattern feels repeatable:
1. Read spec section for command
2. Write full implementation + tests in prompt
3. InnerClaude executes
4. OuterClaude verifies with pytest
5. Next task

**Questions for Phase 2:**
- How does the pattern handle failure/iteration?
- Is full-code-in-prompt sustainable at scale?
- When to use multiple InnerClaudes in parallel?

## Next Steps

Phase 2: `arc wait`, `arc unwait`, `arc edit`

Should be able to track Phase 2 using arc itself.
