"""Tests for bon migrate command."""
import os
from unittest.mock import patch

import pytest

from bon.storage import BonError, _reset_backend, _reset_data_dir
from conftest import run_bon


class TestMigrateCommand:
    """Test the migrate CLI command."""

    def test_migrate_same_backend_noop(self, bon_dir):
        """Migrating to the same backend is a no-op."""
        result = run_bon("migrate", "--to", "jsonl", cwd=bon_dir)
        assert result.returncode == 0
        assert "Already using jsonl" in result.stdout

    def test_migrate_requires_init(self, tmp_path):
        """Migrate fails without .bon/."""
        result = run_bon("migrate", "--to", "dolt", cwd=tmp_path)
        assert result.returncode == 1
        assert "Not initialized" in result.stderr

    def test_migrate_invalid_backend(self, bon_dir):
        """Invalid backend name is rejected."""
        result = run_bon("migrate", "--to", "sqlite", cwd=bon_dir)
        assert result.returncode != 0  # argparse error


class TestInitBackend:
    """Test bon init --backend flag."""

    def test_init_default_jsonl(self, tmp_path):
        result = run_bon("init", "--prefix", "test", cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / ".bon" / "items.jsonl").exists()
        assert not (tmp_path / ".bon" / "backend").exists()

    def test_init_explicit_jsonl(self, tmp_path):
        result = run_bon("init", "--prefix", "test", "--backend", "jsonl", cwd=tmp_path)
        assert result.returncode == 0
        assert (tmp_path / ".bon" / "items.jsonl").exists()
        assert not (tmp_path / ".bon" / "backend").exists()

    def test_init_dolt(self, tmp_path):
        # Point Dolt at an unreachable local port: init must still succeed
        # (repos-table registration soft-fails with a warning) and must never
        # reach a real server from a unit test.
        env = dict(os.environ)
        env.update({"BON_DOLT_HOST": "127.0.0.1", "BON_DOLT_PORT": "9"})
        result = run_bon("init", "--prefix", "test", "--backend", "dolt", cwd=tmp_path, env=env)
        assert result.returncode == 0
        assert (tmp_path / ".bon" / "backend").read_text() == "dolt"
        assert (tmp_path / ".bon" / "prefix").read_text() == "test"
        # items.jsonl should NOT be created for dolt backend
        assert not (tmp_path / ".bon" / "items.jsonl").exists()
        assert "dolt" in result.stdout
        assert "could not register" in result.stderr

    def test_init_invalid_backend(self, tmp_path):
        result = run_bon("init", "--prefix", "test", "--backend", "mongo", cwd=tmp_path)
        assert result.returncode != 0  # argparse error


class TestSessionIdentity:
    """Test get_session_identity behavior."""

    def test_jsonl_uses_realpath(self, bon_dir, monkeypatch):
        """JSONL mode uses plain realpath."""
        import os

        from bon.storage import _reset_backend, _reset_data_dir, get_session_identity
        monkeypatch.chdir(bon_dir)
        _reset_data_dir()
        _reset_backend()
        session = get_session_identity()
        assert session == os.path.realpath(str(bon_dir))
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

    def test_migrate_to_dolt_fails_cleanly_when_server_down(self, bon_dir, monkeypatch):
        """If Dolt is unreachable, backend file should not be written."""
        from bon.cli import cmd_migrate

        monkeypatch.chdir(bon_dir)
        _reset_data_dir()
        _reset_backend()

        # Create a stub item so there's something to migrate
        (bon_dir / ".bon" / "items.jsonl").write_text(
            '{"id":"bon-aaa","type":"outcome","title":"t","brief":{"why":"w","what":"x","done":"d"},'
            '"status":"open","order":1,"created_at":"2026-01-01T00:00:00Z","created_by":"test"}\n'
        )

        class Args:
            to = "dolt"

        with patch("bon.dolt.verify_dolt_connection", side_effect=BonError("Cannot connect")):
            with pytest.raises(BonError, match="Cannot connect"):
                cmd_migrate(Args())

        # Backend file must NOT have been written
        assert not (bon_dir / ".bon" / "backend").exists()
        # JSONL files must be untouched
        assert (bon_dir / ".bon" / "items.jsonl").exists()
        assert not (bon_dir / ".bon" / "items.jsonl.pre-dolt").exists()

    @pytest.mark.skipif(
        os.environ.get("BON_DOLT_TEST") != "1",
        reason="BON_DOLT_TEST=1 not set",
    )
    def test_migrate_to_dolt_succeeds_with_live_server(self, bon_dir, monkeypatch):
        """With a running Dolt server, migration should complete."""
        monkeypatch.chdir(bon_dir)
        _reset_data_dir()
        _reset_backend()

        result = run_bon("migrate", "--to", "dolt", cwd=bon_dir)
        assert result.returncode == 0
        assert (bon_dir / ".bon" / "backend").read_text() == "dolt"


