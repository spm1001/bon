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
    _normalise_waiting_for,
    error,
    get_creator,
    load_prefix,
    now_iso,
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


@contextlib.contextmanager
def _write_transaction(conn, describe: str):
    """Commit on success, roll back explicitly on any failure.

    Dolt's working set is shared across every project on the server — a
    half-applied truncate-and-reinsert surviving a crashed command corrupts
    all sessions' view, not just this one (observed 2026-06-07: a mid-batch
    INSERT failure left 47 rows deleted but never reinserted). Relying on
    rollback-on-disconnect is not sufficient; roll back before the process
    dies so the working set is untouched.
    """
    try:
        yield
        conn.commit()
    except Exception as e:
        with contextlib.suppress(Exception):
            conn.rollback()
        error(
            f"Dolt write failed during {describe} — rolled back, "
            f"working set unchanged.\n  Detail: {e}"
        )


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
        waiting_for TEXT,
        wait_note   TEXT,
        released_note TEXT,
        someday     TEXT,
        area        VARCHAR(100),
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
        waiting_for TEXT,
        wait_note   TEXT,
        released_note TEXT,
        someday     TEXT,
        area        VARCHAR(100),
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
    """CREATE TABLE IF NOT EXISTS repos (
        prefix      VARCHAR(64) PRIMARY KEY,
        repo_name   VARCHAR(200) NOT NULL,
        origin_url  VARCHAR(500),
        job         VARCHAR(64),
        updated_at  VARCHAR(30)
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
            # someday arrived August 2026 (Someday/Maybe parking, bon-majoca)
            cur.execute(f"SHOW COLUMNS FROM {table} LIKE 'someday'")
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {table} ADD COLUMN someday TEXT AFTER wait_note")
            # area arrived August 2026 (Areas of Focus grouping, bon-razonu)
            cur.execute(f"SHOW COLUMNS FROM {table} LIKE 'area'")
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {table} ADD COLUMN area VARCHAR(100) AFTER someday")
            # released_note arrived August 2026 (why a block lifted, bon-wevapu)
            cur.execute(f"SHOW COLUMNS FROM {table} LIKE 'released_note'")
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {table} ADD COLUMN released_note TEXT AFTER wait_note")
            # waiting_for was VARCHAR(500) until June 2026; as a JSON-serialised
            # blocker list it can legitimately exceed that, and overflow used to
            # abort a save mid-batch. Lossless widen, old clients unaffected.
            cur.execute(f"SHOW COLUMNS FROM {table} LIKE 'waiting_for'")
            col = cur.fetchone()
            if col and "varchar" in str(col.get("Type", "")).lower():
                cur.execute(f"ALTER TABLE {table} MODIFY COLUMN waiting_for TEXT")
        # repos.job arrived August 2026 (jobs-grouped review pyramid, bon-jagoha)
        cur.execute("SHOW COLUMNS FROM repos LIKE 'job'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE repos ADD COLUMN job VARCHAR(64) AFTER origin_url")
    conn.commit()


# ---------- row <-> dict conversion ----------

# Columns shared between items and archive tables
_ITEM_COLUMNS = [
    "id", "type", "title", "status", "brief", "parent", "order",
    "waiting_for", "wait_note", "released_note", "someday", "area", "tactical", "created_at", "created_by",
    "updated_at", "updated_by", "done_at", "done_note",
]

_ARCHIVE_COLUMNS = _ITEM_COLUMNS + ["archived_at"]

# VARCHAR limits mirroring _SCHEMA_SQL — checked before any write so an
# oversized value fails with a named item and field instead of a pymysql
# traceback halfway through a batch.
_VARCHAR_LIMITS = {
    "id": 64,
    "type": 10,
    "title": 500,
    "status": 10,
    "parent": 64,
    "area": 100,
    "created_at": 30,
    "created_by": 100,
    "updated_at": 30,
    "updated_by": 30,
    "done_at": 30,
    "archived_at": 30,
}


def _check_row_limits(row: dict) -> None:
    """Raise BonError if any value exceeds its column's VARCHAR limit."""
    for col, limit in _VARCHAR_LIMITS.items():
        val = row.get(col)
        if isinstance(val, str) and len(val) > limit:
            error(
                f"Value too long for '{col}' on {row.get('id', '<no id>')}: "
                f"{len(val)} chars (column limit {limit}). Nothing was written."
            )


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

