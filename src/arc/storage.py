"""Storage operations for arc items."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


class ValidationError(Exception):
    """Raised when item validation fails."""
    pass


def error(message: str) -> None:
    """Print error message and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


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
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_initialized() -> None:
    """Check if .arc/ is initialized. Exit with error if not."""
    if not Path(".arc").is_dir():
        error("Not initialized. Run `arc init` first.")
