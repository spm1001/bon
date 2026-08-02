"""Integration tests for Dolt backend — requires a running Dolt server.

Skipped unless BON_DOLT_TEST=1 is set. Expects connection via
BON_DOLT_HOST / BON_DOLT_PORT / BON_DOLT_DATABASE / BON_DOLT_USER env vars.

These tests use a unique prefix per run to avoid collisions.
"""
import os
import uuid

import pytest

# Skip entire module unless opted in
pytestmark = pytest.mark.skipif(
    os.environ.get("BON_DOLT_TEST") != "1",
    reason="BON_DOLT_TEST=1 not set — skipping Dolt integration tests",
)

from bon.storage import (
    BonError,
    _reset_backend,
    _reset_data_dir,
    append_archive,
    load_archive,
    load_items,
    now_iso,
    remove_from_archive,
    save_items,
)


@pytest.fixture
def dolt_dir(tmp_path, monkeypatch):
    """Create a temp dir configured for Dolt backend with a unique prefix."""
    bon_dir = tmp_path / ".bon"
    bon_dir.mkdir()
    (bon_dir / "backend").write_text("dolt")
    # Unique prefix to avoid cross-test collisions
    prefix = f"test{uuid.uuid4().hex[:6]}"
    (bon_dir / "prefix").write_text(prefix)
    monkeypatch.chdir(tmp_path)
    _reset_data_dir()
    _reset_backend()

    yield tmp_path, prefix

    # Cleanup: remove test items from the DB
    try:
        from bon.dolt import _get_connection
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM items WHERE id LIKE %s", (f"{prefix}-%",))
            cur.execute("DELETE FROM archive WHERE id LIKE %s", (f"{prefix}-%",))
            cur.execute("DELETE FROM repos WHERE prefix = %s", (prefix,))
            cur.execute("CALL DOLT_ADD('-A')")
            cur.execute(
                "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                (f"test cleanup {prefix}", "test <test@localhost>"),
            )
        conn.commit()
    except Exception:
        pass  # Best-effort cleanup


