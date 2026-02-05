# Building Arc: Implementation Guide

Companion to SPEC.md. Describes **how** to build arc, including the orchestration pattern for multi-agent development.

---

## Decisions Made

- **Autonomy**: Medium leash - InnerClaudes get command-sized chunks (one command + its tests), OuterClaude reviews before proceeding
- **Bootstrap**: TodoWrite for Session 1, arc takes over from Session 2
- **Meta-approach**: Experimental branches to test orchestration pattern before committing

---

## Experimental Approach

We're testing the orchestration pattern itself, not just building arc. Branch structure:

```
main                          ← Frozen: SPEC.md + this guide
  └── experiment/orch-v1      ← First attempt at OuterClaude orchestration
        └── (learnings captured in NOTES.md)
  └── experiment/orch-v2      ← Second attempt with adjustments
        └── ...
  └── experiment/orch-vN      ← Working pattern emerges
        └── (merge to main when confident)
```

**Each experiment branch contains:**
- The actual implementation attempt
- `NOTES.md` capturing what worked, what didn't, questions that arose
- Commits showing the progression of InnerClaude outputs and OuterClaude decisions

**Exit criteria for experiments:**
- Pattern feels repeatable
- Failure modes are understood
- Ready to commit to building arc with confidence

**First experiment scope:** Full Phase 1 (all 6 InnerClaude tasks)

---

## The Orchestration Pattern

Within each session, OuterClaude:
1. Holds context (spec understanding, decisions, overall progress)
2. Spawns InnerClaude Task agents for implementation chunks
3. Reviews results, decides: accept / fix / redirect
4. Updates TodoWrite to track progress
5. Closes with handoff when session naturally ends

**InnerClaude chunk size (medium leash):**
- One command implementation + its tests
- E.g., "Implement `arc list` with snapshot tests for all fixtures"
- Can ask clarifying questions, OuterClaude answers from spec context

---

## Bamboo Scaffolding: The Test Strategy

### The Metaphor

Bamboo scaffolding:
- Goes up fast, adjusts easily
- Supports work without over-constraining
- Comes down when building stands alone
- Cheap to discard and rebuild

Steel scaffolding (what we avoid):
- Pre-planned, rigid
- Expensive to change
- Over-specified for the actual work

### Fixtures (from SPEC.md)

```
fixtures/
├── empty.jsonl                # Fixture 1
├── single_outcome.jsonl       # Fixture 2
├── outcome_with_actions.jsonl # Fixture 3
├── waiting_dependency.jsonl   # Fixture 4
├── multiple_outcomes.jsonl    # Fixture 5
├── standalone_actions.jsonl   # Fixture 6
└── all_waiting.jsonl          # Fixture 7
```

### Test Harness

```python
# tests/conftest.py
import subprocess
from pathlib import Path

def run_arc(*args, cwd=None, env=None):
    """Run arc CLI and return result."""
    result = subprocess.run(
        ["python", "-m", "arc.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env
    )
    return result

@pytest.fixture
def arc_dir(tmp_path):
    """Create temp dir with initialized .arc/"""
    (tmp_path / ".arc").mkdir()
    (tmp_path / ".arc/items.jsonl").touch()
    (tmp_path / ".arc/prefix").write_text("arc")
    return tmp_path

@pytest.fixture
def arc_dir_with_fixture(request, tmp_path, fixtures_dir):
    """Load a specific fixture into .arc/"""
    fixture_name = request.param
    (tmp_path / ".arc").mkdir()
    content = (fixtures_dir / f"{fixture_name}.jsonl").read_text()
    (tmp_path / ".arc/items.jsonl").write_text(content)
    (tmp_path / ".arc/prefix").write_text("arc")
    return tmp_path
```

### Snapshot Tests (the bamboo)

```python
# tests/test_list_snapshots.py

EXPECTED_OUTPUTS = {
    "empty": "No outcomes.\n",
    "single_outcome": "○ User auth (arc-aaa)\n",
    "outcome_with_actions": """\
○ User auth (arc-aaa)
  1. ✓ Add endpoint (arc-bbb)
  2. ○ Add UI (arc-ccc)
""",
    # ... etc from spec
}

@pytest.mark.parametrize("fixture,expected", EXPECTED_OUTPUTS.items())
def test_list_output(arc_dir_with_fixture, expected):
    result = run_arc("list", cwd=arc_dir_with_fixture)
    assert result.stdout == expected
```

### Why Bamboo, Not Steel

| We do | We don't |
|-------|----------|
| Snapshot expected CLI output | Mock internal functions |
| Test error message strings | Test argparse internals |
| Run real CLI in subprocess | Unit test each private method |
| Update snapshots when format changes | Fight tests during refactoring |

---

## Session 1 Plan: Phase 1 Core CLI

### TodoWrite Structure

