# InnerPlan: The Arc Specification

**Version:** 2.1-draft
**Date:** 2026-01-25
**Status:** Ready for implementation

---

## Vision

Arc is a lightweight work tracker designed for Claude-human collaboration.

**The problem:** Existing tools (Jira, Linear, beads) are built for human teams with human assumptions — dashboards, sprints, standups. When Claude uses these tools, the vocabulary triggers training-deep responses: "blocker" creates panic, "P0" triggers urgency, "backlog" implies burden.

**The solution:** Arc uses GTD-aligned vocabulary that encourages thoughtful, leisurely development. Work is organized as *Outcomes* (what we're trying to achieve) and *Actions* (concrete next steps). There are no sprints, no story points, no priority levels — just ordering and a clear answer to "what can I work on now?"

### Design Principles

1. **LLM-ergonomic first, human-ergonomic second** — JSON APIs, predictable commands
2. **GTD-aligned vocabulary** — Outcomes not Epics, Waiting not Blocked
3. **No daemon, no dual-database** — JSONL is the source of truth
4. **Works on Google Drive** — No SQLite, no file locking requirements
5. **Hierarchical by default** — Claudes naturally flatten; arc enforces structure
6. **Natural syntax = correct syntax** — Output works with grep, jq without gymnastics
7. **Tiny, fast, reliable** — 12 commands, not 86

### Open Question: Tool Name

The CLI command is `arc` (avoids collision with Unix `ar` archive utility).

The tool name "arc" works but isn't as natural as "bead" for human speech:
- "Make a bead for that" ✓ natural
- "Make an arc for that" ⚠️ acceptable

Alternatives under consideration: `pebble`, `mark`, `pin`. No decision yet.

---

## Vocabulary

### What We Say

| Term | Definition |
|------|------------|
| **Outcome** | A result worth achieving. Has actions. "Users can authenticate with GitHub" |
| **Action** | A concrete next step. Belongs to an outcome. "Add OAuth callback endpoint" |
| **Report** | An observation from the field. Orphan until promoted. |
| **Waiting** | Something that must happen first. Not "blocked" — waiting. |
| **Ready** | Can be worked on now. Open, not waiting. |
| **Done** | Completed. |

### What We Don't Say

| Banned | Why |
|--------|-----|
| Epic, Sprint, Story | Agile ceremony triggers |
| Blocker, Blocked | Panic-inducing |
| P0, P1, Critical, Priority | Urgency theater — use ordering instead |
| Backlog | Burden framing |
| Ticket | Bureaucratic |
| Tags, Labels | Unnecessary complexity — ordering is enough |

---

## Data Model

### Directory Structure

```
.arc/
├── items.jsonl    # All items (outcomes, actions, reports)
└── prefix         # Just the prefix string, e.g. "arc"
```

No SQLite. No daemon. No config.yaml. Git tracks history.

### The `prefix` File

Contains the prefix string only, **no trailing newline**.

```bash
# Create
echo -n "myproject" > .arc/prefix

# Read
PREFIX=$(cat .arc/prefix)
```

If missing, default to `"arc"`.

Used only for generating new IDs — existing IDs are not validated against it.

### Item Schema

All fields shown. **Bold** = required, others optional.

**Outcome:**
```json
{
  "id": "arc-gaBdur",
  "type": "outcome",
  "title": "Users can authenticate with GitHub",
  "description": "OAuth flow for GitHub login.\nInclude token refresh.",
  "status": "open",
  "order": 1,
  "created_at": "2026-01-25T10:30:00Z",
  "created_by": "sameer"
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | ✓ | string | `{prefix}-{hash}` |
| `type` | ✓ | `"outcome"` | |
| `title` | ✓ | string | Short, one line |
| `description` | | string | Multi-line OK, use `\n` |
| `status` | ✓ | `"open"` or `"done"` | |
| `order` | ✓ | integer | Position among outcomes |
| `created_at` | ✓ | ISO8601 | |
| `created_by` | ✓ | string | |

**Action:**
```json
{
  "id": "arc-zoKte",
  "type": "action",
  "title": "Add OAuth callback endpoint",
  "description": null,
  "status": "open",
  "parent": "arc-gaBdur",
  "order": 1,
  "created_at": "2026-01-25T10:31:00Z",
  "created_by": "claude-session-abc123",
  "waiting_for": null
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | ✓ | string | `{prefix}-{hash}` |
| `type` | ✓ | `"action"` | |
| `title` | ✓ | string | |
| `description` | | string | Optional, usually null |
| `status` | ✓ | `"open"` or `"done"` | |
| `parent` | ✓ | string | Parent outcome ID |
| `order` | ✓ | integer | Position within parent |
| `created_at` | ✓ | ISO8601 | |
| `created_by` | ✓ | string | |
| `waiting_for` | | string or null | ID or free text |

**Report:**
```json
{
  "id": "rpt-miFola",
  "type": "report",
  "title": "OAuth callback seems broken",
  "body": "Malformed tokens cause 500 instead of 400.\n\nRepro steps:\n1. Start auth\n2. Tamper token",
  "status": "open",
  "created_at": "2026-01-25T11:00:00Z",
  "created_by": "claude-session-def456"
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | ✓ | string | Always `rpt-{hash}` |
| `type` | ✓ | `"report"` | |
| `title` | ✓ | string | |
| `body` | | string | Longer description |
| `status` | ✓ | `"open"` or `"done"` | |
| `created_at` | ✓ | ISO8601 | |
| `created_by` | ✓ | string | |

### ID Generation

Pronounceable hashes for human-friendly, collision-resistant IDs.

```python
import random

CONSONANTS = "bcdfghjklmnprstvwz"  # No ambiguous: q, x, y
VOWELS = "aeiou"

def generate_id(prefix: str = "arc") -> str:
    """Generate pronounceable ID like 'arc-gaBdur'."""
    syllables = []
    for _ in range(3):
        c = random.choice(CONSONANTS)
        v = random.choice(VOWELS)
        # 30% chance to capitalize consonant
        if random.random() < 0.3:
            c = c.upper()
        syllables.append(c + v)
    return f"{prefix}-{''.join(syllables)}"

def generate_unique_id(prefix: str, existing_ids: set[str]) -> str:
    """Generate ID that doesn't collide with existing."""
    for _ in range(100):  # Safety limit
        new_id = generate_id(prefix)
        if new_id not in existing_ids:
            return new_id
    raise RuntimeError("Failed to generate unique ID after 100 attempts")
```

Reports always use `rpt-` prefix regardless of project prefix.

### Order Assignment

When creating a new item, assign `order` as:

```python
def next_order(items: list[dict], parent: str | None = None) -> int:
    """Get next order value for new item."""
    if parent:
        # Action: max order among siblings + 1
        siblings = [i for i in items if i.get("parent") == parent]
    else:
        # Outcome: max order among outcomes + 1
        siblings = [i for i in items if i["type"] == "outcome"]

    if not siblings:
        return 1
    return max(i.get("order", 0) for i in siblings) + 1
```

---

## CLI Reference

### Commands (12)

```
arc new "title" [--for PARENT]   Create outcome (or action if --for)
arc done ID                       Complete item
arc show ID                       View item with actions
arc list [--ready|--waiting]      List items (hierarchical)
arc wait ID REASON                Mark as waiting
arc unwait ID                     Clear waiting
arc edit ID                       Edit in $EDITOR
arc report "title"                Create report (orphan)
arc inbox                         List reports
arc status                        Overview
arc init                          Initialize .arc/
arc help                          Show help
```

### Global Flags

| Flag | Description |
|------|-------------|
| `--json` | Nested JSON output (machine-friendly) |
| `--jsonl` | Flat JSONL output (raw) |
| `--quiet` | Minimal output (just ID on create) |

---

## Command Behaviors

### `arc init`

```bash
arc init [--prefix PREFIX]
```

Creates `.arc/` directory with empty `items.jsonl` and `prefix` file.

```python
def init(prefix: str = "arc"):
    Path(".arc").mkdir(exist_ok=True)
    Path(".arc/items.jsonl").touch()
    Path(".arc/prefix").write_text(prefix)  # No trailing newline
    print(f"Initialized .arc/ with prefix '{prefix}'")
```

### `arc new`

```bash
arc new "title" [--for PARENT]
```

Creates outcome (default) or action (if `--for`).

```python
def new(title: str, parent: str | None = None):
    items = load_items()
    prefix = load_prefix()
    existing_ids = {i["id"] for i in items}

    if parent:
        # Validate parent exists and is an outcome
        parent_item = find_by_id(items, parent)
        if not parent_item:
            error(f"Parent '{parent}' not found")
        if parent_item["type"] != "outcome":
            error(f"Parent must be an outcome, got {parent_item['type']}")

        item = {
            "id": generate_unique_id(prefix, existing_ids),
            "type": "action",
            "title": title,
            "status": "open",
            "parent": parent,
            "order": next_order(items, parent),
            "created_at": now_iso(),
            "created_by": get_creator(),
            "waiting_for": None,
        }
    else:
        item = {
            "id": generate_unique_id(prefix, existing_ids),
            "type": "outcome",
            "title": title,
            "status": "open",
            "order": next_order(items, None),
            "created_at": now_iso(),
            "created_by": get_creator(),
        }

    items.append(item)
    save_items(items)
    print(f"Created: {item['id']}")
```

### `arc done`

```bash
arc done ID
```

Marks item as done. **Crucially:** clears `waiting_for` on any items waiting for this one.

```python
def done(item_id: str):
    items = load_items()
    item = find_by_id(items, item_id)
    if not item:
        error(f"Item '{item_id}' not found")

    # Mark as done
    item["status"] = "done"
    item["done_at"] = now_iso()

    # Unblock waiters
    unblocked = []
    for other in items:
        if other.get("waiting_for") == item_id:
            other["waiting_for"] = None
            unblocked.append(other["id"])

    save_items(items)
    print(f"Done: {item_id}")
    if unblocked:
        print(f"Unblocked: {', '.join(unblocked)}")
```

**Note:** `waiting_for` can be an item ID or free text. Only clear if it matches the completed item's ID exactly.

### `arc wait`

```bash
arc wait ID REASON
```

REASON can be another item ID or free text.

```python
def wait(item_id: str, reason: str):
    items = load_items()
    item = find_by_id(items, item_id)
    if not item:
        error(f"Item '{item_id}' not found")

    item["waiting_for"] = reason
    save_items(items)
    print(f"{item_id} now waiting for: {reason}")
```

### `arc unwait`

```bash
arc unwait ID
```

Clears `waiting_for`.

```python
def unwait(item_id: str):
    items = load_items()
    item = find_by_id(items, item_id)
    if not item:
        error(f"Item '{item_id}' not found")

    item["waiting_for"] = None
    save_items(items)
    print(f"{item_id} no longer waiting")
```

### `arc edit`

```bash
arc edit ID
```

Opens item in `$EDITOR` as YAML. Saves changes back.

```python
import subprocess
import tempfile
import yaml

def edit(item_id: str):
    items = load_items()
    item = find_by_id(items, item_id)
    if not item:
        error(f"Item '{item_id}' not found")

    # Write to temp file as YAML
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(item, f, default_flow_style=False, allow_unicode=True)
        temp_path = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, temp_path], check=True)

    # Read back
    with open(temp_path) as f:
        edited = yaml.safe_load(f)
    os.unlink(temp_path)

    # Validate: ID cannot change
    if edited.get("id") != item_id:
        error("Cannot change item ID")

    # Update in list
    for i, existing in enumerate(items):
        if existing["id"] == item_id:
            items[i] = edited
            break

    save_items(items)
    print(f"Updated: {item_id}")