class TestDoltIntegration:
    def test_roundtrip_items(self, dolt_dir):
        _, prefix = dolt_dir
        ts = now_iso()
        items = [
            {
                "id": f"{prefix}-aaa",
                "type": "outcome",
                "title": "Integration test outcome",
                "status": "open",
                "brief": {"why": "testing", "what": "1. verify", "done": "passes"},
                "order": 1,
                "created_at": ts,
                "created_by": "test",
            },
            {
                "id": f"{prefix}-bbb",
                "type": "action",
                "title": "Integration test action",
                "status": "open",
                "brief": {"why": "testing", "what": "check", "done": "works"},
                "parent": f"{prefix}-aaa",
                "order": 1,
                "created_at": ts,
                "created_by": "test",
            },
        ]
        save_items(items)
        loaded = load_items()

        assert len(loaded) == 2
        ids = {i["id"] for i in loaded}
        assert f"{prefix}-aaa" in ids
        assert f"{prefix}-bbb" in ids

        # Verify brief roundtrip
        outcome = next(i for i in loaded if i["id"] == f"{prefix}-aaa")
        assert outcome["brief"]["why"] == "testing"

        # Bottle refresh rides Dolt saves too (the .bon dir is still local)
        tmp_root, _ = dolt_dir
        from bon.storage import BOARD_README
        assert (tmp_root / ".bon" / "README.md").read_text() == BOARD_README

    def test_archive_roundtrip(self, dolt_dir):
        _, prefix = dolt_dir
        ts = now_iso()
        item = {
            "id": f"{prefix}-bon",
            "type": "outcome",
            "title": "Archived item",
            "status": "done",
            "brief": {"why": "done", "what": "done", "done": "done"},
            "order": 1,
            "created_at": ts,
            "created_by": "test",
            "done_at": ts,
            "archived_at": ts,
        }
        append_archive([item])
        loaded = load_archive()
        assert any(i["id"] == f"{prefix}-bon" for i in loaded)

        # Remove from archive
        removed = remove_from_archive(f"{prefix}-bon", prefix)
        assert removed is not None
        assert removed["id"] == f"{prefix}-bon"

        # Verify removed
        loaded2 = load_archive()
        assert not any(i["id"] == f"{prefix}-bon" for i in loaded2)

    def test_tactical_roundtrip(self, dolt_dir):
        _, prefix = dolt_dir
        ts = now_iso()
        items = [{
            "id": f"{prefix}-tac",
            "type": "action",
            "title": "Tactical test",
            "status": "open",
            "brief": {"why": "t", "what": "1. a 2. b", "done": "d"},
            "parent": None,
            "order": 1,
            "tactical": {
                "steps": ["Step A", "Step B"],
                "current": 0,
                "session": "/tmp/test",
                "skipped": {"1": "not needed"},
            },
            "created_at": ts,
            "created_by": "test",
        }]
        save_items(items)
        loaded = load_items()
        item = next(i for i in loaded if i["id"] == f"{prefix}-tac")
        assert item["tactical"]["steps"] == ["Step A", "Step B"]
        assert item["tactical"]["current"] == 0
        assert item["tactical"]["session"] == "/tmp/test"
        assert item["tactical"]["skipped"] == {"1": "not needed"}

    def test_prefix_isolation(self, dolt_dir):
        """Items from other prefixes are not visible."""
        _, prefix = dolt_dir
        ts = now_iso()
        items = [{
            "id": f"{prefix}-iso",
            "type": "outcome",
            "title": "Visible",
            "status": "open",
            "brief": {"why": "t", "what": "t", "done": "t"},
            "order": 1,
            "created_at": ts,
            "created_by": "test",
        }]
        save_items(items)

        # load_items only returns this prefix's items
        loaded = load_items()
        for item in loaded:
            assert item["id"].startswith(f"{prefix}-")

    def test_migrate_refuses_when_foreign_prefix_rows_exist(self, tmp_path, monkeypatch):
        """JSONL→Dolt migration refuses when Dolt has foreign prefix-rows.

        Reproduces the 2026-04-24 incident: two repos sharing a prefix,
        second repo's migrate would silently DELETE first repo's items.
        """
        prefix = f"coll{uuid.uuid4().hex[:6]}"
        ts = now_iso()

        # Step 1: plant a "foreign" row in Dolt using save_items() from a
        # throwaway Dolt-backed dir with this prefix.
        repo_a = tmp_path / "repo_a"
        bon_a = repo_a / ".bon"
        bon_a.mkdir(parents=True)
        (bon_a / "backend").write_text("dolt")
        (bon_a / "prefix").write_text(prefix)
        monkeypatch.chdir(repo_a)
        _reset_data_dir()
        _reset_backend()
        save_items([{
            "id": f"{prefix}-foreign",
            "type": "outcome",
            "title": "Foreign repo data",
            "status": "open",
            "brief": {"why": "foreign", "what": "foreign", "done": "foreign"},
            "order": 1,
            "created_at": ts,
            "created_by": "other",
        }])

        try:
            # Step 2: set up a JSONL repo with the same prefix and a DIFFERENT id.
            repo_b = tmp_path / "repo_b"
            bon_b = repo_b / ".bon"
            bon_b.mkdir(parents=True)
            (bon_b / "prefix").write_text(prefix)
            (bon_b / "items.jsonl").write_text(
                f'{{"id":"{prefix}-mine","type":"outcome","title":"my item",'
                f'"brief":{{"why":"w","what":"x","done":"d"}},"status":"open","order":1,'
                f'"created_at":"2026-01-01T00:00:00Z","created_by":"test"}}\n'
            )
            monkeypatch.chdir(repo_b)
            _reset_data_dir()
            _reset_backend()

            from bon.cli import cmd_migrate
            from bon.storage import BonError

            class Args:
                to = "dolt"

            with pytest.raises(BonError, match="Refusing to migrate"):
                cmd_migrate(Args())

            # Foreign row must survive
            from bon.dolt import _get_connection
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM items WHERE id = %s", (f"{prefix}-foreign",))
                assert cur.fetchone() is not None, "Foreign row was destroyed!"

            # Backend file must NOT have been switched in repo_b
            assert not (bon_b / "backend").exists()
            # JSONL must NOT have been renamed
            assert (bon_b / "items.jsonl").exists()
            assert not (bon_b / "items.jsonl.pre-dolt").exists()
        finally:
            # Cleanup: remove all rows for this prefix
            from bon.dolt import _get_connection
            conn = _get_connection()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM items WHERE id LIKE %s", (f"{prefix}-%",))
                cur.execute("DELETE FROM repos WHERE prefix = %s", (prefix,))
                cur.execute("CALL DOLT_ADD('-A')")
                cur.execute(
                    "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                    (f"test cleanup {prefix}", "test <test@localhost>"),
                )
            conn.commit()


