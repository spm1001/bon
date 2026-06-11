"""Storage operations for bon items."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from bon.ids import get_siblings

# Known updated_by verbs, used by cmd_doctor for validation
KNOWN_VERBS = frozenset({
    "edited", "waited", "unwaited", "worked", "stepped",
    "cleared", "archived", "converted", "reopened", "reclaimed",
})


class ValidationError(Exception):
    """Raised when item validation fails."""
    pass


class BonError(Exception):
    """Raised by error() for user-facing errors."""
    pass


def error(message: str) -> None:
    """Raise BonError with the given message."""
    raise BonError(message)


def warn(message: str) -> None:
    """Print warning message to stderr (does not exit)."""
    print(f"Warning: {message}", file=sys.stderr)


_cached_data_dir: Path | None = None
_cached_backend: str | None = None


def _find_bon_dir() -> Path | None:
    """Walk up from CWD to find an existing .bon directory.

    Mirrors git rev-parse semantics: check each directory from CWD upward,
    stopping at a .git boundary (a nested repo without its own board must
    not adopt an outer repo's). At CWD any .bon directory counts; above it
    only a real board does — one with a prefix file — so bare handoff
    stashes like ~/.bon are never adopted on the way up.
    """
    cur = Path.cwd().resolve()
    for directory in (cur, *cur.parents):
        bon = directory / ".bon"
        if bon.is_dir():
            if directory == cur or (bon / "prefix").is_file():
                return bon
            # A cloned repo can carry knowledge files while its local
            # markers were gitignored — adopt it so check_initialized can
            # name the real problem instead of "Not initialized".
            if (directory / ".git").exists() and _looks_like_cloned_board(bon):
                return bon
        if (directory / ".git").exists():
            return None
    return None


def _looks_like_cloned_board(bon: Path) -> bool:
    """True when a .bon has git-tracked knowledge files but no prefix marker."""
    if (bon / "prefix").is_file():
        return False
    return (bon / "handoffs").is_dir() or (bon / "understanding.md").is_file()


def _data_dir() -> Path:
    """Return the data directory as an absolute path.

    Walks up from CWD (stopping at a .git boundary) so subdirectory
    sessions find their repo's board; falls back to ./.bon when no board
    exists yet (pre-init). Caches on first call, so CWD changes
    mid-process can't cause reads/writes to target the wrong directory.
    """
    global _cached_data_dir
    if _cached_data_dir is not None:
        return _cached_data_dir

    _cached_data_dir = _find_bon_dir() or Path(".bon").resolve()
    return _cached_data_dir


def _reset_data_dir() -> None:
    """Reset cached data dir. For tests only."""
    global _cached_data_dir
    _cached_data_dir = None


def _get_backend() -> str:
    """Return the storage backend: 'jsonl' (default) or 'dolt'.

    Reads .bon/backend once per process and caches. Absent file = jsonl.
    """
    global _cached_backend
    if _cached_backend is not None:
        return _cached_backend
    backend_file = _data_dir() / "backend"
    if backend_file.exists():
        _cached_backend = backend_file.read_text().strip().lower()
    else:
        _cached_backend = "jsonl"
    return _cached_backend


def _reset_backend() -> None:
    """Reset cached backend. For tests only."""
    global _cached_backend
    _cached_backend = None


def items_path() -> Path:
    """Return the path to items.jsonl.

    Raises BonError in Dolt mode (no local file exists).
    """
    if _get_backend() == "dolt":
        raise BonError("items_path() not available in Dolt mode — items are in the database")
    return _data_dir() / "items.jsonl"


def _most_recent_timestamp(item: dict) -> str:
    """Return the most recent timestamp from an item for dedup comparison."""
    return (item.get("done_at") or item.get("archived_at")
            or item.get("updated_at") or item.get("created_at") or "")


def _normalise_waiting_for(items: list[dict]) -> list[dict]:
    """Normalise waiting_for from legacy string to list format.

    After this, waiting_for is always list[str] or None.
    """
    for item in items:
        wf = item.get("waiting_for")
        if isinstance(wf, str):
            item["waiting_for"] = [wf]
        elif wf is not None and not isinstance(wf, list):
            item["waiting_for"] = None
    return items


def load_items() -> list[dict]:
    """Load all items from JSONL (or Dolt) with validation.

    Deduplicates by ID, preferring the version with the most recent timestamp
    (done_at > archived_at > updated_at > created_at). This handles union merge artifacts where git keeps
    both old and new versions of an edited line.
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_load_items
        return _normalise_waiting_for(dolt_load_items())

    path = _data_dir() / "items.jsonl"
    if not path.exists():
        return []

    seen: dict[str, dict] = {}  # id -> item (best version wins)
    duplicates: set[str] = set()
    for line_num, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        # Detect git conflict markers
        if line.startswith(("<<<<<<", "======", ">>>>>>")):
            print(
                f"Warning: Git conflict marker on line {line_num} — "
                f"resolve merge conflicts in {path}",
                file=sys.stderr,
            )
            continue
        try:
            item = json.loads(line)
            validate_item(item)
            item_id = item["id"]
            if item_id in seen:
                duplicates.add(item_id)
                # Keep the version with the most recent timestamp
                if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                    seen[item_id] = item
            else:
                seen[item_id] = item
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"Warning: Skipping malformed item on line {line_num}: {e}", file=sys.stderr)

    if duplicates:
        ids = ", ".join(sorted(duplicates))
        print(
            f"Warning: Duplicate IDs found (merge artifact?): {ids}",
            file=sys.stderr,
        )

    return _normalise_waiting_for(list(seen.values()))


