# InnerPlan: The Arc Specification

**Version:** 2.3
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
7. **Tiny, fast, reliable** — 10 commands, not 86

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
| **Action** | A concrete next step. May belong to an outcome, or standalone. "Add OAuth callback endpoint" |
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
├── items.jsonl    # All items (outcomes, actions)
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
  "brief": {
    "why": "Team struggling with auth complexity, new devs take 2 days to set up",
    "what": "Simplified OAuth flow that works for 90% of cases",
    "done": "New dev can set up auth in < 10 minutes following the guide"
  },
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
| `brief` | ✓ | object | Structured context (see below) |
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
  "brief": {
    "why": "Need callback URL for OAuth flow to complete",
    "what": "POST /auth/callback endpoint that exchanges code for token",
    "done": "Endpoint returns 200 with valid token, handles errors gracefully"
  },
  "status": "open",
  "parent": "arc-gaBdur",
  "order": 1,
  "created_at": "2026-01-25T10:31:00Z",
  "created_by": "sameer",
  "waiting_for": null
}
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | ✓ | string | `{prefix}-{hash}` |
| `type` | ✓ | `"action"` | |
| `title` | ✓ | string | |
| `brief` | ✓ | object | Structured context (see below) |
| `status` | ✓ | `"open"` or `"done"` | |
| `parent` | | string or null | Parent outcome ID. Null = standalone. |
| `order` | ✓ | integer | Position within parent |
| `created_at` | ✓ | ISO8601 | |
| `created_by` | ✓ | string | |
| `waiting_for` | | string or null | ID or free text |

### The `brief` Field

The `brief` field enables Claude-to-Claude handoff. It has three required subfields:

| Subfield | Required | Question it answers |
|----------|----------|---------------------|
| `why` | ✓ | Why are we doing this? |
| `what` | ✓ | What will we produce/achieve? |
| `done` | ✓ | How do we know it's complete? |

**For Outcomes:**
- `why` — Purpose, what led here, why this matters
- `what` — Key results, vision, what success looks like
- `done` — Success criteria, how you know the outcome is achieved

**For Actions:**
- `why` — Context the receiving Claude needs, background
- `what` — Deliverables, artifacts, specific things to produce
- `done` — Definition of done, acceptance criteria

**The test:** Could a Claude with no context execute this action from the brief alone?

**Good action brief:**
```json
{
  "why": "OAuth flow causing race conditions when batch jobs run concurrently. See error logs from Jan 10.",
  "what": "1. processes list command to show running executions. 2. --guard flag to abort if already running. 3. --force flag to skip check.",
  "done": "Can run `itv-appscript processes list` and see running jobs. Running with --guard aborts if duplicate detected."
}
```

**Bad action brief (too thin):**
```json
{
  "why": "Need this feature",
  "what": "Add the thing",
  "done": "It works"
}
```

### Brief Quality Expectations

**For AI-created items**, briefs should be detailed enough for execution without conversation history. Include:

- **Concrete details:** File paths, function names, API endpoints, error messages
- **Numbered steps** in `what` when multiple deliverables exist
- **Verifiable criteria** in `done` — not "it works" but "returns 200 with valid token"
- **References** to related items, commits, or documentation when relevant

**The test:** Could a Claude with zero context *and no access to the conversation that spawned this* execute the action from the brief alone?

**Rich brief (expected from AI):**
```json
{
  "why": "OAuth token refresh fails silently when refresh_token is expired. Users see 401 errors with no recovery path. Affects ~5% of daily active users based on error logs.",
  "what": "1. Detect expired refresh_token (not just access_token). 2. Clear stored credentials and redirect to /auth/login. 3. Add 'session_expired' query param so UI can show explanation.",
  "done": "Expired refresh_token triggers redirect within 1 request. Login page shows 'Your session expired, please sign in again.' No user sees raw 401."
}
```

**Thin brief (acceptable for quick standalone actions, not for outcome work):**
```json
{
  "why": "Typo in error message reported by user",
  "what": "Fix 'authenication' → 'authentication' in auth.py:47",
  "done": "String corrected, no typo visible"
}
```

**Unacceptable brief (will strand future Claude):**
```json
{
  "why": "Need this for the feature",
  "what": "Add the handler",
  "done": "It works"
}
```

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

### Order Assignment

Orders are dense rank positions (1, 2, 3, ...) within each sibling group. Three separate ordering pools exist:

1. **Outcomes** — ordered among outcomes
2. **Actions under a parent** — ordered among siblings
3. **Standalone actions** — ordered among standalone actions

```python
def next_order(items: list[dict], item_type: str, parent: str | None = None) -> int:
    """Get next order value (append position) for new item."""
    siblings = get_siblings(items, item_type, parent)
    if not siblings:
        return 1
    return max(i.get("order", 0) for i in siblings) + 1


def get_siblings(items: list[dict], item_type: str, parent: str | None = None) -> list[dict]:
    """Get sibling items for ordering context."""
    if parent:
        # Action under an outcome: siblings are other actions under same parent
        return [i for i in items if i.get("parent") == parent]
    elif item_type == "outcome":
        # Outcome: siblings are other outcomes
        return [i for i in items if i["type"] == "outcome"]
    else:
        # Standalone action: siblings are other standalone actions
        return [i for i in items if i["type"] == "action" and not i.get("parent")]
```