class TestWriteAtomicity:
    """Regression tests for the 2026-06-07 half-wipe (bon-mozove).

    A mid-batch INSERT failure used to leave the shared working set with
    rows deleted but not reinserted. These exercise the real server: the
    failure must roll back, leaving committed rows untouched.
    """

    def _item(self, prefix, suffix, **overrides):
        item = {
            "id": f"{prefix}-{suffix}",
            "type": "action",
            "title": f"atomicity test {suffix}",
            "status": "open",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "order": 1,
            "created_at": now_iso(),
            "created_by": "test",
        }
        item.update(overrides)
        return item

    def test_oversized_waiting_for_now_saves(self, dolt_dir):
        """The original incident input — a ~700-char reason — now round-trips."""
        _, prefix = dolt_dir
        long_reason = "waiting because " + "x" * 700
        save_items([self._item(prefix, "aaa", waiting_for=[long_reason])])
        loaded = load_items()
        assert len(loaded) == 1
        assert loaded[0]["waiting_for"] == [long_reason]

    def test_failed_write_leaves_committed_rows_unchanged(self, dolt_dir):
        _, prefix = dolt_dir
        good = [self._item(prefix, "aaa"), self._item(prefix, "bbb")]
        save_items(good)

        # Poison passes pre-flight (length checks) but fails at the DB
        # layer: a non-numeric string into the INT `order` column.
        poison = self._item(prefix, "ccc", order="not-a-number")
        with pytest.raises(BonError, match="rolled back"):
            save_items(good + [poison])

        loaded = load_items()
        assert sorted(i["id"] for i in loaded) == [f"{prefix}-aaa", f"{prefix}-bbb"]

    def test_oversized_title_fails_clean_before_write(self, dolt_dir):
        _, prefix = dolt_dir
        save_items([self._item(prefix, "aaa")])

        bad = self._item(prefix, "bbb", title="x" * 501)
        with pytest.raises(BonError, match="title"):
            save_items([self._item(prefix, "aaa"), bad])

        loaded = load_items()
        assert [i["id"] for i in loaded] == [f"{prefix}-aaa"]


class TestDoltMove:
    """Cross-prefix move within the shared Dolt database (bon move)."""

    def test_move_between_dolt_boards(self, tmp_path, monkeypatch):
        import subprocess
        import sys

        def make_dolt_board(name):
            root = tmp_path / name
            bon = root / ".bon"
            bon.mkdir(parents=True)
            (bon / "backend").write_text("dolt")
            prefix = f"test{uuid.uuid4().hex[:6]}"
            (bon / "prefix").write_text(prefix)
            return root, prefix

        src_root, src_prefix = make_dolt_board("source")
        tgt_root, tgt_prefix = make_dolt_board("target")

        try:
            # Seed the source board via the library
            monkeypatch.chdir(src_root)
            _reset_data_dir()
            _reset_backend()
            save_items([{
                "id": f"{src_prefix}-mova",
                "type": "action",
                "title": "Dolt move test",
                "status": "open",
                "brief": {"why": "original why", "what": "x", "done": "d"},
                "parent": None,
                "order": 1,
                "created_at": now_iso(),
                "created_by": "test",
                "waiting_for": None,
            }])

            # Move via the real CLI
            result = subprocess.run(
                [sys.executable, "-m", "bon.cli", "move",
                 f"{src_prefix}-mova", "--to", str(tgt_root), "-q"],
                capture_output=True, text=True, cwd=src_root,
            )
            assert result.returncode == 0, f"stderr: {result.stderr}"
            new_id = result.stdout.strip()
            assert new_id.startswith(f"{tgt_prefix}-")

            # Target board sees the new item with provenance
            monkeypatch.chdir(tgt_root)
            _reset_data_dir()
            _reset_backend()
            t_items = load_items()
            new = next(i for i in t_items if i["id"] == new_id)
            assert new["title"] == "Dolt move test"
            assert new["status"] == "open"
            assert f"[Moved from {src_prefix}-mova" in new["brief"]["why"]

            # Source closed with cross-reference
            monkeypatch.chdir(src_root)
            _reset_data_dir()
            _reset_backend()
            s_items = load_items()
            src = next(i for i in s_items if i["id"] == f"{src_prefix}-mova")
            assert src["status"] == "done"
            assert src["updated_by"] == "moved"
            assert src["done_note"].startswith(f"Moved to {new_id}")
        finally:
            try:
                from bon.dolt import _get_connection
                conn = _get_connection()
                with conn.cursor() as cur:
                    for p in (src_prefix, tgt_prefix):
                        cur.execute("DELETE FROM items WHERE id LIKE %s", (f"{p}-%",))
                        cur.execute("DELETE FROM archive WHERE id LIKE %s", (f"{p}-%",))
                        cur.execute("DELETE FROM repos WHERE prefix = %s", (p,))
                    cur.execute("CALL DOLT_ADD('-A')")
                    cur.execute(
                        "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
                        (f"test cleanup move {src_prefix}/{tgt_prefix}", "test <test@localhost>"),
                    )
                conn.commit()
            except Exception:
                pass  # Best-effort cleanup

