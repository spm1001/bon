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

    def test_archive_roundtrip(self, dolt_dir):
        _, prefix = dolt_dir
        ts = now_iso()
        item = {
            "id": f"{prefix}-arc",
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
        assert any(i["id"] == f"{prefix}-arc" for i in loaded)

        # Remove from archive
        removed = remove_from_archive(f"{prefix}-arc", prefix)
        assert removed is not None
        assert removed["id"] == f"{prefix}-arc"

        # Verify removed
        loaded2 = load_archive()
        assert not any(i["id"] == f"{prefix}-arc" for i in loaded2)

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