def validate_item(item: dict, strict: bool = False) -> None:
    """Validate item has required fields. Raises ValidationError if invalid.

    Args:
        item: The item to validate
        strict: If True, also validates brief subfields (used for bon edit).
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

    Deduplicates by ID before writing, keeping the version with the most
    recent timestamp. This prevents duplicate lines from any source
    (migrate, manual edits, agent mistakes).

    Deterministic order means two branches that touch different items
    produce minimal diffs, enabling clean git merges.
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_save_items
        return dolt_save_items(items)

    seen: dict[str, dict] = {}
    duplicates: set[str] = set()
    for item in items:
        item_id = item.get("id", "")
        if item_id in seen:
            duplicates.add(item_id)
            if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                seen[item_id] = item
        else:
            seen[item_id] = item

    if duplicates:
        ids = ", ".join(sorted(duplicates))
        print(f"Warning: Deduplicated IDs on save: {ids}", file=sys.stderr)

    path = _data_dir() / "items.jsonl"
    tmp = path.with_suffix(".tmp")

    with open(tmp, "w") as f:
        for item in sorted(seen.values(), key=lambda i: i.get("id", "")):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    tmp.rename(path)  # Atomic on POSIX


def load_prefix() -> str:
    """Load prefix from local .bon/prefix file, default to 'bon'.

    Even in Dolt mode, prefix is local — it scopes which items to load.
    """
    path = _data_dir() / "prefix"
    if path.exists():
        return path.read_text()
    return "bon"


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


_creator_cache: str | None = None


def get_creator() -> str:
    """Get creator identifier for new items.

    Returns "{name}" for AI agents (common case), "{name}-tty" for humans typing directly.
    Result is cached after first call (git runs at most once per process).

    Name priority:
    1. BON_USER env var (explicit override)
    2. ARC_USER env var (transition fallback)
    3. git config user.name (most common)
    4. USER env var (fallback)
    5. "unknown" (last resort)
    """
    global _creator_cache
    if _creator_cache is not None:
        return _creator_cache

    # Get the human identity
    name = None

    # Explicit override (BON_USER preferred, ARC_USER fallback)
    if bon_user := os.environ.get("BON_USER"):
        name = bon_user
    elif arc_user := os.environ.get("ARC_USER"):
        # Deprecated old-codename fallback — remove this branch in v0.30+
        warn("ARC_USER is deprecated, use BON_USER (will be removed in v0.30+)")
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
        _creator_cache = f"{name}-tty"
    else:
        _creator_cache = name

    return _creator_cache


def now_iso() -> str:
    """Current time in ISO8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def check_initialized() -> None:
    """Check if .bon/ is initialized here or in a parent (up to a .git boundary)."""
    data = _data_dir()
    if not data.is_dir():
        error(
            f"Not initialized: no .bon/ found from {data.parent} upward\n"
            "(the search stops at a .git boundary). Run `bon init` here, or cd\n"
            "into a directory whose repo has a board."
        )
    if _looks_like_cloned_board(data):
        error(
            f"{data} has bon knowledge files (handoffs/understanding) but no local\n"
            "state markers (.bon/prefix, .bon/backend) — this looks like a fresh clone\n"
            "of a repo that gitignores them. The board data is safe; it lives in the\n"
            "Dolt server (or the origin's items.jsonl), not here. Reconnect from\n"
            f"{data.parent} with:\n"
            "  bon init --prefix <prefix> --backend dolt\n"
            "(non-destructive — completes the missing markers, touches nothing else).\n"
            "Better still: commit .bon/prefix and .bon/backend in the origin repo;\n"
            "the machine-local part of Dolt config is ~/.config/bon/dolt.toml."
        )


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