# Per-process snapshot of the last loaded, normalised state of each prefix.
# save-time diffs run against this, so a save touches only the rows its own
# command changed (bon-resena: whole-prefix truncate-and-reinsert let one
# lane's save persist another lane's in-flight state as the whole board).
_LOAD_SNAPSHOTS: dict[str, dict[str, str]] = {}


def _canon_item(item: dict) -> str:
    """Canonical form for change detection — stable across key order."""
    return json.dumps(item, sort_keys=True, default=str)


def _select_prefix_committed(cur, table: str, prefix: str) -> list:
    """Read a prefix's rows from COMMITTED state, never the live working set.

    Dolt's sql-server serves other connections' in-flight transaction state
    to plain reads (measured 2026-08-23: a plain SELECT during another
    connection's uncommitted DELETE saw the deletion; the same read
    AS OF 'HEAD' saw committed truth). A plain load during a concurrent
    write therefore sees a half-written board — the trigger of the
    bon-resena row loss. AS OF 'HEAD' pins the read to the last Dolt commit.

    Fallback: a table that exists but has never been dolt-committed (a
    brand-new database mid-init) raises 'table not found' under AS OF —
    a plain read is safe there, since a board with no commit history has
    no concurrent-writer window to fear.
    """
    try:
        cur.execute(
            f"SELECT * FROM {table} AS OF 'HEAD' WHERE id LIKE %s",
            (f"{prefix}-%",),
        )
    except Exception:
        cur.execute(f"SELECT * FROM {table} WHERE id LIKE %s", (f"{prefix}-%",))
    return cur.fetchall()


def dolt_load_items(prefix: str | None = None) -> list[dict]:
    """Load all items for a project prefix from Dolt (default: current repo's).

    Deduplicates by ID (same contract as JSONL load_items). Reads committed
    state only, and snapshots the normalised result so the next save can
    write just the rows that actually changed (see _LOAD_SNAPSHOTS).
    """
    conn = _get_connection()
    prefix = prefix or load_prefix()

    with conn.cursor() as cur:
        rows = _select_prefix_committed(cur, "items", prefix)

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

    # Normalise BEFORE snapshotting — storage.load_items re-normalises the
    # returned list (idempotent), and the snapshot must match what cli code
    # actually holds, or every legacy-shaped row diffs as phantom-changed.
    result = _normalise_waiting_for(list(seen.values()))
    _LOAD_SNAPSHOTS[prefix] = {i["id"]: _canon_item(i) for i in result}
    return result


