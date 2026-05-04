"""Dolt backend for bon — MySQL-compatible storage with git semantics.

All Dolt-specific code lives here. Lazily imported from storage.py only
when .bon/backend contains "dolt". JSONL users never import pymysql.
"""
import contextlib
import json
import os
import sys
from pathlib import Path

from bon.storage import (
    _data_dir,
    _most_recent_timestamp,
    error,
    get_creator,
    validate_item,
)

# ---------- pymysql lazy import ----------

_pymysql = None


def _ensure_pymysql():
    """Lazy-import pymysql with a clear error if missing."""
    global _pymysql
    if _pymysql is not None:
        return _pymysql
    try:
        import pymysql
        _pymysql = pymysql
        return pymysql
    except ImportError:
        error(
            "Dolt backend requires PyMySQL. Install with:\n"
            "  pip install bon[dolt]\n"
            "  # or: uv pip install pymysql"
        )


# ---------- configuration ----------

_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 3306,
    "database": "bon",
    "user": "root",
    "password": "",
}


def _load_dolt_config() -> dict:
    """Load Dolt connection config.

    Priority: env vars > config file > defaults.
    """
    config = dict(_DEFAULTS)

    # Secondary: config file (~/.config/bon/dolt.toml)
    config_path = Path.home() / ".config" / "bon" / "dolt.toml"
    if config_path.exists():
        try:
            import tomllib
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)
            for key in ("host", "port", "database", "user", "password"):
                if key in file_config:
                    config[key] = file_config[key]
        except Exception as e:
            print(f"Warning: Failed to read {config_path}: {e}", file=sys.stderr)

    # Primary: env vars override everything
    env_map = {
        "BON_DOLT_HOST": "host",
        "BON_DOLT_PORT": "port",
        "BON_DOLT_DATABASE": "database",
        "BON_DOLT_USER": "user",
        "BON_DOLT_PASSWORD": "password",
    }
    for env_key, config_key in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            if config_key == "port":
                try:
                    config[config_key] = int(val)
                except ValueError:
                    error(f"BON_DOLT_PORT must be an integer, got '{val}'")
            else:
                config[config_key] = val

    # Password lookup chain: env var already handled above
    if not config["password"] and not os.environ.get("BON_DOLT_PASSWORD"):
        # Try macOS Keychain
        config["password"] = _keychain_password(config["user"])

    return config


def _keychain_password(user: str) -> str:
    """Try macOS Keychain for bon-dolt password. Returns empty string on failure."""
    if sys.platform != "darwin":
        return ""
    try:
        import subprocess
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "bon-dolt", "-a", user, "-w"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


# ---------- connection ----------

_cached_connection = None


def _get_connection():
    """Get or create a cached pymysql connection."""
    global _cached_connection
    pymysql = _ensure_pymysql()

    if _cached_connection is not None:
        try:
            _cached_connection.ping(reconnect=True)
            return _cached_connection
        except Exception:
            _cached_connection = None

    config = _load_dolt_config()

    # Check that at least host is configured (not just defaults)
    has_env = any(os.environ.get(k) for k in (
        "BON_DOLT_HOST", "BON_DOLT_PORT", "BON_DOLT_DATABASE", "BON_DOLT_USER",
    ))
    has_config = (Path.home() / ".config" / "bon" / "dolt.toml").exists()
    if not has_env and not has_config:
        error(
            "Dolt backend requires connection config. Set env vars:\n"
            "  BON_DOLT_HOST=100.64.0.3\n"
            "  BON_DOLT_PORT=3306\n"
            "  BON_DOLT_DATABASE=bon\n"
            "  BON_DOLT_USER=sameer\n"
            "Or create ~/.config/bon/dolt.toml"
        )

    try:
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        _ensure_schema(conn)
        _cached_connection = conn
        return conn
    except pymysql.err.OperationalError as e:
        error(
            f"Cannot connect to {config['host']}:{config['port']}. "
            f"Is Dolt running? Is Tailscale connected?\n"
            f"  Detail: {e}"
        )


