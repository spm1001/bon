"""Tests for bon migrate command."""
import os
from unittest.mock import patch

import pytest

from bon.storage import BonError, _reset_backend, _reset_data_dir
from conftest import run_arc


class TestMigrateCommand:
    """Test the migrate CLI command."""

    def test_migrate_same_backend_noop(self, arc_dir):
        """Migrating to the same backend is a no-op."""
        result = run_arc("migrate", "--to", "jsonl", cwd=arc_dir)
        assert result.returncode == 0
        assert "Already using jsonl" in result.stdout

    def test_migrate_requires_init(self, tmp_path):
        """Migrate fails without .bon/."""
        result = run_arc("migrate", "--to", "dolt", cwd=tmp_path)
        assert result.returncode == 1
        assert "Not initialized" in result.stderr

    def test_migrate_invalid_backend(self, arc_dir):
        """Invalid backend name is rejected."""
        result = run_arc("migrate", "--to", "sqlite", cwd=arc_dir)
        assert result.returncode != 0  # argparse error


class TestInitBackend:
    """Test bon init --backend flag."""

    def test_init_default_jsonl(self, tmp_path):
        result = run_arc("init", "--prefix", "test", cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / ".bon" / "items.jsonl").exists()
        assert not (tmp_path / ".bon" / "backend").exists()

    def test_init_explicit_jsonl(self, tmp_path):
        result = run_arc("init", "--prefix", "test", "--backend", "jsonl", cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / ".bon" / "items.jsonl").exists()
        assert not (tmp_path / ".bon" / "backend").exists()

    def test_init_dolt(self, tmp_path):
        result = run_arc("init", "--prefix", "test", "--backend", "dolt", cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / ".bon" / "backend").read_text() == "dolt"
        assert (tmp_path / ".bon" / "prefix").read_text() == "test"
        # items.jsonl should NOT be created for dolt backend
        assert not (tmp_path / ".bon" / "items.jsonl").exists()
        assert "dolt" in result.stdout

    def test_init_invalid_backend(self, tmp_path):
        result = run_arc("init", "--prefix", "test", "--backend", "mongo", cwd=tmp_path)
        assert result.returncode != 0  # argparse error


class TestSessionIdentity:
    """Test get_session_identity behavior."""

    def test_jsonl_uses_realpath(self, arc_dir, monkeypatch):
        """JSONL mode uses plain realpath."""
        import os

        from bon.storage import _reset_backend, _reset_data_dir, get_session_identity
        monkeypatch.chdir(arc_dir)
        _reset_data_dir()
        _reset_backend()
        session = get_session_identity()
        assert session == os.path.realpath(str(arc_dir))
        assert ":" not in session or session[1] == ":"  # Allow Windows drive letters

    def test_dolt_includes_hostname(self, tmp_path, monkeypatch):
        """Dolt mode prefixes with hostname."""
        import os
        import socket

        from bon.storage import _reset_backend, _reset_data_dir, get_session_identity
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir()
        (bon_dir / "backend").write_text("dolt")
        (bon_dir / "prefix").write_text("test")
        monkeypatch.chdir(tmp_path)
        _reset_data_dir()
        _reset_backend()
        session = get_session_identity()
        hostname = socket.gethostname()
        expected = f"{hostname}:{os.path.realpath(str(tmp_path))}"
        assert session == expected


class TestMigrateDoltVerification:
    """Test that migrate --to dolt verifies connection before switching backend."""

    def test_migrate_to_dolt_fails_cleanly_when_server_down(self, arc_dir, monkeypatch):
        """If Dolt is unreachable, backend file should not be written."""
        from bon.cli import cmd_migrate

        monkeypatch.chdir(arc_dir)
        _reset_data_dir()
        _reset_backend()

        # Create a stub item so there's something to migrate
        (arc_dir / ".bon" / "items.jsonl").write_text(
            '{"id":"arc-aaa","type":"outcome","title":"t","brief":{"why":"w","what":"x","done":"d"},'
            '"status":"open","order":1,"created_at":"2026-01-01T00:00:00Z","created_by":"test"}\n'
        )

        class Args:
            to = "dolt"

        with patch("bon.dolt.verify_dolt_connection", side_effect=BonError("Cannot connect")):
            with pytest.raises(BonError, match="Cannot connect"):
                cmd_migrate(Args())

        # Backend file must NOT have been written
        assert not (arc_dir / ".bon" / "backend").exists()
        # JSONL files must be untouched
        assert (arc_dir / ".bon" / "items.jsonl").exists()
        assert not (arc_dir / ".bon" / "items.jsonl.pre-dolt").exists()

    @pytest.mark.skipif(
        os.environ.get("BON_DOLT_TEST") != "1",
        reason="BON_DOLT_TEST=1 not set",
    )
    def test_migrate_to_dolt_succeeds_with_live_server(self, arc_dir, monkeypatch):
        """With a running Dolt server, migration should complete."""
        monkeypatch.chdir(arc_dir)
        _reset_data_dir()
        _reset_backend()

        result = run_arc("migrate", "--to", "dolt", cwd=arc_dir)
        assert result.returncode == 0
        assert (arc_dir / ".bon" / "backend").read_text() == "dolt"