class TestReposRegistration:
    """The repos mapping table self-populates as boards write (bon-hatemu)."""

    def _item(self, prefix, suffix):
        return {
            "id": f"{prefix}-{suffix}",
            "type": "action",
            "title": f"repos registration test {suffix}",
            "status": "open",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "order": 1,
            "created_at": now_iso(),
            "created_by": "test",
        }

    def _repos_row(self, prefix):
        from bon.dolt import _get_connection
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM repos WHERE prefix = %s", (prefix,))
            return cur.fetchone()

    def test_save_items_registers_board(self, dolt_dir):
        tmp_path, prefix = dolt_dir
        save_items([self._item(prefix, "rega")])
        row = self._repos_row(prefix)
        assert row is not None
        assert row["repo_name"] == tmp_path.name
        assert row["origin_url"] is None  # tmp dir is not a git repo
        assert row["updated_at"]

    def test_unchanged_identity_does_not_churn(self, dolt_dir):
        tmp_path, prefix = dolt_dir
        save_items([self._item(prefix, "rega")])
        # Plant a sentinel: a save with unchanged identity must not overwrite
        # it. (Comparing timestamps would false-pass within the same second.)
        from bon.dolt import _get_connection
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE repos SET updated_at = %s WHERE prefix = %s",
                ("SENTINEL", prefix),
            )
        conn.commit()
        save_items([self._item(prefix, "rega"), self._item(prefix, "regb")])
        assert self._repos_row(prefix)["updated_at"] == "SENTINEL"

    def test_dolt_register_repo_explicit(self, dolt_dir):
        tmp_path, prefix = dolt_dir
        from bon.dolt import dolt_register_repo
        assert dolt_register_repo(prefix) is True   # first registration writes
        assert dolt_register_repo(prefix) is False  # re-run is a no-op
        assert self._repos_row(prefix)["repo_name"] == tmp_path.name

    def test_register_job_curated_and_preserved(self, dolt_dir):
        """The job column is human-curated: only an explicit --job touches it.

        The parasitic save-path registration must never clobber a curated
        value, and --job "" clears back to NULL (unassigned)."""
        tmp_path, prefix = dolt_dir
        from bon.dolt import dolt_register_repo
        assert dolt_register_repo(prefix, job="batterie") is True
        assert self._repos_row(prefix)["job"] == "batterie"
        # Same job again: no churn
        assert dolt_register_repo(prefix, job="batterie") is False
        # Parasitic save (no job argument) preserves the curated value
        save_items([self._item(prefix, "rega")])
        assert self._repos_row(prefix)["job"] == "batterie"
        # Explicit register without --job also preserves
        assert dolt_register_repo(prefix) is False
        assert self._repos_row(prefix)["job"] == "batterie"
        # --job "" clears to NULL (surfaces as unassigned)
        assert dolt_register_repo(prefix, job="") is True
        assert self._repos_row(prefix)["job"] is None