```

**YAML format allows multi-line descriptions:**
```yaml
id: arc-gaBdur
type: outcome
title: Users can authenticate with GitHub
description: |
  OAuth flow for GitHub login.
  Include token refresh.
  Handle edge cases.
status: open
order: 1
created_at: '2026-01-25T10:30:00Z'
created_by: sameer
```

### `arc report`

```bash
arc report "title"
```

Creates a report (orphan) with `rpt-` prefix.

```python
def report(title: str):
    items = load_items()
    existing_ids = {i["id"] for i in items}

    item = {
        "id": generate_unique_id("rpt", existing_ids),
        "type": "report",
        "title": title,
        "status": "open",
        "created_at": now_iso(),
        "created_by": get_creator(),
    }

    items.append(item)
    save_items(items)
    print(f"Created: {item['id']}")
```

### Report Promotion

There is no `promote` command. Promotion is done via `arc edit`:

1. Open report: `arc edit rpt-miFola`
2. Change `type` from `"report"` to `"action"`
3. Add `parent` field with outcome ID
4. Add `order` field
5. Optionally change `id` from `rpt-` to match project prefix

**Or create-and-dismiss:**
```bash
arc new "Fix the bug described in rpt-miFola" --for arc-gaBdur
arc done rpt-miFola
```

### `arc show`

```bash
arc show ID
```

Displays a single item with full details. For outcomes, includes all actions.

```python
def show(item_id: str):
    items = load_items()
    item = find_by_id(items, item_id)
    if not item:
        error(f"Item '{item_id}' not found")

    # Header
    status_icon = "✓" if item["status"] == "done" else "○"
    print(f"{status_icon} {item['title']} ({item['id']})")
    print(f"   Type: {item['type']}")
    print(f"   Status: {item['status']}")
    print(f"   Created: {item['created_at']} by {item['created_by']}")

    if item.get("waiting_for"):
        print(f"   Waiting for: {item['waiting_for']}")

    if item.get("description"):
        print(f"\n   {item['description']}")

    # For outcomes, show actions
    if item["type"] == "outcome":
        actions = sorted(
            [i for i in items if i.get("parent") == item_id],
            key=lambda x: x.get("order", 999)
        )
        if actions:
            print("\n   Actions:")
            for action in actions:
                a_icon = "✓" if action["status"] == "done" else "○"
                waiting = f" ⏳ {action['waiting_for']}" if action.get("waiting_for") else ""
                print(f"   {action.get('order', '?')}. {a_icon} {action['title']} ({action['id']}){waiting}")
