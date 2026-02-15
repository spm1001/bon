"""Tests for session-scoped tactical tracking.

CWD as session identity: each worktree (different directory) gets its own
tactical scope. Two sessions can have active tactical on different actions
simultaneously without conflicting.
"""
import json

import pytest
from conftest import run_arc


class TestSessionIsolation:
    """Two CWDs can have independent active tacticals."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_two_sessions_independent_tacticals(self, arc_dir_with_fixture, tmp_path):
        """Two different CWDs can each have active tactical on different actions."""
        base = arc_dir_with_fixture

        # Create a second action
        result = run_arc(
            "new", "Second action",
            "--for", "arc-aaa",
            "--why", "Test", "--what", "Test", "--done", "Test",
            cwd=base,
        )
        assert result.returncode == 0
        second_id = result.stdout.strip().replace("Created: ", "")

        # Session A (base dir): work on arc-ccc
        result = run_arc("work", "arc-ccc", "Step A1", "Step A2", cwd=base)
        assert result.returncode == 0

        # Verify session stamped
        items = _load_items(base)
        ccc = next(i for i in items if i["id"] == "arc-ccc")
        assert ccc["tactical"]["session"] == str(base)

        # Session B (tmp_path as different CWD): needs its own .bon/
        # We symlink .bon so both dirs share the same data
        arc_link = tmp_path / "session_b" / ".bon"
        arc_link.parent.mkdir()
        arc_link.symlink_to(base / ".bon")
        session_b = arc_link.parent

        result = run_arc("work", second_id, "Step B1", "Step B2", cwd=session_b)
        assert result.returncode == 0

        # Both should have active tactical
        items = _load_items(base)
        ccc = next(i for i in items if i["id"] == "arc-ccc")
        second = next(i for i in items if i["id"] == second_id)
        assert ccc["tactical"]["session"] == str(base)
        assert second["tactical"]["session"] == str(session_b)


class TestSessionScopedLookup:
    """arc step / arc show --current only find this session's tactical."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_step_scoped_to_session(self, arc_dir_with_fixture, tmp_path):
        """arc step in CWD-A does not advance CWD-B's tactical."""
        base = arc_dir_with_fixture

        # Patch fixture: set session fields to our actual tmp dirs
        session_a = tmp_path / "worktree_a"
        session_a.mkdir()
        (session_a / ".bon").symlink_to(base / ".bon")

        session_b = tmp_path / "worktree_b"
        session_b.mkdir()
        (session_b / ".bon").symlink_to(base / ".bon")

        # Rewrite items with real paths
        items = _load_items(base)
        for item in items:
            if item.get("tactical", {}).get("session") == "/worktree/a":
                item["tactical"]["session"] = str(session_a)
            elif item.get("tactical", {}).get("session") == "/worktree/b":
                item["tactical"]["session"] = str(session_b)
        _save_items(base, items)

        # Step from session A — should advance arc-alpha (session A's tactical)
        result = run_arc("step", cwd=session_a)
        assert result.returncode == 0
        assert "Alpha step" in result.stdout

        # Verify arc-bravo (session B) unchanged
        items = _load_items(base)
        bravo = next(i for i in items if i["id"] == "arc-bravo")
        assert bravo["tactical"]["current"] == 1  # Unchanged

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_show_current_scoped(self, arc_dir_with_fixture, tmp_path):
        """arc show --current only returns this session's tactical."""
        base = arc_dir_with_fixture

        session_a = tmp_path / "worktree_a"
        session_a.mkdir()
        (session_a / ".bon").symlink_to(base / ".bon")

        session_b = tmp_path / "worktree_b"
        session_b.mkdir()
        (session_b / ".bon").symlink_to(base / ".bon")

        # Rewrite items with real paths
        items = _load_items(base)
        for item in items:
            if item.get("tactical", {}).get("session") == "/worktree/a":
                item["tactical"]["session"] = str(session_a)
            elif item.get("tactical", {}).get("session") == "/worktree/b":
                item["tactical"]["session"] = str(session_b)
        _save_items(base, items)

        # Session A sees arc-alpha
        result = run_arc("show", "--current", cwd=session_a)
        assert result.returncode == 0
        assert "Action in session A" in result.stdout

        # Session B sees arc-bravo
        result = run_arc("show", "--current", cwd=session_b)
        assert result.returncode == 0
        assert "Action in session B" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_show_current_unknown_session_empty(self, arc_dir_with_fixture, tmp_path):
        """arc show --current from unrelated CWD returns nothing."""
        base = arc_dir_with_fixture

        # Don't rewrite sessions — they're /worktree/a and /worktree/b
        # Run from base which matches neither
        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_arc("show", "--current", cwd=session_c)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestCrossSessionConflict:
    """Same action claimed by different CWDs → error."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_scoped_tactical"], indirect=True)
    def test_work_cross_session_error(self, arc_dir_with_fixture, tmp_path):
        """arc work on action with active steps from another CWD → error."""
        base = arc_dir_with_fixture

        # Patch session to a known path
        items = _load_items(base)
        child = next(i for i in items if i["id"] == "arc-child")
        child["tactical"]["session"] = "/other/worktree"
        _save_items(base, items)

        # Try to work on it from base (different CWD)
        result = run_arc("work", "arc-child", "--force", "New step", cwd=base)
        assert result.returncode == 1
        assert "active steps from another worktree" in result.stderr


class TestSessionScopedClear:
    """arc work --clear only clears this session's tactical."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_clear_scoped_to_session(self, arc_dir_with_fixture, tmp_path):
        """arc work --clear in session A does not clear session B."""
        base = arc_dir_with_fixture

        session_a = tmp_path / "worktree_a"
        session_a.mkdir()
        (session_a / ".bon").symlink_to(base / ".bon")

        session_b = tmp_path / "worktree_b"
        session_b.mkdir()
        (session_b / ".bon").symlink_to(base / ".bon")

        # Rewrite items with real paths
        items = _load_items(base)
        for item in items:
            if item.get("tactical", {}).get("session") == "/worktree/a":
                item["tactical"]["session"] = str(session_a)
            elif item.get("tactical", {}).get("session") == "/worktree/b":
                item["tactical"]["session"] = str(session_b)
        _save_items(base, items)

        # Clear from session A
        result = run_arc("work", "--clear", cwd=session_a)
        assert result.returncode == 0
        assert "Cleared tactical steps from arc-alpha" in result.stdout

        # Session B's tactical still intact
        items = _load_items(base)
        bravo = next(i for i in items if i["id"] == "arc-bravo")
        assert "tactical" in bravo
        assert bravo["tactical"]["current"] == 1

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_clear_from_unrelated_session_silent(self, arc_dir_with_fixture, tmp_path):
        """arc work --clear from unrelated CWD is silent (nothing to clear)."""
        base = arc_dir_with_fixture

        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_arc("work", "--clear", cwd=session_c)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

        # Both tacticals still intact
        items = _load_items(base)
        alpha = next(i for i in items if i["id"] == "arc-alpha")
        bravo = next(i for i in items if i["id"] == "arc-bravo")
        assert "tactical" in alpha
        assert "tactical" in bravo