class TestMigrateDoltPrefixCollision:
    """Test that migrate --to dolt refuses when another repo's items already exist."""

    def _stub_item(self, bon_dir):
        (bon_dir / ".bon" / "items.jsonl").write_text(
            '{"id":"bon-aaa","type":"outcome","title":"t","brief":{"why":"w","what":"x","done":"d"},'
            '"status":"open","order":1,"created_at":"2026-01-01T00:00:00Z","created_by":"test"}\n'
        )

    def test_refuses_on_collision(self, bon_dir, monkeypatch):
        """If Dolt has prefix-rows we don't own, migration is refused and no state is mutated."""
        from bon.cli import cmd_migrate

        monkeypatch.chdir(bon_dir)
        _reset_data_dir()
        _reset_backend()
        self._stub_item(bon_dir)

        class Args:
            to = "dolt"

        def fake_collision(prefix, local_item_ids, local_archive_ids):
            from bon.storage import error
            error(
                f"Refusing to migrate: Dolt already has rows with prefix '{prefix}' "
                f"that are not in this repo's local data."
            )

        with patch("bon.dolt.verify_dolt_connection"), \
             patch("bon.dolt.check_prefix_collision", side_effect=fake_collision):
            with pytest.raises(BonError, match="Refusing to migrate"):
                cmd_migrate(Args())

        # Backend file must NOT have been written
        assert not (bon_dir / ".bon" / "backend").exists()
        # JSONL must be untouched
        assert (bon_dir / ".bon" / "items.jsonl").exists()
        assert not (bon_dir / ".bon" / "items.jsonl.pre-dolt").exists()

    def test_collision_check_called_with_local_ids(self, bon_dir, monkeypatch):
        """Verify the helper receives our prefix and local IDs (so the foreign-vs-local subtraction is correct)."""
        from bon.cli import cmd_migrate

        monkeypatch.chdir(bon_dir)
        _reset_data_dir()
        _reset_backend()
        self._stub_item(bon_dir)

        class Args:
            to = "dolt"

        captured = {}

        def capture(prefix, local_item_ids, local_archive_ids):
            captured["prefix"] = prefix
            captured["item_ids"] = local_item_ids
            captured["archive_ids"] = local_archive_ids
            # Don't raise — let the rest of the migration proceed (or fail later).
            from bon.storage import error
            error("stop here")  # halt before touching real Dolt

        with patch("bon.dolt.verify_dolt_connection"), \
             patch("bon.dolt.check_prefix_collision", side_effect=capture):
            with pytest.raises(BonError, match="stop here"):
                cmd_migrate(Args())

        assert captured["prefix"] == "bon"
        assert captured["item_ids"] == {"bon-aaa"}
        assert captured["archive_ids"] == set()
        # And nothing got written
        assert not (bon_dir / ".bon" / "backend").exists()

class TestRegisterCommand:
    """bon register — the manual/backfill path for the repos mapping table."""

    def test_register_requires_dolt_backend(self, bon_dir):
        result = run_bon("register", cwd=bon_dir)
        assert result.returncode == 1
        assert "requires the Dolt backend" in result.stderr

    def test_register_requires_init(self, tmp_path):
        result = run_bon("register", cwd=tmp_path)
        assert result.returncode == 1
        assert "Not initialized" in result.stderr