```
1. [ ] Create project skeleton (pyproject.toml, src/arc/, tests/)
2. [ ] Create fixtures/ from spec
3. [ ] Create test harness (conftest.py with run_arc)
4. [ ] Implement arc init + test
5. [ ] Implement storage layer (load/save/find_by_id)
6. [ ] Implement arc new + tests (with brief validation)
7. [ ] Implement arc list + snapshot tests
8. [ ] Implement arc show + tests
9. [ ] Implement arc done + tests (including unblock behavior)
10. [ ] Verify all Phase 1 tests pass
11. [ ] Commit: "arc phase 1: core CLI"
```

### InnerClaude Task Sequence

**Task 1: Scaffold**
```
"Create arc project skeleton:
- pyproject.toml with uv, pytest
- src/arc/__init__.py, cli.py, storage.py, ids.py, queries.py, display.py
- tests/conftest.py with run_arc helper
- fixtures/ directory with all 7 fixtures from SPEC.md

Read SPEC.md for exact fixture content (Test Fixtures section).
Do NOT implement commands yet - just structure."
```

**Task 2: Storage + Init**
```
"Implement arc init and storage layer per SPEC.md:
- storage.py: load_items, save_items, load_prefix, find_by_id, get_creator, now_iso, validate_item
- cli.py: arc init command
- Test: arc init creates .arc/ with empty items.jsonl and prefix file

Read SPEC.md Storage Operations section for exact implementation."
```

**Task 3: ID Generation + New**
```
"Implement arc new per SPEC.md:
- ids.py: generate_id, generate_unique_id (pronounceable pattern)
- cli.py: arc new with --for, --why, --what, --done flags
- Brief validation (required, non-empty fields)
- Tests: create outcome, create action under outcome, error cases

Read SPEC.md sections: ID Generation, arc new behavior, Canonical Error Messages."
```

**Task 4: List + Display**
```
"Implement arc list per SPEC.md:
- display.py: format_hierarchical with filter_mode
- queries.py: filter_ready, filter_waiting
- cli.py: arc list with --ready, --waiting, --all flags
- Snapshot tests for all 7 fixtures

Expected outputs are in SPEC.md Test Fixtures section. Match exactly."
```

**Task 5: Show**
```
"Implement arc show per SPEC.md:
- cli.py: arc show ID
- Full detail output with brief fields
- For outcomes: include actions list
- Test against fixture 3 (outcome with actions)

Read SPEC.md arc show section for exact output format."
```

**Task 6: Done**
```
"Implement arc done per SPEC.md:
- cli.py: arc done ID
- Set status to done, add done_at timestamp
- CRITICAL: Clear waiting_for on items waiting for this one
- Tests: complete item, already done, unblock waiters

Read SPEC.md arc done section. Test with fixture 4 (waiting dependency)."
```

### Session 1 Exit Criteria

- `arc init`, `new`, `list`, `show`, `done` working
- All snapshot tests pass for Phase 1 commands
- `uv run pytest` green
- Ready to track Phase 2 using arc itself

---

## Sessions 2-4 (Tracked by Arc)

### Session 2: Phase 2

```bash
arc new "Dependencies & Editing" \
  --why "Phase 1 complete, need wait/unwait/edit for full workflow" \
  --what "1. arc wait ID REASON 2. arc unwait ID 3. arc edit ID (JSON in editor)" \
  --done "Fixture 4, 7 tests pass. Reorder logic works. Edit validates."
```

### Session 3: Phase 3

```bash
arc new "Polish" \
  --why "Core commands working, need status/help/json output" \
  --what "1. arc status 2. arc help [CMD] 3. --json and --jsonl flags" \
  --done "All error messages match spec. JSON output matches format_json spec."
```

### Session 4: Phase 4

```bash
arc new "Skill" \
  --why "CLI complete, need Claude workflow integration" \
  --what "arc/SKILL.md with draw-down, draw-up patterns" \
  --done "Skill loads, describes arc workflow clearly"
```

---

## Verification Strategy

**Per-command verification:**
1. Unit tests for pure functions (ids, queries)
2. Snapshot tests for CLI output
3. Error message tests against spec's canonical list

**End-to-end verification:**
```bash
# After Session 1:
uv run pytest tests/ -v

# Manual smoke test:
arc init --prefix test
arc new "Test outcome" --why "Testing" --what "Make it work" --done "It works"
arc new "Test action" --for test-<id> --why "Sub-task" --what "Do thing" --done "Thing done"
arc list
arc show test-<id>
arc done test-<action-id>
arc list --ready
```

---

## Files to Create

- `pyproject.toml`
- `src/arc/__init__.py`
- `src/arc/cli.py`
- `src/arc/storage.py`
- `src/arc/ids.py`
- `src/arc/queries.py`
- `src/arc/display.py`
- `tests/conftest.py`
- `tests/test_init.py`
- `tests/test_new.py`
- `tests/test_list.py`
- `tests/test_show.py`
- `tests/test_done.py`
- `fixtures/*.jsonl` (7 files)