```

**Example output for outcome:**
```
○ User authentication (arc-gaBdur)
   Type: outcome
   Status: open
   Created: 2026-01-25T10:30:00Z by sameer

   OAuth flow for GitHub login. Include token refresh.

   Actions:
   1. ✓ Add OAuth endpoint (arc-zoKte)
   2. ○ Add token refresh (arc-miFola) ⏳ arc-zoKte
   3. ○ Add logout (arc-haVone)
```

**Example output for action:**
```
○ Add OAuth endpoint (arc-zoKte)
   Type: action
   Status: open
   Created: 2026-01-25T10:31:00Z by claude-session-abc123
   Waiting for: arc-miFola
```

### `arc status`

```bash
arc status
```

Shows overview of current state.

```python
def status():
    items = load_items()
    prefix = load_prefix()

    outcomes = [i for i in items if i["type"] == "outcome"]
    actions = [i for i in items if i["type"] == "action"]
    reports = [i for i in items if i["type"] == "report"]

    open_outcomes = [i for i in outcomes if i["status"] == "open"]
    done_outcomes = [i for i in outcomes if i["status"] == "done"]

    open_actions = [i for i in actions if i["status"] == "open"]
    done_actions = [i for i in actions if i["status"] == "done"]
    waiting_actions = [i for i in actions if i.get("waiting_for")]
    ready_actions = [i for i in open_actions if not i.get("waiting_for")]

    open_reports = [i for i in reports if i["status"] == "open"]

    print(f"Arc status (prefix: {prefix})")
    print()
    print(f"Outcomes:  {len(open_outcomes)} open, {len(done_outcomes)} done")
    print(f"Actions:   {len(open_actions)} open ({len(ready_actions)} ready, {len(waiting_actions)} waiting), {len(done_actions)} done")
    print(f"Reports:   {len(open_reports)} pending")