### Reordering on Edit

When an item's order is changed via `arc edit`, siblings shift to maintain density:

```python
def apply_reorder(items: list[dict], edited: dict, old_order: int, new_order: int):
    """Shift siblings to accommodate order change.

    Moving from 5 to 2: items at 2, 3, 4 shift to 3, 4, 5.
    Moving from 2 to 5: items at 3, 4, 5 shift to 2, 3, 4.
    """
    if old_order == new_order:
        return

    siblings = [i for i in get_siblings(items, edited["type"], edited.get("parent"))
                if i["id"] != edited["id"]]

    if new_order < old_order:
        # Moving up: shift items in [new, old) down by 1
        for s in siblings:
            if new_order <= s.get("order", 0) < old_order:
                s["order"] += 1
    else:
        # Moving down: shift items in (old, new] up by 1
        for s in siblings:
            if old_order < s.get("order", 0) <= new_order:
                s["order"] -= 1
```

### Order on Completion

Completed items retain their order. This preserves position for display (showing ✓ in place) and maintains sibling order stability.

---

## CLI Reference

### Commands (10)

```
arc new "title" [--for PARENT] [--why W --what X --done D]
                                  Create outcome (or action if --for)
arc done ID                       Complete item
arc show ID                       View item with actions
arc list [--ready|--waiting|--all] List items (hierarchical)
arc wait ID REASON                Mark as waiting
arc unwait ID                     Clear waiting
arc edit ID                       Edit in $EDITOR
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
arc new "title" [--for PARENT] [--why WHY] [--what WHAT] [--done DONE]
```

Creates outcome (default) or action (if `--for`).

**Brief is required.** Either:
- Interactive: prompted for why/what/done (must provide non-empty answers)
- Non-interactive: must provide `--why`, `--what`, `--done` flags

```python
def new(title: str, parent: str | None = None,
        why: str | None = None, what: str | None = None, done: str | None = None):
    # Normalize title: single line, trimmed
    title = " ".join(title.split())
    if not title:
        error("Title cannot be empty")

    items = load_items()
    prefix = load_prefix()
    existing_ids = {i["id"] for i in items}

    # Get brief: interactive prompts or flags (both enforce non-empty)
    if sys.stdin.isatty() and not (why and what and done):
        brief = prompt_brief()
    else:
        brief = require_brief_flags(why, what, done)

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
            "brief": brief,
            "status": "open",
            "parent": parent,
            "order": next_order(items, "action", parent),
            "created_at": now_iso(),
            "created_by": get_creator(),
            "waiting_for": None,
        }
    else:
        item = {
            "id": generate_unique_id(prefix, existing_ids),
            "type": "outcome",
            "title": title,
            "brief": brief,
            "status": "open",
            "order": next_order(items, "outcome", None),
            "created_at": now_iso(),
            "created_by": get_creator(),
        }

    items.append(item)
    save_items(items)
    print(f"Created: {item['id']}")


def prompt_brief() -> dict:
    """Prompt user for brief fields interactively.

    Guides human through the same structure Claude should use.
    All fields required — empty answers rejected.
    """
    print("Brief (all fields required):")
    print()

    why = input("  Why are we doing this? ").strip()
    if not why:
        error("'Why' cannot be empty")

    what = input("  What will we produce? ").strip()
    if not what:
        error("'What' cannot be empty")

    done = input("  How do we know it's done? ").strip()
    if not done:
        error("'Done' cannot be empty")

    return {"why": why, "what": what, "done": done}


def require_brief_flags(why: str | None, what: str | None, done: str | None) -> dict:
    """Validate brief flags for non-interactive creation.

    All three flags required when not in interactive mode.
    """
    missing = []
    if not why:
        missing.append("--why")
    if not what:
        missing.append("--what")
    if not done:
        missing.append("--done")

    if missing:
        error(f"Brief required. Missing: {', '.join(missing)}")

    return {"why": why, "what": what, "done": done}
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

    if item["status"] == "done":
        print(f"Already done: {item_id}")
        return

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

**`waiting_for` semantics:**

The field can contain either:
- An item ID (e.g., `"arc-miFola"`) — auto-clears when that item completes
- Free text (e.g., `"security review approval"`) — must be manually cleared with `arc unwait`

**How `arc done` distinguishes:** Exact string match against completed item's ID. If `waiting_for` matches, it clears. If not (free text), it remains.

**Display:** Both render the same way (`⏳ {value}`). The receiving Claude sees what's written.

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

Opens item in `$EDITOR` as JSON. Saves changes back with validation.

```python
import subprocess
import tempfile
import json

