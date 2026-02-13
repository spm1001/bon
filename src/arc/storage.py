"""Storage operations for arc items."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


class ValidationError(Exception):
    """Raised when item validation fails."""
    pass


def error(message: str) -> None:
    """Print error message and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def warn(message: str) -> None:
    """Print warning message to stderr (does not exit)."""
    print(f"Warning: {message}", file=sys.stderr)


def load_items() -> list[dict]:
    """Load all items from JSONL with validation.

    Deduplicates by ID (last occurrence wins). This handles union merge
    artifacts where git keeps both old and new versions of an edited line.
    """
    path = Path(".arc/items.jsonl")
    if not path.exists():
        return []

    seen: dict[str, dict] = {}  # id -> item (last wins)
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            validate_item(item)
            seen[item["id"]] = item
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Warning: Skipping malformed item on line {line_num}: {e}", file=sys.stderr)

    return list(seen.values())


def validate_item(item: dict, strict: bool = False) -> None:
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


def save_items(items: list[dict]) -> None:
    """Save items atomically, sorted by ID for deterministic output.

    Deterministic order means two branches that touch different items
    produce minimal diffs, enabling clean git merges.
    """
    path = Path(".arc/items.jsonl")
    tmp = path.with_suffix(".tmp")

    with open(tmp, "w") as f:
        for item in sorted(items, key=lambda i: i.get("id", "")):
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
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_initialized() -> None:
    """Check if .arc/ is initialized. Exit with error if not."""
    if not Path(".arc").is_dir():
        error("Not initialized. Run `arc init` first.")


from arc.ids import get_siblings


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


def apply_reparent(items: list[dict], edited: dict, old_parent: str | None, new_parent: str | None):
    """Handle parent change: close gap in old parent, append to new parent.

    When an action moves from one outcome to another:
    1. Close the gap left behind (shift old siblings up)
    2. Append at end of new parent's children
    """
    if old_parent == new_parent:
        return

    old_order = edited.get("order", 1)

    # Close gap in old parent's children
    old_siblings = [i for i in items
                    if i["type"] == "action"
                    and i.get("parent") == old_parent
                    and i["id"] != edited["id"]]
    for s in old_siblings:
        if s.get("order", 0) > old_order:
            s["order"] -= 1

    # Append to end of new parent's children
    new_siblings = [i for i in items
                    if i["type"] == "action"
                    and i.get("parent") == new_parent
                    and i["id"] != edited["id"]]
    if new_siblings:
        max_order = max(s.get("order", 0) for s in new_siblings)
        edited["order"] = max_order + 1
    else:
        edited["order"] = 1


def _tactical_is_active(item: dict) -> bool:
    """Check if an item has active (incomplete) tactical steps."""
    if item.get("status") != "open":
        return False
    tactical = item.get("tactical")
    return bool(tactical and tactical.get("current", 0) < len(tactical.get("steps", [])))


def find_active_tactical(items: list[dict], session: str | None = None) -> dict | None:
    """Find the item with active tactical steps for a given session, or None.

    Session scoping (CWD-based):
    - session=None: match only unscoped tacticals (no session field) — backward compat
    - session="/path": match tactical.session == path OR unscoped (legacy claimable)
    """
    for item in items:
        if not _tactical_is_active(item):
            continue
        item_session = item.get("tactical", {}).get("session")
        if session is None:
            # Caller wants unscoped only
            if item_session is None:
                return item
        else:
            # Caller wants their session OR unscoped (legacy)
            if item_session == session or item_session is None:
                return item
    return None


def find_any_active_tactical(items: list[dict]) -> list[dict]:
    """Find ALL items with active tactical steps, regardless of session.

    Used for cross-session conflict detection.
    """
    return [item for item in items if _tactical_is_active(item)]


def load_archive() -> list[dict]:
    """Load archived items from archive.jsonl."""
    path = Path(".arc/archive.jsonl")
    if not path.exists():
        return []

    items = []
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
            items.append(item)
        except json.JSONDecodeError as e:
            print(f"Warning: Skipping malformed archive item on line {line_num}: {e}", file=sys.stderr)

    return items


def append_archive(items: list[dict]) -> None:
    """Append items to archive.jsonl atomically."""
    path = Path(".arc/archive.jsonl")

    # Read existing content (if any)
    existing = ""
    if path.exists():
        existing = path.read_text()

    # Write existing + new atomically
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        if existing:
            f.write(existing)
            if not existing.endswith("\n"):
                f.write("\n")
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    tmp.rename(path)  # Atomic on POSIX


def remove_from_archive(item_id: str, prefix: str | None = None) -> dict | None:
    """Remove an item from archive.jsonl by ID. Returns the item, or None if not found.

    Rewrites archive atomically (same pattern as save_items).
    """
    archived = load_archive()
    item = find_by_id(archived, item_id, prefix)
    if not item:
        return None

    remaining = [i for i in archived if i["id"] != item["id"]]
    path = Path(".arc/archive.jsonl")
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        for i in remaining:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")
    tmp.rename(path)

    return item


def validate_tactical(tactical: dict) -> None:
    """Validate tactical structure. Raises ValidationError if invalid."""
    if not isinstance(tactical.get("steps"), list):
        raise ValidationError("tactical.steps must be a list")
    if not tactical["steps"]:
        raise ValidationError("tactical.steps cannot be empty")
    if not all(isinstance(s, str) for s in tactical["steps"]):
        raise ValidationError("tactical.steps must contain strings")
    current = tactical.get("current", 0)
    if not isinstance(current, int) or current < 0:
        raise ValidationError("tactical.current must be non-negative integer")
    # session is optional; when present must be a non-empty string
    session = tactical.get("session")
    if session is not None and (not isinstance(session, str) or not session):
        raise ValidationError("tactical.session must be a non-empty string")