```

**Example output:**
```
Arc status (prefix: arc)

Outcomes:  3 open, 2 done
Actions:   8 open (5 ready, 3 waiting), 12 done
Reports:   2 pending
```

---

## Output Format

### Hierarchical Output Algorithm

```python
def format_hierarchical(items: list[dict]) -> str:
    """Format items as hierarchical text output."""
    lines = []

    # Get outcomes sorted by order
    outcomes = sorted(
        [i for i in items if i["type"] == "outcome" and i["status"] == "open"],
        key=lambda x: x.get("order", 999)
    )

    for outcome in outcomes:
        # Outcome line
        status_icon = "✓" if outcome["status"] == "done" else "○"
        lines.append(f"{status_icon} {outcome['title']} ({outcome['id']})")

        # Get actions for this outcome, sorted by order
        actions = sorted(
            [i for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", 999)
        )

        for action in actions:
            order_num = action.get("order", "?")
            if action["status"] == "done":
                status_icon = "✓"
            elif action.get("waiting_for"):
                status_icon = "○"  # Still open, but...
                waiting_suffix = f" ⏳ {action['waiting_for']}"
            else:
                status_icon = "○"
                waiting_suffix = ""

            lines.append(f"  {order_num}. {status_icon} {action['title']} ({action['id']}){waiting_suffix}")

        lines.append("")  # Blank line between outcomes

    return "\n".join(lines)
```

**Example output:**
```
○ Edge cases and errors (arc-dyd)
  1. ✓ Fix silent thumbnail failures (arc-6zd)
  2. ○ Handle orphaned temp files (arc-mii)

○ Search, fetch, AND create (arc-6ku)
  1. ○ Replace v1 in claude.json (arc-br7) ⏳ arc-02b
  2. ○ Implement contacts search (arc-bmk)
  3. ○ Wire resources (arc-tld)
```

### `--ready` Filter

Shows only items that are open AND not waiting:

```python
def filter_ready(items: list[dict]) -> list[dict]:
    """Return items that can be worked on now."""
    return [
        i for i in items
        if i["status"] == "open" and not i.get("waiting_for")
    ]
```

### `--waiting` Filter

Shows only items that have `waiting_for` set:

```python
def filter_waiting(items: list[dict]) -> list[dict]:
    """Return items that are waiting."""
    return [i for i in items if i.get("waiting_for")]
```

### `--json` Output

Nested structure for machine consumption:

```python
def format_json(items: list[dict]) -> dict:
    """Format as nested JSON structure."""
    outcomes = []
    for outcome in sorted(
        [i for i in items if i["type"] == "outcome"],
        key=lambda x: x.get("order", 999)
    ):
        actions = sorted(
            [i for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", 999)
        )
        outcome_copy = dict(outcome)
        outcome_copy["actions"] = actions
        outcomes.append(outcome_copy)

    reports = [i for i in items if i["type"] == "report" and i["status"] == "open"]

    return {"outcomes": outcomes, "reports": reports}
```

---

## Storage Operations

### Load and Save

```python
import json
from pathlib import Path

def load_items() -> list[dict]:
    """Load all items from JSONL."""
    path = Path(".arc/items.jsonl")
    if not path.exists():
        return []

    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def save_items(items: list[dict]):
    """Save items atomically."""
    path = Path(".arc/items.jsonl")
    tmp = path.with_suffix(".tmp")

    with open(tmp, "w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    tmp.rename(path)  # Atomic on POSIX

def load_prefix() -> str:
    """Load prefix, default to 'arc'."""
    path = Path(".arc/prefix")
    if path.exists():
        return path.read_text()
    return "arc"

def get_creator() -> str:
    """Get creator identifier for new items.

    Priority:
    1. ARC_USER env var (explicit override)
    2. git config user.name (most common)
    3. USER env var (fallback)
    4. "unknown" (last resort)
    """
    import os
    import subprocess

    # Explicit override
    if arc_user := os.environ.get("ARC_USER"):
        return arc_user

    # Git user name
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # System user
    if user := os.environ.get("USER"):
        return user

    return "unknown"

def now_iso() -> str:
    """Current time in ISO8601 format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

---

## Getting Started (For Implementers)

### Step 1: Create Project

```bash
mkdir -p arc/src/arc arc/tests/unit arc/tests/integration
cd arc
```

### Step 2: Create pyproject.toml

```toml
[project]
name = "arc"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
arc = "arc.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Step 3: Create src/arc/__init__.py

```python
"""Arc - Work tracker for Claude-human collaboration."""
__version__ = "0.1.0"
```

### Step 4: Implement in Order

1. **`models.py`** — Dataclasses (optional, can just use dicts)
2. **`ids.py`** — `generate_id()`, `generate_unique_id()`
3. **`storage.py`** — `load_items()`, `save_items()`, `load_prefix()`
4. **`queries.py`** — `filter_ready()`, `filter_waiting()`, `find_by_id()`
5. **`display.py`** — `format_hierarchical()`, `format_json()`
6. **`cli.py`** — Start with `init`, `new`, `list`, `done`, then add others

### Step 5: Install for Development

```bash
uv pip install -e .
arc init
arc new "Build arc itself"
```

---

## Test Fixtures

### Fixture 1: Empty

```jsonl
```

**`arc list` output:**
```
No outcomes.
```

### Fixture 2: Single Outcome, No Actions

```jsonl
{"id":"arc-gaBdur","type":"outcome","title":"User auth","status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
```

**`arc list` output:**
```
○ User auth (arc-gaBdur)
```

### Fixture 3: Outcome with Actions

```jsonl
{"id":"arc-gaBdur","type":"outcome","title":"User auth","status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-zoKte","type":"action","title":"Add endpoint","status":"done","parent":"arc-gaBdur","order":1,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer"}
{"id":"arc-miFola","type":"action","title":"Add UI","status":"open","parent":"arc-gaBdur","order":2,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":null}
```

**`arc list` output:**
```
○ User auth (arc-gaBdur)
  1. ✓ Add endpoint (arc-zoKte)
  2. ○ Add UI (arc-miFola)
```

### Fixture 4: Waiting Dependency

```jsonl
{"id":"arc-gaBdur","type":"outcome","title":"Deploy","status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-zoKte","type":"action","title":"Run tests","status":"open","parent":"arc-gaBdur","order":1,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer","waiting_for":"arc-miFola"}
{"id":"arc-miFola","type":"action","title":"Security review","status":"open","parent":"arc-gaBdur","order":2,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":null}
```

**`arc list` output:**
```
○ Deploy (arc-gaBdur)
  1. ○ Run tests (arc-zoKte) ⏳ arc-miFola
  2. ○ Security review (arc-miFola)
```

**`arc list --ready` output:**
```
○ Deploy (arc-gaBdur)
  2. ○ Security review (arc-miFola)
```

### Fixture 5: Multiple Outcomes

```jsonl
{"id":"arc-aaa","type":"outcome","title":"First outcome","status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-bbb","type":"outcome","title":"Second outcome","status":"open","order":2,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer"}
{"id":"arc-ccc","type":"action","title":"Action for first","status":"open","parent":"arc-aaa","order":1,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":null}
{"id":"arc-ddd","type":"action","title":"Action for second","status":"open","parent":"arc-bbb","order":1,"created_at":"2026-01-25T10:03:00Z","created_by":"sameer","waiting_for":null}
```

**`arc list` output:**
```
○ First outcome (arc-aaa)
  1. ○ Action for first (arc-ccc)

○ Second outcome (arc-bbb)
  1. ○ Action for second (arc-ddd)
```

### Fixture 6: Reports (Inbox)

```jsonl
{"id":"rpt-xyzzy","type":"report","title":"Something seems broken","status":"open","created_at":"2026-01-25T10:00:00Z","created_by":"claude-session-abc"}
{"id":"rpt-plugh","type":"report","title":"Feature idea","status":"open","created_at":"2026-01-25T10:01:00Z","created_by":"claude-session-def"}
```

**`arc inbox` output:**
```
○ Something seems broken (rpt-xyzzy)
○ Feature idea (rpt-plugh)
```

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `arc new` with no `.arc/` | Error: "Not initialized. Run `arc init` first." |
| `arc done` on already-done item | No-op, print "Already done: {id}" |
| `arc done` on non-existent ID | Error: "Item '{id}' not found" |
| `arc wait` on item that's waiting | Overwrites previous `waiting_for` |
| `arc wait X Y` where Y doesn't exist | Allowed — Y might be free text or future item |
| `arc new --for X` where X is an action | Error: "Parent must be an outcome" |
| `arc new --for X` where X doesn't exist | Error: "Parent '{X}' not found" |
| `arc edit` changes ID | Error: "Cannot change item ID" |
| Duplicate IDs in JSONL | Undefined — generator should prevent |
| Empty title | Error: "Title cannot be empty" |

---

## Key Workflows

### Solo Claude Session

```bash
arc list                           # See outcomes with actions
arc new "Implement user search"    # Create outcome
arc new "Add endpoint" --for arc-nePato
arc new "Add UI" --for arc-nePato

# Work
arc done arc-zoKte                 # Complete action
arc done arc-nePato                # Complete outcome

# Commit
git add .arc/ && git commit -m "arc: implement user search"
```

### Waiting Dependencies

```bash
arc new "Deploy to production"
arc new "Run tests" --for arc-nePato
arc new "Get security review" --for arc-nePato

arc wait arc-zoKte arc-miFola      # Tests wait for security review

arc list
# ○ Deploy to production (arc-nePato)
#   1. ○ Get security review (arc-miFola)
#   2. ○ Run tests (arc-zoKte) ⏳ arc-miFola

arc done arc-miFola                # Complete review → unblocks arc-zoKte
```

### Field Report Flow

```bash
# Claude notices issue
arc report "Search pagination broken"

# Later, triage
arc inbox
arc edit rpt-gaBdur   # Change type to action, add parent, add order

# Or create-and-dismiss
arc new "Fix pagination" --for arc-nePato
arc done rpt-gaBdur
```

---

## Multi-Agent Coordination

### Sync Mechanism

Git. No daemon, no locks.

### Conventions

1. **Pull before work** — See current state
2. **Small commits, often** — Easier merges
3. **One outcome at a time** — Reduces conflicts

### Session Tracking

Every item tracks `created_by`:
- Claude sessions: `claude-session-abc123`
- Humans: `sameer`

---

## Implementation Notes

### Language

Python with uv. Matches existing Claude tooling.

### Dependencies

- `argparse` (stdlib) — CLI parsing
- `pyyaml` — For `arc edit` (only external dependency)
- Standard library otherwise

### Performance Target

- `arc list` < 10ms for 500 items
- `arc new` < 10ms
- No startup latency (no daemon)

---

## Repository Architecture

```
arc/
├── src/arc/
│   ├── __init__.py
│   ├── cli.py          # argparse commands, main()
│   ├── storage.py      # load_items, save_items, load_prefix
│   ├── ids.py          # generate_id, generate_unique_id
│   ├── queries.py      # filter_ready, filter_waiting, find_by_id
│   └── display.py      # format_hierarchical, format_json
├── tests/
│   ├── unit/
│   │   ├── test_ids.py
│   │   ├── test_queries.py
│   │   └── test_display.py
│   └── integration/
│       ├── test_cli_init.py
│       ├── test_cli_new.py
│       ├── test_cli_done.py
│       └── test_cli_list.py
├── fixtures/
│   ├── empty.jsonl
│   ├── single_outcome.jsonl
│   ├── outcome_with_actions.jsonl
│   ├── waiting_dependency.jsonl
│   └── multiple_outcomes.jsonl
├── skill/
│   └── SKILL.md
├── pyproject.toml
└── README.md
```

---

## Execution Plan

### Phase 1: Core CLI

Build: `arc init`, `arc new`, `arc done`, `arc list`, `arc show`

Track with TodoWrite. Delivers working hierarchical output.

### Phase 2: Status & Reports

Build: `arc wait`, `arc unwait`, `arc report`, `arc inbox`, `arc edit`

Dogfood arc itself.

### Phase 3: Polish

Build: `arc status`, error messages, `--json` output.

### Phase 4: Skill

Write companion skill for Claude workflow guidance.

---

## Migration from Beads

```bash
bd export --format jsonl > /tmp/beads.jsonl
python transform.py < /tmp/beads.jsonl > .arc/items.jsonl
```

Transform: `issue_type: epic` → `type: outcome`, `closed` → `done`, etc.

---

## Future (v2)

Deferred:
- Todoist integration
- MCP server
- Graph visualization
- Cross-project aggregation
- Multi-agent ownership (`assign`/`mine`)

---

## Summary

| Beads | Arc |
|-------|-----|
| 86 commands | 12 commands |
| SQLite + JSONL dual | JSONL only |
| Daemon required | No daemon |
| Flat list output | Hierarchical by default |
| Priority levels | Ordering only |
| Tags/labels | None |
| Cloud storage broken | Cloud storage works |
| Agile vocabulary | GTD vocabulary |

---

## Appendix: Command Reference

```
arc — Work tracker for Claude-human collaboration

Usage: arc [command] [options]

Commands:
  new TITLE [--for PARENT]    Create outcome or action
  done ID                     Complete item (unblocks waiters)
  show ID                     View item details
  list [--ready|--waiting]    List items hierarchically
  wait ID REASON              Mark item as waiting
  unwait ID                   Clear waiting status
  edit ID                     Edit in $EDITOR (YAML format)
  report TITLE                Create field report
  inbox                       List pending reports
  status                      Show overview
  init [--prefix PREFIX]      Initialize .arc/
  help                        Show help

Flags:
  --json     Nested JSON output
  --jsonl    Flat JSONL output
  --quiet    Minimal output
```