def edit(item_id: str):
    items = load_items()
    item = find_by_id(items, item_id)
    if not item:
        error(f"Item '{item_id}' not found")

    old_order = item.get("order")  # Capture before edit

    # Write to temp file as formatted JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(item, f, indent=2, ensure_ascii=False)
        f.write('\n')
        temp_path = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, temp_path], check=True)

    # Read back
    with open(temp_path) as f:
        edited = json.load(f)
    os.unlink(temp_path)

    # Validate
    validate_edit(item, edited, items)

    # Handle reorder if order changed
    new_order = edited.get("order")
    if old_order != new_order:
        apply_reorder(items, edited, old_order, new_order)

    # Update in list
    for i, existing in enumerate(items):
        if existing["id"] == item_id:
            items[i] = edited
            break

    save_items(items)
    print(f"Updated: {item_id}")


def validate_edit(original: dict, edited: dict, all_items: list[dict]):
    """Validate edited item. Raises error on invalid changes."""
    # ID cannot change
    if edited.get("id") != original["id"]:
        error("Cannot change item ID")

    # Type cannot change
    if edited.get("type") != original["type"]:
        error("Cannot change item type")

    # Full validation including brief subfields
    try:
        validate_item(edited, strict=True)
    except ValidationError as e:
        error(str(e))

    # Additional required fields for edit (beyond base validation)
    for field in ["order", "created_at", "created_by"]:
        if field not in edited:
            error(f"Missing required field: {field}")

    # Parent must exist if specified
    if edited.get("parent"):
        parent = find_by_id(all_items, edited["parent"])
        if not parent:
            error(f"Parent '{edited['parent']}' not found")
        if parent["type"] != "outcome":
            error(f"Parent must be an outcome, got {parent['type']}")
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

    # Brief
    brief = item.get("brief", {})
    if brief:
        print(f"\n   Why: {brief.get('why', 'N/A')}")
        print(f"   What: {brief.get('what', 'N/A')}")
        print(f"   Done: {brief.get('done', 'N/A')}")

    # For outcomes, show actions
    if item["type"] == "outcome":
        actions = sorted(
            [i for i in items if i.get("parent") == item_id],
            key=lambda x: x.get("order", 999)
        )
        if actions:
            print("\n   Actions:")
            for idx, action in enumerate(actions, 1):
                a_icon = "✓" if action["status"] == "done" else "○"
                waiting = f" ⏳ {action['waiting_for']}" if action.get("waiting_for") else ""
                print(f"   {idx}. {a_icon} {action['title']} ({action['id']}){waiting}")
```

**Example output for outcome:**
```
○ User authentication (arc-gaBdur)
   Type: outcome
   Status: open
   Created: 2026-01-25T10:30:00Z by sameer

   Why: Team struggling with auth complexity, new devs take 2 days to set up
   What: Simplified OAuth flow that works for 90% of cases
   Done: New dev can set up auth in < 10 minutes following the guide

   Actions:
   1. ✓ Add OAuth endpoint (arc-zoKte)
   2. ○ Add token refresh (arc-miFola) ⏳ arc-zoKte
   3. ○ Add logout (arc-haVone)
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

    open_outcomes = [i for i in outcomes if i["status"] == "open"]
    done_outcomes = [i for i in outcomes if i["status"] == "done"]

    open_actions = [i for i in actions if i["status"] == "open"]
    done_actions = [i for i in actions if i["status"] == "done"]
    waiting_actions = [i for i in open_actions if i.get("waiting_for")]
    ready_actions = [i for i in open_actions if not i.get("waiting_for")]

    standalone = [i for i in actions if not i.get("parent")]

    print(f"Arc status (prefix: {prefix})")
    print()
    print(f"Outcomes:   {len(open_outcomes)} open, {len(done_outcomes)} done")
    print(f"Actions:    {len(open_actions)} open ({len(ready_actions)} ready, {len(waiting_actions)} waiting), {len(done_actions)} done")
    if standalone:
        print(f"Standalone: {len([s for s in standalone if s['status'] == 'open'])} open")