def get_session_identity() -> str:
    """Return the session identity for tactical steps.

    Identity is the .bon root (the directory holding .bon), not the bare
    CWD: walk-up discovery means every subdirectory of a project shares
    the board, so they must also share the one-active-tactical claim —
    otherwise two subdirs of one repo could claim two tacticals on the
    same board. Pre-init (no .bon found) this degrades to CWD, matching
    the old behavior.
    In JSONL mode: realpath of the .bon root.
    In Dolt mode: hostname:realpath — prevents false conflicts when two
    machines have the same absolute path.
    """
    path = os.path.realpath(_data_dir().parent)
    if _get_backend() == "dolt":
        import socket
        return f"{socket.gethostname()}:{path}"
    return path


def _tactical_is_active(item: dict) -> bool:
    """Check if an item has active (incomplete) tactical steps."""
    if item.get("status") != "open":
        return False
    tactical = item.get("tactical")
    return bool(tactical and tactical.get("current", 0) < len(tactical.get("steps", [])))


def _matches_session(item_session: str | None, session: str | None) -> bool:
    """Check if an item's tactical session matches the requested session.

    - session=None: match only unscoped tacticals (no session field) — backward compat
    - session="/path": match tactical.session == path OR unscoped (legacy claimable)
    """
    if session is None:
        return item_session is None
    return item_session == session or item_session is None


def find_active_tactical(items: list[dict], session: str | None = None) -> dict | None:
    """Find the item with active tactical steps for a given session, or None."""
    for item in items:
        if not _tactical_is_active(item):
            continue
        item_session = item.get("tactical", {}).get("session")
        if _matches_session(item_session, session):
            return item
    return None


def find_any_active_tactical(items: list[dict]) -> list[dict]:
    """Find ALL items with active tactical steps, regardless of session.

    Used for cross-session conflict detection.
    """
    return [item for item in items if _tactical_is_active(item)]


def find_no_complete_tactical(items: list[dict], session: str | None = None) -> dict | None:
    """Find an open action where all tactical steps are done (--no-complete state)."""
    for item in items:
        if item.get("status") != "open" or not item.get("tactical"):
            continue
        tactical = item["tactical"]
        steps = tactical.get("steps", [])
        if not steps or tactical.get("current", 0) < len(steps):
            continue
        if _matches_session(tactical.get("session"), session):
            return item
    return None


def find_orphaned_tactical(items: list[dict], session: str) -> dict | None:
    """Find an item with active tactical steps whose session path no longer exists.

    Returns the first orphaned item found, or None. Only checks items
    whose session differs from the given session (current CWD).
    """
    for item in items:
        if not _tactical_is_active(item):
            continue
        item_session = item.get("tactical", {}).get("session")
        if item_session and item_session != session and not os.path.isdir(item_session):
            return item
    return None


def load_archive() -> list[dict]:
    """Load archived items from archive.jsonl (or Dolt archive table)."""
    if _get_backend() == "dolt":
        from bon.dolt import dolt_load_archive
        return dolt_load_archive()

    path = _data_dir() / "archive.jsonl"
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
    """Append items to archive.jsonl (or Dolt archive table) atomically.

    Deduplicates by ID (keeping most recent via _most_recent_timestamp),
    same as save_items. Writes atomically with tmp+rename.
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_append_archive
        return dolt_append_archive(items)

    existing = load_archive()

    seen: dict[str, dict] = {}
    for item in existing + items:
        item_id = item.get("id", "")
        if item_id in seen:
            if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                seen[item_id] = item
        else:
            seen[item_id] = item

    path = _data_dir() / "archive.jsonl"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        for item in sorted(seen.values(), key=lambda i: i.get("id", "")):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    tmp.rename(path)  # Atomic on POSIX


def remove_from_archive(item_id: str, prefix: str | None = None) -> dict | None:
    """Remove an item from archive (JSONL or Dolt). Returns the item, or None if not found.

    Rewrites archive atomically (same pattern as save_items).
    """
    if _get_backend() == "dolt":
        from bon.dolt import dolt_remove_from_archive
        return dolt_remove_from_archive(item_id, prefix)

    archived = load_archive()
    item = find_by_id(archived, item_id, prefix)
    if not item:
        return None

    remaining = [i for i in archived if i["id"] != item["id"]]
    path = _data_dir() / "archive.jsonl"
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
    # skipped is optional; when present must be dict with string keys and string values
    skipped = tactical.get("skipped")
    if skipped is not None:
        if not isinstance(skipped, dict):
            raise ValidationError("tactical.skipped must be a dict")
        for key, value in skipped.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValidationError("tactical.skipped keys and values must be strings")
