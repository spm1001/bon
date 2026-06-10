"""Tests for the Dolt backend — mocked, no real Dolt needed."""
import json
from unittest.mock import MagicMock, patch

import pytest

from bon.storage import (
    BonError,
    _get_backend,
    _reset_backend,
    _reset_data_dir,
    append_archive,
    items_path,
    load_archive,
    load_items,
    remove_from_archive,
    save_items,
)

# ---------- backend detection ----------

class TestGetBackend:
    def test_default_is_jsonl(self, tmp_path, monkeypatch):
        """No .bon/backend file means JSONL."""
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()
        assert _get_backend() == "jsonl"

    def test_reads_backend_file(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()
        assert _get_backend() == "dolt"

    def test_strips_and_lowercases(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("  Dolt \n")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()
        assert _get_backend() == "dolt"

    def test_caches_result(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()
        assert _get_backend() == "dolt"
        # Change the file — cached value should stick
        (bon_dir / "backend").write_text("jsonl")
        assert _get_backend() == "dolt"


# ---------- items_path in dolt mode ----------

class TestItemsPathDolt:
    def test_raises_in_dolt_mode(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()
        with pytest.raises(BonError, match="not available in Dolt mode"):
            items_path()


# ---------- dispatch: load_items ----------

class TestLoadItemsDolt:
    def test_dispatches_to_dolt(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        (bon_dir / "prefix").write_text("test")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        mock_items = [{"id": "test-abc", "type": "outcome", "title": "T", "status": "open"}]
        with patch("bon.dolt.dolt_load_items", return_value=mock_items) as mock:
            result = load_items()
            mock.assert_called_once()
            assert result == mock_items


# ---------- dispatch: save_items ----------

class TestSaveItemsDolt:
    def test_dispatches_to_dolt(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        (bon_dir / "prefix").write_text("test")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        items = [{"id": "test-abc", "type": "outcome", "title": "T", "status": "open"}]
        with patch("bon.dolt.dolt_save_items") as mock:
            save_items(items)
            mock.assert_called_once_with(items)


# ---------- dispatch: archive operations ----------

class TestBonhiveDolt:
    def test_load_archive_dispatches(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        with patch("bon.dolt.dolt_load_archive", return_value=[]) as mock:
            result = load_archive()
            mock.assert_called_once()
            assert result == []

    def test_append_archive_dispatches(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        items = [{"id": "test-abc", "type": "outcome", "title": "T", "status": "done"}]
        with patch("bon.dolt.dolt_append_archive") as mock:
            append_archive(items)
            mock.assert_called_once_with(items)

    def test_remove_from_archive_dispatches(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        with patch("bon.dolt.dolt_remove_from_archive", return_value=None) as mock:
            result = remove_from_archive("test-abc", "test")
            mock.assert_called_once_with("test-abc", "test")
            assert result is None


# ---------- dolt.py internal functions ----------

class TestDoltConfig:
    def test_env_vars_override_defaults(self, monkeypatch):
        monkeypatch.setenv("BON_DOLT_HOST", "10.0.0.1")
        monkeypatch.setenv("BON_DOLT_PORT", "3307")
        monkeypatch.setenv("BON_DOLT_DATABASE", "mydb")
        monkeypatch.setenv("BON_DOLT_USER", "testuser")
        monkeypatch.setenv("BON_DOLT_PASSWORD", "secret")

        from bon.dolt import _load_dolt_config
        config = _load_dolt_config()

        assert config["host"] == "10.0.0.1"
        assert config["port"] == 3307
        assert config["database"] == "mydb"
        assert config["user"] == "testuser"
        assert config["password"] == "secret"

    def test_invalid_port_raises(self, monkeypatch):
        monkeypatch.setenv("BON_DOLT_PORT", "notanumber")
        monkeypatch.setenv("BON_DOLT_HOST", "localhost")

        from bon.dolt import _load_dolt_config
        with pytest.raises(BonError, match="must be an integer"):
            _load_dolt_config()

    def test_defaults_when_nothing_set(self, monkeypatch, tmp_path):
        # Clear all env vars
        for key in ("BON_DOLT_HOST", "BON_DOLT_PORT", "BON_DOLT_DATABASE",
                     "BON_DOLT_USER", "BON_DOLT_PASSWORD"):
            monkeypatch.delenv(key, raising=False)
        # No config file
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        from bon.dolt import _load_dolt_config
        config = _load_dolt_config()

        assert config["host"] == "127.0.0.1"
        assert config["port"] == 3306
        assert config["database"] == "bon"
        assert config["user"] == "root"


class TestDoltRowConversion:
    def test_item_to_row_serializes_json(self):
        from bon.dolt import _item_to_row
        item = {
            "id": "test-abc",
            "type": "outcome",
            "title": "Test",
            "status": "open",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "tactical": {"steps": ["a", "b"], "current": 0},
            "order": 1,
        }
        row = _item_to_row(item)
        assert isinstance(row["brief"], str)
        assert json.loads(row["brief"]) == {"why": "w", "what": "x", "done": "d"}
        assert isinstance(row["tactical"], str)
        assert row["id"] == "test-abc"

    def test_row_to_item_deserializes_json(self):
        from bon.dolt import _row_to_item
        row = {
            "id": "test-abc",
            "type": "outcome",
            "title": "Test",
            "status": "open",
            "brief": '{"why": "w", "what": "x", "done": "d"}',
            "tactical": None,
            "order": 1,
            "parent": None,
            "waiting_for": None,
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "test",
            "updated_at": None,
            "updated_by": None,
            "done_at": None,
            "done_note": None,
        }
        item = _row_to_item(row)
        assert item["brief"] == {"why": "w", "what": "x", "done": "d"}
        assert "tactical" not in item  # None tactical omitted
        assert item["order"] == 1

    def test_row_to_item_handles_auto_parsed_json(self):
        """PyMySQL may auto-parse JSON columns as dicts."""
        from bon.dolt import _row_to_item
        row = {
            "id": "test-abc",
            "type": "outcome",
            "title": "Test",
            "status": "open",
            "brief": {"why": "w", "what": "x", "done": "d"},  # Already a dict
            "tactical": None,
            "order": None,
            "parent": None,
            "waiting_for": None,
            "created_at": None,
            "created_by": None,
            "updated_at": None,
            "updated_by": None,
            "done_at": None,
            "done_note": None,
        }
        item = _row_to_item(row)
        assert item["brief"] == {"why": "w", "what": "x", "done": "d"}
        assert item["order"] == 999  # None order defaults to 999

    def test_roundtrip(self):
        """item -> row -> item preserves data."""
        from bon.dolt import _item_to_row, _row_to_item
        original = {
            "id": "test-abc",
            "type": "action",
            "title": "Do the thing",
            "status": "open",
            "brief": {"why": "because", "what": "stuff", "done": "check"},
            "parent": "test-xyz",
            "order": 3,
            "waiting_for": None,
            "tactical": {"steps": ["a", "b"], "current": 1, "session": "/tmp/foo"},
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "test",
            "updated_at": "2026-01-02T00:00:00Z",
            "updated_by": "edited",
            "done_at": None,
            "done_note": None,
        }
        row = _item_to_row(original)
        restored = _row_to_item(row)
        assert restored["id"] == original["id"]
        assert restored["brief"] == original["brief"]
        assert restored["tactical"] == original["tactical"]
        assert restored["order"] == original["order"]


class TestEnsurePymysql:
    def test_missing_pymysql_raises(self, monkeypatch):
        """When pymysql is not installed, give a clear error."""
        import bon.dolt
        # Reset cached module
        bon.dolt._pymysql = None

        # Make import fail
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pymysql":
                raise ImportError("No module named 'pymysql'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        with pytest.raises(BonError, match="PyMySQL"):
            bon.dolt._ensure_pymysql()

        # Restore
        bon.dolt._pymysql = None


class TestGetConnection:
    def test_no_config_raises(self, monkeypatch, tmp_path):
        """No env vars and no config file → helpful error."""
        for key in ("BON_DOLT_HOST", "BON_DOLT_PORT", "BON_DOLT_DATABASE",
                     "BON_DOLT_USER", "BON_DOLT_PASSWORD"):
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        import bon.dolt
        bon.dolt._cached_connection = None
        # Provide a fake pymysql so _ensure_pymysql passes
        bon.dolt._pymysql = MagicMock()

        with pytest.raises(BonError, match="connection config"):
            bon.dolt._get_connection()

        bon.dolt._pymysql = None
        bon.dolt._cached_connection = None


class TestDoltLog:
    def test_queries_dolt_log(self):
        import bon.dolt
        from bon.dolt import dolt_log

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"date": "2026-01-01", "message": "bon new", "committer": "test"},
        ]
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        # Set both cached connection and pymysql mock to bypass real imports
        bon.dolt._cached_connection = mock_conn
        bon.dolt._pymysql = MagicMock()
        mock_conn.ping = MagicMock()

        try:
            result = dolt_log(limit=10)
            assert len(result) == 1
            assert result[0]["message"] == "bon new"

            # Verify the query
            mock_cursor.execute.assert_called_once()
            sql = mock_cursor.execute.call_args[0][0]
            assert "dolt_log" in sql
        finally:
            bon.dolt._cached_connection = None
            bon.dolt._pymysql = None


# ---------- jsonl path unchanged ----------

class TestJsonlUnchanged:
    """Verify JSONL path is completely unaffected by the Dolt code."""

    def test_load_items_jsonl(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "items.jsonl").write_text(
            '{"id":"test-abc","type":"outcome","title":"T","status":"open"}\n'
        )
        (bon_dir / "prefix").write_text("test")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        items = load_items()
        assert len(items) == 1
        assert items[0]["id"] == "test-abc"

    def test_save_items_jsonl(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "items.jsonl").touch()
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        items = [{"id": "test-abc", "type": "outcome", "title": "T", "status": "open"}]
        save_items(items)

        content = (bon_dir / "items.jsonl").read_text()
        assert "test-abc" in content

    def test_items_path_jsonl(self, tmp_path, monkeypatch):
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()

        path = items_path()
        assert path.name == "items.jsonl"


# ---------- write transaction & pre-flight limits ----------

class TestWriteTransaction:
    def test_commits_on_success(self):
        from bon.dolt import _write_transaction
        conn = MagicMock()
        with _write_transaction(conn, "test"):
            pass
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_rolls_back_and_raises_bon_error_on_failure(self):
        from bon.dolt import _write_transaction
        conn = MagicMock()
        with pytest.raises(BonError, match="rolled back"):
            with _write_transaction(conn, "items save"):
                raise RuntimeError("mid-batch INSERT exploded")
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_rollback_failure_does_not_mask_original_error(self):
        from bon.dolt import _write_transaction
        conn = MagicMock()
        conn.rollback.side_effect = RuntimeError("connection gone")
        with pytest.raises(BonError, match="exploded"):
            with _write_transaction(conn, "items save"):
                raise RuntimeError("exploded")


class TestCheckRowLimits:
    def test_oversized_title_names_field_and_item(self):
        from bon.dolt import _check_row_limits
        with pytest.raises(BonError) as exc:
            _check_row_limits({"id": "test-aaa", "title": "x" * 501})
        assert "title" in str(exc.value)
        assert "test-aaa" in str(exc.value)

    def test_within_limits_passes(self):
        from bon.dolt import _check_row_limits
        # waiting_for is TEXT now — deliberately unbounded
        _check_row_limits({
            "id": "test-aaa",
            "title": "x" * 500,
            "waiting_for": "y" * 5000,
        })

    def test_non_string_values_ignored(self):
        from bon.dolt import _check_row_limits
        _check_row_limits({"id": "test-aaa", "order": 999999999, "title": None})


class TestSaveItemsAtomicity:
    def _item(self, suffix):
        return {
            "id": f"test-{suffix}",
            "type": "action",
            "title": f"atomicity {suffix}",
            "status": "open",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "order": 1,
            "created_at": "2026-06-10T20:00:00Z",
            "created_by": "test",
        }

    def test_mid_batch_insert_failure_rolls_back(self):
        from bon import dolt as dolt_mod
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        inserts = {"count": 0}

        def fail_second_insert(sql, params=None):
            if sql.startswith("INSERT"):
                inserts["count"] += 1
                if inserts["count"] == 2:
                    raise RuntimeError("Data too long for column")

        cur.execute.side_effect = fail_second_insert
        with patch.object(dolt_mod, "_get_connection", return_value=conn), \
             patch.object(dolt_mod, "_dolt_load_prefix_local", return_value="test"):
            with pytest.raises(BonError, match="rolled back"):
                dolt_mod.dolt_save_items([self._item("aaa"), self._item("bbb")])
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()

    def test_oversized_title_fails_before_any_sql(self):
        from bon import dolt as dolt_mod
        conn = MagicMock()
        bad = self._item("aaa")
        bad["title"] = "x" * 501
        with patch.object(dolt_mod, "_get_connection", return_value=conn), \
             patch.object(dolt_mod, "_dolt_load_prefix_local", return_value="test"):
            with pytest.raises(BonError, match="title"):
                dolt_mod.dolt_save_items([bad])
        conn.cursor.assert_not_called()
        conn.rollback.assert_not_called()