```

### `arc help`

```bash
arc help [COMMAND]
```

Without argument, shows command list (same as `arc --help`).
With argument, shows help for specific command.

**Implementation:** Use argparse's built-in help generation.

---

## Output Format

### Hierarchical Output Algorithm

```python
def format_hierarchical(items: list[dict], filter_mode: str = "default") -> str:
    """Format items as hierarchical text output.

    Args:
        items: All items to consider
        filter_mode: One of:
            - "default": Open outcomes, all their actions (shows progress)
            - "ready": Open outcomes, only ready actions (or waiting count)
            - "waiting": Open outcomes, only waiting actions
            - "all": All outcomes including done, all their actions
    """
    lines = []
    include_done_outcomes = filter_mode == "all"

    # Get outcomes sorted by order
    outcomes = sorted(
        [i for i in items if i["type"] == "outcome" and (include_done_outcomes or i["status"] == "open")],
        key=lambda x: x.get("order", 999)
    )

    for outcome in outcomes:
        # Outcome line
        status_icon = "✓" if outcome["status"] == "done" else "○"
        lines.append(f"{status_icon} {outcome['title']} ({outcome['id']})")

        # Get actions for this outcome
        all_actions = sorted(
            [i for i in items if i.get("parent") == outcome["id"]],
            key=lambda x: x.get("order", 999)
        )

        # Filter actions based on mode
        if filter_mode == "ready":
            visible_actions = [a for a in all_actions if a["status"] == "open" and not a.get("waiting_for")]
            waiting_count = len([a for a in all_actions if a["status"] == "open" and a.get("waiting_for")])
        elif filter_mode == "waiting":
            visible_actions = [a for a in all_actions if a.get("waiting_for")]
            waiting_count = 0
        else:
            # default and all: show all actions
            visible_actions = all_actions
            waiting_count = 0

        # Render visible actions
        for idx, action in enumerate(visible_actions, 1):
            if action["status"] == "done":
                status_icon = "✓"
                waiting_suffix = ""
            elif action.get("waiting_for"):
                status_icon = "○"
                waiting_suffix = f" ⏳ {action['waiting_for']}"
            else:
                status_icon = "○"
                waiting_suffix = ""

            lines.append(f"  {idx}. {status_icon} {action['title']} ({action['id']}){waiting_suffix}")

        # Show waiting count when filtering to ready and some are hidden
        if filter_mode == "ready" and waiting_count > 0 and not visible_actions:
            lines.append(f"  ({waiting_count} waiting)")
        elif filter_mode == "ready" and waiting_count > 0 and visible_actions:
            lines.append(f"  (+{waiting_count} waiting)")

        lines.append("")  # Blank line between outcomes

    # Standalone actions (no parent)
    if filter_mode == "ready":
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")
                      and i["status"] == "open" and not i.get("waiting_for")]
    elif filter_mode == "waiting":
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")
                      and i.get("waiting_for")]
    elif filter_mode == "all":
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")]
    else:
        standalone = [i for i in items if i["type"] == "action" and not i.get("parent")
                      and i["status"] == "open"]

    if standalone:
        lines.append("Standalone:")
        for action in sorted(standalone, key=lambda x: x.get("order", 999)):
            status_icon = "✓" if action["status"] == "done" else "○"
            waiting_suffix = f" ⏳ {action['waiting_for']}" if action.get("waiting_for") else ""
            lines.append(f"  {status_icon} {action['title']} ({action['id']}){waiting_suffix}")
        lines.append("")

    return "\n".join(lines).rstrip()
```

### Done Items in Output

**`arc list` filters by outcome status, not action status:**
- **Done outcomes** are hidden (unless `--all`)
- **Done actions** under open outcomes are shown (to display progress)

This means an open outcome with some completed actions shows the full picture:
```
○ User auth (arc-aaa)
  1. ✓ Add endpoint (arc-bbb)    ← done action, visible
  2. ○ Add UI (arc-ccc)          ← open action, visible
```

**To see done outcomes:** Use `arc list --all`.

**Edge case:** If all actions under an outcome are done but the outcome itself is still open, the outcome appears with all actions checked:

```
○ User auth (arc-gaBdur)
  1. ✓ Add endpoint (arc-zoKte)
  2. ✓ Add UI (arc-miFola)
```

This is user discipline — the tool doesn't auto-complete outcomes when actions finish.

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

    standalone = [i for i in items if i["type"] == "action" and not i.get("parent")]

    return {"outcomes": outcomes, "standalone": standalone}
```

### `--jsonl` Output

Raw JSONL dump of filtered items (respects `--ready`, `--waiting`, `--all` filters):

```python
def format_jsonl(items: list[dict]) -> str:
    """Format as flat JSONL, one item per line."""
    lines = []
    for item in items:
        lines.append(json.dumps(item, ensure_ascii=False))
    return "\n".join(lines)
```

Use case: Piping to `jq`, debugging, or feeding to another tool.

### Display Logic Summary

| Scenario | `arc list` | `arc list --ready` |
|----------|------------|-------------------|
| Outcome with mixed actions | All actions shown | Ready actions + "(+N waiting)" |
| Outcome with all ready | All actions shown | All actions shown |
| Outcome with all waiting | All actions shown | "(N waiting)" only |
| Outcome with no actions | Just outcome line | Just outcome line |

---

## Storage Operations

### Load and Save