def dolt_save_items(items: list[dict], prefix: str | None = None) -> None:
    """Save items to Dolt, writing only the rows this process changed.

    Item-grain writes (bon-resena, adjudicated 2026-08-23): the save diffs
    the final list against the snapshot taken at load and touches only
    changed/new rows plus explicit deletions. Two lanes editing different
    items therefore commute — neither rewrites state it only *saw*. The
    old whole-prefix truncate-and-reinsert let a load that caught another
    lane's write mid-flight persist that half-board as truth (42 of 60
    rows lost in the two-writer reproduction), and let an old client null
    estate-wide fields it had never heard of (the someday/area decay).

    Population fallback: a save with no prior load in this process (migrate,
    init import) rewrites the whole prefix — those paths are deliberately
    board-grain and single-lane by nature.
    """
    conn = _get_connection()
    prefix = prefix or load_prefix()

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

    snapshot = _LOAD_SNAPSHOTS.get(prefix)
    if snapshot is None:
        to_write = sorted(seen.values(), key=lambda i: i.get("id", ""))
        deleted_ids: list[str] = []
    else:
        to_write = sorted(
            (item for iid, item in seen.items() if _canon_item(item) != snapshot.get(iid)),
            key=lambda i: i.get("id", ""),
        )
        deleted_ids = sorted(set(snapshot) - set(seen))
        if not to_write and not deleted_ids:
            return  # nothing changed — no write, no empty commit, no window

    rows = [_item_to_row(item) for item in to_write]
    for row in rows:
        _check_row_limits(row)

    with _write_transaction(conn, "items save"):
        with conn.cursor() as cur:
            if snapshot is None:
                # Population path: replace the whole prefix
                cur.execute("DELETE FROM items WHERE id LIKE %s", (f"{prefix}-%",))
            else:
                doomed = [item["id"] for item in to_write] + deleted_ids
                placeholders = ", ".join(["%s"] * len(doomed))
                cur.execute(
                    f"DELETE FROM items WHERE id IN ({placeholders})", doomed
                )

            for row in rows:
                cols = list(row.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                # Quote 'order' since it's a reserved word
                col_names = ", ".join(f"`{c}`" for c in cols)
                cur.execute(
                    f"INSERT INTO items ({col_names}) VALUES ({placeholders})",
                    list(row.values()),
                )

            # Keep the repos mapping table current — rides this same commit
            _register_repo(cur, prefix)

            # Dolt commit
            cmd_str = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "save"
            author = f"{get_creator()} <bon@localhost>"
            cur.execute("CALL DOLT_ADD('-A')")
            cur.execute(
                "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                (f"bon {cmd_str}", author),
            )

    # Keep the snapshot current so a second save in this process diffs
    # against what was just written, not the original load.
    _LOAD_SNAPSHOTS[prefix] = {iid: _canon_item(item) for iid, item in seen.items()}


# ---------- archive operations ----------

def dolt_load_archive(prefix: str | None = None) -> list[dict]:
    """Load archived items for a project prefix from Dolt (default: current repo's)."""
    conn = _get_connection()
    prefix = prefix or load_prefix()

    with conn.cursor() as cur:
        rows = _select_prefix_committed(cur, "archive", prefix)

    return [_row_to_item(row) for row in rows]


def dolt_append_archive(items: list[dict]) -> None:
    """Append items to the archive table, deduplicating by ID.

    A true append (bon-resena): only the incoming ids are written — an
    existing row survives untouched unless the incoming version is at least
    as recent. The old form rewrote the whole prefix's archive from a fresh
    load, which carried the same fractured-read amplification as items.
    """
    conn = _get_connection()

    # Intra-batch dedup (same contract as before)
    incoming: dict[str, dict] = {}
    for item in items:
        item_id = item.get("id", "")
        if item_id in incoming:
            if _most_recent_timestamp(item) >= _most_recent_timestamp(incoming[item_id]):
                incoming[item_id] = item
        else:
            incoming[item_id] = item

    # Only upsert where the incoming version is new or wins on recency
    existing = {i["id"]: i for i in dolt_load_archive()}
    upserts = [
        item for item_id, item in incoming.items()
        if item_id not in existing
        or _most_recent_timestamp(item) >= _most_recent_timestamp(existing[item_id])
    ]
    if not upserts:
        return

    prefix = load_prefix()
    rows = [_item_to_row(item, _ARCHIVE_COLUMNS)
            for item in sorted(upserts, key=lambda i: i.get("id", ""))]
    for row in rows:
        _check_row_limits(row)

    with _write_transaction(conn, "archive append"):
        with conn.cursor() as cur:
            doomed = [row["id"] for row in rows]
            placeholders = ", ".join(["%s"] * len(doomed))
            cur.execute(f"DELETE FROM archive WHERE id IN ({placeholders})", doomed)
            for row in rows:
                cols = list(row.keys())
                placeholders = ", ".join(["%s"] * len(cols))
                col_names = ", ".join(f"`{c}`" for c in cols)
                cur.execute(
                    f"INSERT INTO archive ({col_names}) VALUES ({placeholders})",
                    list(row.values()),
                )

            # Keep the repos mapping table current — rides this same commit
            _register_repo(cur, prefix)

            cmd_str = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "archive"
            author = f"{get_creator()} <bon@localhost>"
            cur.execute("CALL DOLT_ADD('-A')")
            cur.execute(
                "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                (f"bon {cmd_str}", author),
            )


def dolt_remove_from_archive(item_id: str, prefix: str | None = None) -> dict | None:
    """Remove an item from the archive table. Returns the item or None."""
    from bon.storage import find_by_id

    archived = dolt_load_archive()
    item = find_by_id(archived, item_id, prefix)
    if not item:
        return None

    conn = _get_connection()
    with _write_transaction(conn, f"archive removal of {item['id']}"):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM archive WHERE id = %s", (item["id"],))

            author = f"{get_creator()} <bon@localhost>"
            cur.execute("CALL DOLT_ADD('-A')")
            cur.execute(
                "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                (f"bon reopen {item['id']}", author),
            )
    return item


# ---------- repos mapping table ----------

def _repo_identity() -> tuple[str, str | None]:
    """Derive (repo_name, origin_url) for the current board root.

    repo_name is the board root's directory name; origin_url comes from
    git when the board lives in a repo with an origin remote, else None.
    """
    root = _data_dir().parent
    origin_url = None
    try:
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            origin_url = result.stdout.strip() or None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return root.name, origin_url


def _register_repo(cur, prefix: str, job: str | None = None) -> bool:
    """Sync this board's row in the repos mapping table.

    Compares before writing so an unchanged identity adds nothing to the
    caller's transaction. Returns True when a row was written.

    `job` is the review pyramid's repo-to-job grouping (bon-jagoha). It is
    human-curated: job=None means "leave whatever is there" — the parasitic
    save-path callers never pass it, so an ordinary write can't clear a
    curated value. Only an explicit `bon register --job` sets or changes it,
    and `--job ""` clears it (stored as NULL, surfacing as unassigned).
    """
    repo_name, origin_url = _repo_identity()
    cur.execute(
        "SELECT repo_name, origin_url, job FROM repos WHERE prefix = %s", (prefix,)
    )
    row = cur.fetchone()
    job_current = row["job"] if row else None
    if job is None:
        job_target = job_current
    else:
        job_target = job or None
    if (
        row
        and row["repo_name"] == repo_name
        and row["origin_url"] == origin_url
        and job_current == job_target
    ):
        return False
    if row is None:
        cur.execute(
            "INSERT INTO repos (prefix, repo_name, origin_url, job, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (prefix, repo_name, origin_url, job_target, now_iso()),
        )
    else:
        cur.execute(
            "UPDATE repos SET repo_name = %s, origin_url = %s, job = %s, "
            "updated_at = %s WHERE prefix = %s",
            (repo_name, origin_url, job_target, now_iso(), prefix),
        )
    return True


def dolt_register_repo(prefix: str | None = None, job: str | None = None) -> bool:
    """Upsert this board's repos-table row in its own Dolt commit.

    Explicit registration for `bon init --backend dolt` / `bon register` /
    post-migrate; ordinary writes register as a side-effect of
    dolt_save_items. Returns True when the row changed.
    """
    conn = _get_connection()
    prefix = prefix or load_prefix()
    with _write_transaction(conn, "repo registration"):
        with conn.cursor() as cur:
            changed = _register_repo(cur, prefix, job=job)
            if changed:
                author = f"{get_creator()} <bon@localhost>"
                cur.execute("CALL DOLT_ADD('-A')")
                cur.execute(
                    "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                    (f"bon register {prefix}", author),
                )
    return changed


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