class TestWorkStatus:
    """arc work --status scoped to CWD."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_status_scoped(self, arc_dir_with_fixture, tmp_path):
        """arc work --status shows only this session's tactical."""
        base = arc_dir_with_fixture

        session_a = tmp_path / "worktree_a"
        session_a.mkdir()
        (session_a / ".bon").symlink_to(base / ".bon")

        session_b = tmp_path / "worktree_b"
        session_b.mkdir()
        (session_b / ".bon").symlink_to(base / ".bon")

        items = _load_items(base)
        for item in items:
            if item.get("tactical", {}).get("session") == "/worktree/a":
                item["tactical"]["session"] = str(session_a)
            elif item.get("tactical", {}).get("session") == "/worktree/b":
                item["tactical"]["session"] = str(session_b)
        _save_items(base, items)

        # Status from session A
        result = run_arc("work", "--status", cwd=session_a)
        assert result.returncode == 0
        assert "Action in session A" in result.stdout
        assert "Action in session B" not in result.stdout

        # Status from session B
        result = run_arc("work", "--status", cwd=session_b)
        assert result.returncode == 0
        assert "Action in session B" in result.stdout
        assert "Action in session A" not in result.stdout


class TestLegacyBackwardCompat:
    """Tacticals without session field (legacy) are claimable by any CWD."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_tactical_visible(self, arc_dir_with_fixture):
        """Legacy tactical (no session) is found by find_active_tactical with session."""
        result = run_arc("work", "--status", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        assert "Working on: Test action with steps" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_step_works(self, arc_dir_with_fixture):
        """arc step works on legacy unscoped tactical from any CWD."""
        result = run_arc("step", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        assert "Step three" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_show_current(self, arc_dir_with_fixture):
        """arc show --current finds legacy unscoped tactical."""
        result = run_arc("show", "--current", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        assert "Test action with steps" in result.stdout

    @pytest.mark.parametrize("arc_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_clear(self, arc_dir_with_fixture):
        """arc work --clear clears legacy unscoped tactical."""
        result = run_arc("work", "--clear", cwd=arc_dir_with_fixture)
        assert result.returncode == 0
        assert "Cleared tactical steps from arc-child" in result.stdout


class TestSessionStamping:
    """arc work stamps session field on new tacticals."""

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_stamps_session(self, arc_dir_with_fixture):
        """arc work sets tactical.session to CWD."""
        result = run_arc(
            "edit", "arc-ccc",
            "--what", "1. Step one 2. Step two",
            cwd=arc_dir_with_fixture,
        )
        assert result.returncode == 0

        result = run_arc("work", "arc-ccc", cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        items = _load_items(arc_dir_with_fixture)
        ccc = next(i for i in items if i["id"] == "arc-ccc")
        assert ccc["tactical"]["session"] == str(arc_dir_with_fixture)

    @pytest.mark.parametrize("arc_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_explicit_steps_stamps_session(self, arc_dir_with_fixture):
        """arc work with explicit steps also stamps session."""
        result = run_arc("work", "arc-ccc", "Do A", "Do B", cwd=arc_dir_with_fixture)
        assert result.returncode == 0

        items = _load_items(arc_dir_with_fixture)
        ccc = next(i for i in items if i["id"] == "arc-ccc")
        assert ccc["tactical"]["session"] == str(arc_dir_with_fixture)


# --- helpers ---

def _load_items(base_dir):
    """Load items from .arc/items.jsonl."""
    path = base_dir / ".bon" / "items.jsonl"
    items = []
    for line in path.read_text().strip().split("\n"):
        if line.strip():
            items.append(json.loads(line))
    return items


def _save_items(base_dir, items):
    """Save items to .arc/items.jsonl."""
    path = base_dir / ".bon" / "items.jsonl"
    with open(path, "w") as f:
        for item in sorted(items, key=lambda i: i.get("id", "")):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