```python
import json
import sys
from pathlib import Path

def load_items() -> list[dict]:
    """Load all items from JSONL with validation."""
    path = Path(".arc/items.jsonl")
    if not path.exists():
        return []

    items = []
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            validate_item(item)
            items.append(item)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Warning: Skipping malformed item on line {line_num}: {e}", file=sys.stderr)

    return items


class ValidationError(Exception):
    pass


def error(message: str):
    """Print error message and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def validate_item(item: dict, strict: bool = False):
    """Validate item has required fields. Raises ValidationError if invalid.

    Args:
        item: The item to validate
        strict: If True, also validates brief subfields (used for arc edit).
                If False, lenient validation for loading potentially old data.
    """
    required = ["id", "type", "title", "status"]
    for field in required:
        if field not in item:
            raise ValidationError(f"Missing required field: {field}")

    if item["type"] not in ("outcome", "action"):
        raise ValidationError(f"Invalid type: {item['type']}")

    if item["status"] not in ("open", "done"):
        raise ValidationError(f"Invalid status: {item['status']}")

    if strict:
        # Brief must exist and have all subfields
        if "brief" not in item:
            raise ValidationError("Missing required field: brief")
        brief = item.get("brief", {})
        for subfield in ["why", "what", "done"]:
            if subfield not in brief:
                raise ValidationError(f"Missing brief.{subfield}")


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


def find_by_id(items: list[dict], item_id: str, prefix: str | None = None) -> dict | None:
    """Find item by ID. Returns None if not found.

    Searches all items regardless of status (open or done).
    Case-sensitive. Tries exact match first, then prefix + id.

    Args:
        items: All items to search
        item_id: The ID to find (full or suffix)
        prefix: Current prefix for prefix-tolerant matching
    """
    # Exact match first
    for item in items:
        if item["id"] == item_id:
            return item

    # Prefix-tolerant: try prepending prefix
    if prefix and not item_id.startswith(prefix + "-"):
        prefixed = f"{prefix}-{item_id}"
        for item in items:
            if item["id"] == prefixed:
                return item

    return None


def get_creator() -> str:
    """Get creator identifier for new items.

    Returns "{name}" for AI agents (common case), "{name}-tty" for humans typing directly.

    Name priority:
    1. ARC_USER env var (explicit override)
    2. git config user.name (most common)
    3. USER env var (fallback)
    4. "unknown" (last resort)
    """
    import os
    import subprocess
    import sys

    # Get the human identity
    name = None

    # Explicit override
    if arc_user := os.environ.get("ARC_USER"):
        name = arc_user

    # Git user name
    if not name:
        try:
            result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                name = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # System user
    if not name:
        name = os.environ.get("USER", "unknown")

    # Suffix -tty if human is typing directly (rare case)
    if sys.stdin.isatty():
        return f"{name}-tty"

    return name


def now_iso() -> str:
    """Current time in ISO8601 format."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

---

## Working with Arc (Claude Workflow)

This section describes how Claude should use arc items — the draw-down and draw-up patterns that make sessions productive.

### The Draw-Down Pattern

**When you pick up an action to work on:**

1. **Read the brief:** `arc show <id>` — understand `why`, `what`, and `done`
2. **Create TodoWrite items** from `brief.what` and `brief.done`
3. **Show user the breakdown:** "I'm reading this as: [list]. Sound right?"
4. **VERIFY:** TodoWrite is not empty before proceeding
5. **Work through items with checkpoints** — pause at each completion to confirm direction

**The test:** If work will take >10 minutes, it needs TodoWrite items.

**Why this matters:** Without draw-down, you work from the arc item directly, context accumulates, and by close you've drifted. TodoWrite creates checkpoints where course-correction happens.

**Example:**
```
arc show arc-zoKte
# Why: OAuth flow causing race conditions...
# What: 1. processes list command 2. --guard flag 3. --force flag
# Done: Can see running processes, duplicates prevented

→ TodoWrite:
1. Add script.processes scope to auth
2. Create processes.py with list_processes()
3. Add processes list command to CLI
4. Add --guard/--force flags to run command
5. Test: processes list shows running jobs
6. Test: --guard aborts on duplicate
```

Each TodoWrite item is a checkpoint. When you complete item 3 and start item 4, pause: "Still on track?"

### The Draw-Up Pattern

**When you're filing work for a future Claude:**

1. **Write the brief thoroughly** — `why`/`what`/`done` must stand alone
2. **Include concrete details** — file paths, API endpoints, error messages
3. **Define done clearly** — verifiable criteria, not vague "it works"

**The test:** Could a Claude with zero context execute this from the brief alone?

**Good draw-up:**
```bash
arc new "Add rate limiting to API" --for arc-gaBdur \
  --why "Users hitting 429s during peak, server struggling under load" \
  --what "1. Redis-based rate limiter 2. 100 req/min per user 3. Retry-After header" \
  --done "Load test shows 429s after 100 requests, header present, Redis storing counts"
