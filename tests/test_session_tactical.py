"""Tests for session-scoped tactical tracking.

CWD as session identity: each worktree (different directory) gets its own
tactical scope. Two sessions can have active tactical on different actions
simultaneously without conflicting.
"""
import json

import pytest
from conftest import run_bon


class TestSessionIsolation:
    """Two CWDs can have independent active tacticals."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_two_sessions_independent_tacticals(self, bon_dir_with_fixture, tmp_path):
        """Two different CWDs can each have active tactical on different actions."""
        base = bon_dir_with_fixture

        # Create a second action
        result = run_bon(
            "new", "Second action",
            "--for", "bon-aaa",
            "--why", "Test", "--what", "Test", "--done", "Test",
            cwd=base,
        )
        assert result.returncode == 0
        second_id = result.stdout.strip().split()[-1]

        # Session A (base dir): work on bon-ccc
        result = run_bon("work", "bon-ccc", "Step A1", "Step A2", cwd=base)
        assert result.returncode == 0

        # Verify session stamped
        items = _load_items(base)
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        assert ccc["tactical"]["session"] == str(base)

        # Session B (tmp_path as different CWD): needs its own .bon/
        # We symlink .bon so both dirs share the same data
        bon_link = tmp_path / "session_b" / ".bon"
        bon_link.parent.mkdir()
        bon_link.symlink_to(base / ".bon")
        session_b = bon_link.parent

        result = run_bon("work", second_id, "Step B1", "Step B2", cwd=session_b)
        assert result.returncode == 0

        # Both should have active tactical
        items = _load_items(base)
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        second = next(i for i in items if i["id"] == second_id)
        assert ccc["tactical"]["session"] == str(base)
        assert second["tactical"]["session"] == str(session_b)


class TestSessionScopedLookup:
    """bon step / bon show --current only find this session's tactical."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_step_scoped_to_session(self, bon_dir_with_fixture, tmp_path):
        """bon step in CWD-A does not advance CWD-B's tactical."""
        base = bon_dir_with_fixture

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

        # Step from session A — should advance bon-alpha (session A's tactical)
        result = run_bon("step", cwd=session_a)
        assert result.returncode == 0
        assert "Alpha step" in result.stdout

        # Verify bon-bravo (session B) unchanged
        items = _load_items(base)
        bravo = next(i for i in items if i["id"] == "bon-bravo")
        assert bravo["tactical"]["current"] == 1  # Unchanged

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_show_current_scoped(self, bon_dir_with_fixture, tmp_path):
        """bon show --current only returns this session's tactical."""
        base = bon_dir_with_fixture

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

        # Session A sees bon-alpha
        result = run_bon("show", "--current", cwd=session_a)
        assert result.returncode == 0
        assert "Action in session A" in result.stdout

        # Session B sees bon-bravo
        result = run_bon("show", "--current", cwd=session_b)
        assert result.returncode == 0
        assert "Action in session B" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_show_current_unknown_session_empty(self, bon_dir_with_fixture, tmp_path):
        """bon show --current from unrelated CWD returns nothing when other sessions exist."""
        base = bon_dir_with_fixture

        # Rewrite sessions to real paths so they're not treated as orphaned
        session_a = tmp_path / "worktree_a"
        session_a.mkdir()
        session_b = tmp_path / "worktree_b"
        session_b.mkdir()
        items = _load_items(base)
        for item in items:
            if item.get("tactical", {}).get("session") == "/worktree/a":
                item["tactical"]["session"] = str(session_a)
            elif item.get("tactical", {}).get("session") == "/worktree/b":
                item["tactical"]["session"] = str(session_b)
        _save_items(base, items)

        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_bon("show", "--current", cwd=session_c)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_show_current_surfaces_orphaned_tactical(self, bon_dir_with_fixture, tmp_path):
        """bon show --current hints about orphaned tacticals from non-existent sessions."""
        base = bon_dir_with_fixture

        # Sessions are /worktree/a and /worktree/b — neither exists on disk
        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_bon("show", "--current", cwd=session_c)
        assert result.returncode == 0
        assert "Orphaned tactical" in result.stdout
        assert "bon work" in result.stdout