def _reset_connection():
    """Reset cached connection. For tests."""
    global _cached_connection
    if _cached_connection is not None:
        with contextlib.suppress(Exception):
            _cached_connection.close()
    _cached_connection = None


def verify_dolt_connection():
    """Open a connection and run a trivial query. Raises BonError on failure."""
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT 1")


def check_prefix_collision(prefix: str, local_item_ids: set[str], local_archive_ids: set[str]) -> None:
    """Refuse to migrate if Dolt has prefix-rows not present in our local data.

    dolt_save_items and dolt_append_archive both DELETE all rows under the
    current prefix before re-inserting. If two repos share a prefix, this
    silently destroys the other repo's data. The check predicate is "foreign
    IDs" (Dolt-but-not-local), not "any rows" — the latter would block the
    legitimate JSONL→Dolt→JSONL→Dolt rollback-and-re-migrate flow.
    """
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM items WHERE id LIKE %s", (f"{prefix}-%",))
        existing_item_ids = {row["id"] for row in cur.fetchall()}
        cur.execute("SELECT id FROM archive WHERE id LIKE %s", (f"{prefix}-%",))
        existing_archive_ids = {row["id"] for row in cur.fetchall()}

    foreign_items = existing_item_ids - local_item_ids
    foreign_archive = existing_archive_ids - local_archive_ids

    if not foreign_items and not foreign_archive:
        return

    lines = [
        f"Refusing to migrate: Dolt already has rows with prefix '{prefix}' "
        f"that are not in this repo's local data.",
    ]
    if foreign_items:
        sample = ", ".join(sorted(foreign_items)[:5])
        lines.append(f"  items: {len(foreign_items)} foreign of {len(existing_item_ids)} (e.g. {sample})")
    if foreign_archive:
        sample = ", ".join(sorted(foreign_archive)[:5])
        lines.append(f"  archive: {len(foreign_archive)} foreign of {len(existing_archive_ids)} (e.g. {sample})")
    lines.append("")
    lines.append(f"These rows may belong to another repo using prefix '{prefix}',")
    lines.append("OR they may be stale from a previous JSONL→Dolt→JSONL rollback")
    lines.append("(if you deleted items locally before re-migrating, the originals linger in Dolt).")
    lines.append("")
    lines.append("Migrating would DELETE them. Resolve before retrying:")
    lines.append("  - foreign repo: rename one repo's prefix")
    lines.append(f"  - stale rollback: dolt sql -q \"DELETE FROM items WHERE id LIKE '{prefix}-%';\"")
    error("\n".join(lines))


# ---------- schema ----------

_SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS items (
        id          VARCHAR(64) PRIMARY KEY,
        type        VARCHAR(10) NOT NULL,
        title       VARCHAR(500) NOT NULL,
        status      VARCHAR(10) NOT NULL,
        brief       JSON,
        parent      VARCHAR(64),
        `order`     INT DEFAULT 999,
        waiting_for VARCHAR(500),
        wait_note   TEXT,
        tactical    JSON,
        created_at  VARCHAR(30),
        created_by  VARCHAR(100),
        updated_at  VARCHAR(30),
        updated_by  VARCHAR(30),
        done_at     VARCHAR(30),
        done_note   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS archive (
        id          VARCHAR(64) PRIMARY KEY,
        type        VARCHAR(10) NOT NULL,
        title       VARCHAR(500) NOT NULL,
        status      VARCHAR(10) NOT NULL,
        brief       JSON,
        parent      VARCHAR(64),
        `order`     INT DEFAULT 999,
        waiting_for VARCHAR(500),
        wait_note   TEXT,
        tactical    JSON,
        created_at  VARCHAR(30),
        created_by  VARCHAR(100),
        updated_at  VARCHAR(30),
        updated_by  VARCHAR(30),
        done_at     VARCHAR(30),
        done_note   TEXT,
        archived_at VARCHAR(30)
    )""",
    """CREATE TABLE IF NOT EXISTS config (
        `key`   VARCHAR(64) PRIMARY KEY,
        `value` TEXT NOT NULL
    )""",
]


def _ensure_schema(conn):
    """Create tables if they don't exist, and migrate existing ones (idempotent)."""
    with conn.cursor() as cur:
        for sql in _SCHEMA_SQL:
            cur.execute(sql)
        # Schema migrations for existing databases
        for table in ("items", "archive"):
            cur.execute(f"SHOW COLUMNS FROM {table} LIKE 'wait_note'")
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {table} ADD COLUMN wait_note TEXT AFTER waiting_for")
    conn.commit()


# ---------- row <-> dict conversion ----------

# Columns shared between items and archive tables
_ITEM_COLUMNS = [
    "id", "type", "title", "status", "brief", "parent", "order",
    "waiting_for", "wait_note", "tactical", "created_at", "created_by",
    "updated_at", "updated_by", "done_at", "done_note",
]

_ARCHIVE_COLUMNS = _ITEM_COLUMNS + ["archived_at"]


def _item_to_row(item: dict, columns: list[str] | None = None) -> dict:
    """Convert a bon item dict to a SQL row dict.

    JSON columns (brief, tactical) are serialized to strings.
    Missing keys get None.
    """
    cols = columns or _ITEM_COLUMNS
    row = {}
    for col in cols:
        val = item.get(col)
        if col in ("brief", "tactical") and val is not None:
            val = json.dumps(val, ensure_ascii=False)
        elif col == "waiting_for" and isinstance(val, list):
            val = json.dumps(val, ensure_ascii=False)
        row[col] = val
    return row


def _row_to_item(row: dict) -> dict:
    """Convert a SQL row dict to a bon item dict.

    JSON columns are deserialized. None values for optional fields are preserved
    (matches JSONL behavior where missing keys become None on .get()).
    """
    item = {}
    for key, val in row.items():
        if key == "order":
            item[key] = val if val is not None else 999
        elif key in ("brief", "tactical"):
            if val is not None:
                if isinstance(val, str):
                    item[key] = json.loads(val)
                else:
                    # pymysql may auto-parse JSON columns
                    item[key] = val
            # Omit None brief/tactical to match JSONL behavior
            # (JSONL items may not have these keys at all)
        elif key == "waiting_for" and val is not None and isinstance(val, str):
            # Deserialise JSON list or wrap legacy single string
            if val.startswith("["):
                item[key] = json.loads(val)
            else:
                item[key] = [val]
        else:
            item[key] = val
    return item


# ---------- items operations ----------

def dolt_load_items() -> list[dict]:
    """Load all items for the current project prefix from Dolt.

    Deduplicates by ID (same contract as JSONL load_items).
    """
    conn = _get_connection()
    prefix = _dolt_load_prefix_local()

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM items WHERE id LIKE %s", (f"{prefix}-%",))
        rows = cur.fetchall()

    seen: dict[str, dict] = {}
    for row in rows:
        item = _row_to_item(row)
        try:
            validate_item(item)
        except Exception as e:
            print(f"Warning: Skipping invalid Dolt item {row.get('id')}: {e}", file=sys.stderr)
            continue
        item_id = item["id"]
        if item_id in seen:
            if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                seen[item_id] = item
        else:
            seen[item_id] = item

    return list(seen.values())


def dolt_save_items(items: list[dict]) -> None:
    """Save items to Dolt with truncate-and-reinsert within a transaction.

    Only touches rows matching the current prefix. Other projects' items
    are untouched. Produces a Dolt commit.
    """
    conn = _get_connection()
    prefix = _dolt_load_prefix_local()

    # Deduplicate (same contract as JSONL save_items)
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

    with conn.cursor() as cur:
        # Delete only this prefix's items
        cur.execute("DELETE FROM items WHERE id LIKE %s", (f"{prefix}-%",))

        for item in sorted(seen.values(), key=lambda i: i.get("id", "")):
            row = _item_to_row(item)
            cols = list(row.keys())
            placeholders = ", ".join(["%s"] * len(cols))
            # Quote 'order' since it's a reserved word
            col_names = ", ".join(f"`{c}`" for c in cols)
            cur.execute(
                f"INSERT INTO items ({col_names}) VALUES ({placeholders})",
                list(row.values()),
            )

        # Dolt commit
        cmd_str = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "save"
        author = f"{get_creator()} <bon@localhost>"
        cur.execute("CALL DOLT_ADD('-A')")
        cur.execute(
            "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
            (f"bon {cmd_str}", author),
        )

    conn.commit()


# ---------- archive operations ----------

def dolt_load_archive() -> list[dict]:
    """Load archived items for the current project prefix from Dolt."""
    conn = _get_connection()
    prefix = _dolt_load_prefix_local()

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM archive WHERE id LIKE %s", (f"{prefix}-%",))
        rows = cur.fetchall()

    return [_row_to_item(row) for row in rows]


def dolt_append_archive(items: list[dict]) -> None:
    """Append items to the archive table, deduplicating by ID."""
    conn = _get_connection()

    # Load existing archive for dedup
    existing = dolt_load_archive()
    seen: dict[str, dict] = {}
    for item in existing + items:
        item_id = item.get("id", "")
        if item_id in seen:
            if _most_recent_timestamp(item) >= _most_recent_timestamp(seen[item_id]):
                seen[item_id] = item
        else:
            seen[item_id] = item

    prefix = _dolt_load_prefix_local()
    with conn.cursor() as cur:
        # Replace all archive rows for this prefix
        cur.execute("DELETE FROM archive WHERE id LIKE %s", (f"{prefix}-%",))
        for item in sorted(seen.values(), key=lambda i: i.get("id", "")):
            row = _item_to_row(item, _ARCHIVE_COLUMNS)
            cols = list(row.keys())
            placeholders = ", ".join(["%s"] * len(cols))
            col_names = ", ".join(f"`{c}`" for c in cols)
            cur.execute(
                f"INSERT INTO archive ({col_names}) VALUES ({placeholders})",
                list(row.values()),
            )

        cmd_str = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "archive"
        author = f"{get_creator()} <bon@localhost>"
        cur.execute("CALL DOLT_ADD('-A')")
        cur.execute(
            "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
            (f"bon {cmd_str}", author),
        )

    conn.commit()


def dolt_remove_from_archive(item_id: str, prefix: str | None = None) -> dict | None:
    """Remove an item from the archive table. Returns the item or None."""
    from bon.storage import find_by_id

    archived = dolt_load_archive()
    item = find_by_id(archived, item_id, prefix)
    if not item:
        return None

    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM archive WHERE id = %s", (item["id"],))

        author = f"{get_creator()} <bon@localhost>"
        cur.execute("CALL DOLT_ADD('-A')")
        cur.execute(
            "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
            (f"bon reopen {item['id']}", author),
        )

    conn.commit()
    return item


# ---------- prefix ----------

def _dolt_load_prefix_local() -> str:
    """Load prefix from the local .bon/prefix file.

    Even in Dolt mode, prefix is local — it identifies which project's
    items to load from the shared database.
    """
    path = _data_dir() / "prefix"
    if path.exists():
        return path.read_text()
    return "bon"


# ---------- log ----------

def dolt_log(limit: int = 20) -> list[dict]:
    """Query Dolt commit history via the dolt_log system table."""
    conn = _get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT date, message, committer FROM dolt_log ORDER BY date DESC LIMIT %s",
            (limit,),
        )
        return cur.fetchall()