```

**Bad draw-up (will fail):**
```bash
arc new "Fix the API thing" --for arc-gaBdur
# Error: Brief required. Missing: --why, --what, --done
```

### Session Boundaries

**At session start:**
1. `arc list --ready` — see what's available
2. Pick an action
3. **Draw-down** — read brief, create TodoWrite items

**At session close:**
1. Update arc items with progress
2. File new actions discovered during work
3. **Draw-up** — ensure briefs are complete for next Claude

**Between actions (mid-session):**
1. Complete current action: `arc done <id>`
2. Check what's unblocked: `arc list --ready`
3. If continuing, **draw-down the next action** before starting

### Anti-Patterns

| Pattern | Problem | Fix |
|---------|---------|-----|
| Working without TodoWrite | No checkpoints, drift accumulates | Always draw-down |
| Thin briefs | Next Claude can't execute | Write for zero-context reader |
| Skipping draw-down on "continue" | Scope ambiguity | Always read brief, create todos |
| Motor through without pauses | Miss direction changes | Checkpoint at each TodoWrite completion |

---

## Key Workflows

### Solo Claude Session

```bash
arc list                           # See outcomes with actions
arc show arc-gaBdur                # Read the brief
# → Create TodoWrite from brief.what/done
# → Work through todos
arc done arc-zoKte                 # Complete action
arc done arc-gaBdur                # Complete outcome (when all done)

# Commit
git add .arc/ && git commit -m "arc: implement user search"
```

### Waiting Dependencies

```bash
arc new "Deploy to production" \
  --why "Feature complete, ready to ship" \
  --what "Production deployment with rollback plan" \
  --done "Feature live and monitored for 24h"

arc new "Run tests" --for arc-nePato \
  --why "Ensure quality before deploy" \
  --what "Full test suite pass" \
  --done "All tests green, coverage maintained"

arc new "Get security review" --for arc-nePato \
  --why "Compliance requirement for production" \
  --what "Security team sign-off" \
  --done "Approval email received"

arc wait arc-zoKte arc-miFola      # Tests wait for security review

arc list
# ○ Deploy to production (arc-nePato)
#   1. ○ Get security review (arc-miFola)
#   2. ○ Run tests (arc-zoKte) ⏳ arc-miFola

arc done arc-miFola                # Complete review → unblocks arc-zoKte
```

### Standalone Actions (Field Reports)

Actions without a parent are standalone — observations, one-off tasks, or notes for future Claudes.

```bash
# Claude notices something during work
arc new "Field Report: OAuth flaky under high load" \
  --why "Noticed 3 failures in 10 test runs, only under concurrent load" \
  --what "Document the pattern, identify root cause" \
  --done "Either fixed or filed as action under appropriate outcome"

# Later, can attach to an outcome via arc edit
arc edit arc-nePato
# Add: "parent": "arc-gaBdur"
```

**Or promote observation to proper action:**
```bash
arc new "Fix OAuth race condition" --for arc-gaBdur \
  --why "OAuth fails under concurrent load (see field report arc-nePato)" \
  --what "Add mutex or queue to prevent concurrent token refresh" \
  --done "100 concurrent requests complete without auth failures"