class TestCrossSessionConflict:
    """Same action claimed by different CWDs → error."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_scoped_tactical"], indirect=True)
    def test_work_cross_session_error(self, bon_dir_with_fixture, tmp_path):
        """bon work on action with active steps from another CWD → error."""
        base = bon_dir_with_fixture

        # Patch session to a path that exists (so it's not treated as orphaned)
        other_worktree = tmp_path / "other-worktree"
        other_worktree.mkdir()
        items = _load_items(base)
        child = next(i for i in items if i["id"] == "bon-child")
        child["tactical"]["session"] = str(other_worktree)
        _save_items(base, items)

        # Try to work on it from base (different CWD)
        result = run_bon("work", "bon-child", "--force", "New step", cwd=base)
        assert result.returncode == 1
        assert "active steps from another worktree" in result.stderr


class TestSessionScopedClear:
    """bon work --clear only clears this session's tactical."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_clear_scoped_to_session(self, bon_dir_with_fixture, tmp_path):
        """bon work --clear in session A does not clear session B."""
        base = bon_dir_with_fixture

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
        result = run_bon("work", "--clear", cwd=session_a)
        assert result.returncode == 0
        assert "Cleared tactical steps from bon-alpha" in result.stdout

        # Session B's tactical still intact
        items = _load_items(base)
        bravo = next(i for i in items if i["id"] == "bon-bravo")
        assert "tactical" in bravo
        assert bravo["tactical"]["current"] == 1

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_clear_from_unrelated_session_silent(self, bon_dir_with_fixture, tmp_path):
        """bon work --clear from unrelated CWD is silent (nothing to clear)."""
        base = bon_dir_with_fixture

        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_bon("work", "--clear", cwd=session_c)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

        # Both tacticals still intact
        items = _load_items(base)
        alpha = next(i for i in items if i["id"] == "bon-alpha")
        bravo = next(i for i in items if i["id"] == "bon-bravo")
        assert "tactical" in alpha
        assert "tactical" in bravo


class TestWorkStatus:
    """bon work --status scoped to CWD."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_status_scoped(self, bon_dir_with_fixture, tmp_path):
        """bon work --status shows only this session's tactical."""
        base = bon_dir_with_fixture

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
        result = run_bon("work", "--status", cwd=session_a)
        assert result.returncode == 0
        assert "Action in session A" in result.stdout
        assert "Action in session B" not in result.stdout

        # Status from session B
        result = run_bon("work", "--status", cwd=session_b)
        assert result.returncode == 0
        assert "Action in session B" in result.stdout
        assert "Action in session A" not in result.stdout


class TestLegacyBackwardCompat:
    """Tacticals without session field (legacy) are claimable by any CWD."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_tactical_visible(self, bon_dir_with_fixture):
        """Legacy tactical (no session) is found by find_active_tactical with session."""
        result = run_bon("work", "--status", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        assert "Working on: Test action with steps" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_step_works(self, bon_dir_with_fixture):
        """bon step works on legacy unscoped tactical from any CWD."""
        result = run_bon("step", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        assert "Step three" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_show_current(self, bon_dir_with_fixture):
        """bon show --current finds legacy unscoped tactical."""
        result = run_bon("show", "--current", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        assert "Test action with steps" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_legacy_clear(self, bon_dir_with_fixture):
        """bon work --clear clears legacy unscoped tactical."""
        result = run_bon("work", "--clear", cwd=bon_dir_with_fixture)
        assert result.returncode == 0
        assert "Cleared tactical steps from bon-child" in result.stdout


class TestSessionStamping:
    """bon work stamps session field on new tacticals."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_stamps_session(self, bon_dir_with_fixture):
        """bon work sets tactical.session to CWD."""
        result = run_bon(
            "edit", "bon-ccc",
            "--what", "1. Step one 2. Step two",
            cwd=bon_dir_with_fixture,
        )
        assert result.returncode == 0

        result = run_bon("work", "bon-ccc", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        items = _load_items(bon_dir_with_fixture)
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        assert ccc["tactical"]["session"] == str(bon_dir_with_fixture)

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_explicit_steps_stamps_session(self, bon_dir_with_fixture):
        """bon work with explicit steps also stamps session."""
        result = run_bon("work", "bon-ccc", "Do A", "Do B", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        items = _load_items(bon_dir_with_fixture)
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        assert ccc["tactical"]["session"] == str(bon_dir_with_fixture)


class TestOrphanedTacticalHints:
    """Orphaned tacticals (session path gone) surface hints in step, status, show --current."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_step_hints_orphaned(self, bon_dir_with_fixture, tmp_path):
        """bon step from new CWD mentions orphaned tactical and how to re-claim."""
        base = bon_dir_with_fixture
        # Sessions /worktree/a and /worktree/b don't exist on disk
        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_bon("step", cwd=session_c)
        assert result.returncode == 1
        assert "orphaned steps" in result.stderr
        assert "bon work" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multi_session_tactical"], indirect=True)
    def test_status_hints_orphaned(self, bon_dir_with_fixture, tmp_path):
        """bon work --status from new CWD shows orphaned tactical with re-claim hint."""
        base = bon_dir_with_fixture
        session_c = tmp_path / "worktree_c"
        session_c.mkdir()
        (session_c / ".bon").symlink_to(base / ".bon")

        result = run_bon("work", "--status", cwd=session_c)
        assert result.returncode == 0
        assert "Orphaned tactical" in result.stdout
        assert "bon work" in result.stdout


# --- helpers ---

def _load_items(base_dir):
    """Load items from .bon/items.jsonl."""
    path = base_dir / ".bon" / "items.jsonl"
    items = []
    for line in path.read_text().strip().split("\n"):
        if line.strip():
            items.append(json.loads(line))
    return items


def _save_items(base_dir, items):
    """Save items to .bon/items.jsonl."""
    path = base_dir / ".bon" / "items.jsonl"
    with open(path, "w") as f:
        for item in sorted(items, key=lambda i: i.get("id", "")):
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