arc done arc-nePato                                    # Dismiss the observation
```

---

## Multi-Agent Coordination

### Sync Mechanism

Git. No daemon, no locks.

### Concurrent Write Limitation

**Single-writer assumed.** Arc uses atomic file rename for writes, which is safe for one writer. With two Claudes writing simultaneously:

1. Both read `items.jsonl`
2. Both make changes in memory
3. Both write — last write wins, first writer's changes lost

**Mitigations:**
- Commit frequently (git detects conflicts)
- One outcome at a time per agent
- Google Drive sync adds latency — avoid simultaneous editing across devices

**This is a known limitation, not a bug.** The "no daemon, no locks" design prioritizes simplicity and cloud compatibility over concurrent write safety.

### Conventions

1. **Pull before work** — See current state
2. **Small commits, often** — Easier merges
3. **One outcome at a time** — Reduces conflicts

### Session Tracking

Every item tracks `created_by`:
- AI agents (Claude, Codex, etc.): `sameer` — the human in the loop
- Human typing directly: `sameer-tty` — rare, marked explicitly

The `-tty` suffix indicates a human used arc directly in a terminal. Absence of `-tty` means an AI agent created it (the common case).

---

## Test Fixtures

**Note:** Fixture IDs (`arc-aaa`, `arc-bbb`) are simplified for readability. Production IDs follow the pronounceable pattern (`arc-gaBdur`).

### Fixture 1: Empty

```jsonl
```

**`arc list` output:**
```
No outcomes.
```

### Fixture 2: Single Outcome, No Actions

```jsonl
{"id":"arc-aaa","type":"outcome","title":"User auth","brief":{"why":"New devs struggling with auth setup","what":"Simplified OAuth flow","done":"Setup takes < 10 minutes"},"status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
```

**`arc list` output:**
```
○ User auth (arc-aaa)
```

### Fixture 3: Outcome with Actions

```jsonl
{"id":"arc-aaa","type":"outcome","title":"User auth","brief":{"why":"New devs struggling with auth setup","what":"Simplified OAuth flow","done":"Setup takes < 10 minutes"},"status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-bbb","type":"action","title":"Add endpoint","brief":{"why":"Need callback URL for OAuth","what":"POST /auth/callback endpoint","done":"Endpoint returns 200 with token"},"status":"done","parent":"arc-aaa","order":1,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer"}
{"id":"arc-ccc","type":"action","title":"Add UI","brief":{"why":"Users need login button","what":"Login button in header, redirect flow","done":"Click login → GitHub → back with session"},"status":"open","parent":"arc-aaa","order":2,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":null}
```

**`arc list` output:**
```
○ User auth (arc-aaa)
  1. ✓ Add endpoint (arc-bbb)
  2. ○ Add UI (arc-ccc)
```

### Fixture 4: Waiting Dependency

```jsonl
{"id":"arc-aaa","type":"outcome","title":"Deploy","brief":{"why":"Ship the feature","what":"Production deployment","done":"Feature live and working"},"status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-bbb","type":"action","title":"Run tests","brief":{"why":"Ensure quality","what":"Full test suite","done":"All tests pass"},"status":"open","parent":"arc-aaa","order":1,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer","waiting_for":"arc-ccc"}
{"id":"arc-ccc","type":"action","title":"Security review","brief":{"why":"Compliance requirement","what":"Security team sign-off","done":"Approval email received"},"status":"open","parent":"arc-aaa","order":2,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":null}
```

**`arc list` output:**
```
○ Deploy (arc-aaa)
  1. ○ Run tests (arc-bbb) ⏳ arc-ccc
  2. ○ Security review (arc-ccc)
```

**`arc list --ready` output:**
```
○ Deploy (arc-aaa)
  1. ○ Security review (arc-ccc)
  (+1 waiting)
```

### Fixture 5: Multiple Outcomes

```jsonl
{"id":"arc-aaa","type":"outcome","title":"First outcome","brief":{"why":"Reason one","what":"Result one","done":"Criteria one"},"status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-bbb","type":"outcome","title":"Second outcome","brief":{"why":"Reason two","what":"Result two","done":"Criteria two"},"status":"open","order":2,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer"}
{"id":"arc-ccc","type":"action","title":"Action for first","brief":{"why":"Context","what":"Deliverable","done":"Done when"},"status":"open","parent":"arc-aaa","order":1,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":null}
{"id":"arc-ddd","type":"action","title":"Action for second","brief":{"why":"Context","what":"Deliverable","done":"Done when"},"status":"open","parent":"arc-bbb","order":1,"created_at":"2026-01-25T10:03:00Z","created_by":"sameer","waiting_for":null}
```

**`arc list` output:**
```
○ First outcome (arc-aaa)
  1. ○ Action for first (arc-ccc)

○ Second outcome (arc-bbb)
  1. ○ Action for second (arc-ddd)
```

### Fixture 6: Standalone Actions

```jsonl
{"id":"arc-aaa","type":"action","title":"Field Report: OAuth flaky","brief":{"why":"Noticed during testing","what":"OAuth fails under load","done":"Investigate and fix or dismiss"},"status":"open","parent":null,"order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-bbb","type":"action","title":"Quick fix for typo","brief":{"why":"User reported","what":"Fix typo in error message","done":"Typo fixed"},"status":"open","parent":null,"order":2,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer"}
```

**`arc list` output:**
```
Standalone:
  ○ Field Report: OAuth flaky (arc-aaa)
  ○ Quick fix for typo (arc-bbb)
```

### Fixture 7: All Actions Waiting

```jsonl
{"id":"arc-aaa","type":"outcome","title":"Ship release","brief":{"why":"Q1 deadline approaching","what":"Production deployment","done":"Live and monitored"},"status":"open","order":1,"created_at":"2026-01-25T10:00:00Z","created_by":"sameer"}
{"id":"arc-bbb","type":"action","title":"Legal review","brief":{"why":"Compliance requirement","what":"Legal sign-off","done":"Approval received"},"status":"open","parent":"arc-aaa","order":1,"created_at":"2026-01-25T10:01:00Z","created_by":"sameer","waiting_for":"external counsel"}
{"id":"arc-ccc","type":"action","title":"Security audit","brief":{"why":"SOC2 requirement","what":"Pen test complete","done":"No critical findings"},"status":"open","parent":"arc-aaa","order":2,"created_at":"2026-01-25T10:02:00Z","created_by":"sameer","waiting_for":"arc-bbb"}
```

**`arc list` output:**
```
○ Ship release (arc-aaa)
  1. ○ Legal review (arc-bbb) ⏳ external counsel
  2. ○ Security audit (arc-ccc) ⏳ arc-bbb
```

**`arc list --ready` output:**
```
○ Ship release (arc-aaa)
  (2 waiting)
```

**`arc list --waiting` output:**
```
○ Ship release (arc-aaa)
  1. ○ Legal review (arc-bbb) ⏳ external counsel
  2. ○ Security audit (arc-ccc) ⏳ arc-bbb
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
| `arc edit` changes type | Error: "Cannot change item type" |
| `arc edit` removes brief subfield | Error: "Missing brief.{subfield}" |
| Duplicate IDs in JSONL | Undefined — generator should prevent |
| Empty title | Error: "Title cannot be empty" |
| Multi-line title | Normalized to single line (spaces replace newlines) |
| `arc new` without brief (non-interactive) | Error: "Brief required. Missing: --why, --what, --done" |
| `arc new` with empty brief field (interactive) | Error: "'Why' cannot be empty" (etc.) |

### Canonical Error Messages

All error messages use the format `Error: {message}` and exit with code 1.

| Code | Message | Trigger |
|------|---------|---------|
| `not_initialized` | "Not initialized. Run `arc init` first." | Any command when `.arc/` missing |
| `not_found` | "Item '{id}' not found" | ID doesn't exist (after prefix-tolerant lookup) |
| `parent_not_found` | "Parent '{id}' not found" | `--for` references non-existent ID |
| `parent_not_outcome` | "Parent must be an outcome, got {type}" | `--for` references an action |
| `empty_title` | "Title cannot be empty" | Title is whitespace-only |
| `brief_required` | "Brief required. Missing: {flags}" | Non-interactive without all brief flags |
| `brief_field_empty` | "'{field}' cannot be empty" | Interactive prompt gets empty input |
| `id_immutable` | "Cannot change item ID" | Edit attempts to change ID |
| `type_immutable` | "Cannot change item type" | Edit attempts to change type |
| `missing_field` | "Missing required field: {field}" | Validation fails on load or edit |
| `missing_brief_field` | "Missing brief.{subfield}" | Brief missing why/what/done |
| `invalid_type` | "Invalid type: {type}" | Type not "outcome" or "action" |
| `invalid_status` | "Invalid status: {status}" | Status not "open" or "done" |

---

## Implementation Notes

### Language

Python with uv. Matches existing Claude tooling.

### Dependencies

None. Standard library only.

- `argparse` (stdlib) — CLI parsing
- `json` (stdlib) — Storage format
- `tempfile` (stdlib) — For `arc edit`

### Performance Target

Design targets (not tested invariants):
- `arc list` < 10ms for 500 items
- `arc new` < 10ms
- No startup latency (no daemon)

These guide implementation choices. If commands feel slow, profile and fix.

---

## Repository Architecture

```
arc/
├── src/arc/
│   ├── __init__.py
│   ├── cli.py          # argparse commands, main()
│   ├── storage.py      # load_items, save_items, load_prefix, find_by_id
│   ├── ids.py          # generate_id, generate_unique_id
│   ├── queries.py      # filter_ready, filter_waiting
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
│   ├── multiple_outcomes.jsonl
│   └── standalone_actions.jsonl
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

### Phase 2: Dependencies & Editing

Build: `arc wait`, `arc unwait`, `arc edit`

Dogfood arc itself.

### Phase 3: Polish

Build: `arc status`, `arc help`, error messages, `--json` output.

### Phase 4: Skill

Write companion skill for Claude workflow guidance.

---

## Migration from Beads

```bash
bd export --format jsonl > /tmp/beads.jsonl
python transform.py < /tmp/beads.jsonl > .arc/items.jsonl
```

Transform: `issue_type: epic` → `type: outcome`, `closed` → `done`, etc.

### Migration Script

```python
def migrate_item(item: dict) -> dict:
    """Migrate beads item to arc schema."""
    # Type mapping
    if item.get("issue_type") == "epic":
        item["type"] = "outcome"
    else:
        item["type"] = "action"

    # Status mapping
    if item.get("status") == "closed":
        item["status"] = "done"
    elif item.get("status") not in ("open", "done"):
        item["status"] = "open"

    # Brief from description/design/acceptance
    desc = item.pop("description", "") or ""
    design = item.pop("design", "") or ""
    acceptance = item.pop("acceptance_criteria", "") or ""

    item["brief"] = {
        "why": desc if desc else "Migrated from beads",
        "what": design if design else "See title",
        "done": acceptance if acceptance else "When complete"
    }

    # Clean up beads-specific fields
    for field in ["issue_type", "notes", "labels", "priority"]:
        item.pop(field, None)

    return item
```

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
| 86 commands | 10 commands |
| SQLite + JSONL dual | JSONL only |
| Daemon required | No daemon |
| Flat list output | Hierarchical by default |
| Priority levels | Ordering only |
| Tags/labels | None |
| Cloud storage broken | Cloud storage works |
| Agile vocabulary | GTD vocabulary |
| Optional description | Required structured brief |

---

## Appendix: Command Reference

```
arc — Work tracker for Claude-human collaboration

Usage: arc [command] [options]

Commands:
  new TITLE [--for PARENT] [--why W --what X --done D]
                              Create outcome or action
  done ID                     Complete item (unblocks waiters)
  show ID                     View item details with brief
  list [--ready|--waiting|--all] List items hierarchically
  wait ID REASON              Mark item as waiting
  unwait ID                   Clear waiting status
  edit ID                     Edit in $EDITOR (JSON format)
  status                      Show overview
  init [--prefix PREFIX]      Initialize .arc/
  help [COMMAND]              Show help

Flags:
  --json     Nested JSON output
  --jsonl    Flat JSONL output
  --quiet    Minimal output
```
