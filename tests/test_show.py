"""Tests for bon show command."""
import json

import pytest
from conftest import run_bon


class TestShowOutcome:
    """Test bon show for outcomes."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_show_outcome_with_actions(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays outcome with all its actions."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        # Check header
        assert "○ User auth (bon-aaa)" in result.stdout
        assert "Type: outcome" in result.stdout
        assert "Status: open" in result.stdout
        assert "Created:" in result.stdout

        # Check brief
        assert "--why: New devs struggling with auth setup" in result.stdout
        assert "--what: Simplified OAuth flow" in result.stdout
        assert "--done: Setup takes < 10 minutes" in result.stdout

        # Check actions
        assert "Actions:" in result.stdout
        assert "1. ✓ Add endpoint (bon-bbb)" in result.stdout
        assert "2. ○ Add UI (bon-ccc)" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_outcome_no_actions(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays outcome without actions section when empty."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "○ User auth (bon-aaa)" in result.stdout
        assert "Actions:" not in result.stdout  # No actions section


class TestShowAction:
    """Test bon show for actions."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_show_action(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays action details."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "✓ Add endpoint (bon-bbb)" in result.stdout
        assert "Type: action" in result.stdout
        assert "Status: done" in result.stdout
        assert "Actions:" not in result.stdout  # Actions don't show nested actions

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_show_waiting_action(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays waiting status."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Waiting for: bon-ccc" in result.stdout


class TestShowErrors:
    """Test bon show error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    def test_show_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("show", "bon-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestShowCurrent:
    """Test bon show --current with active tactical steps."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_show_current_with_active_tactical(self, bon_dir_with_fixture, monkeypatch):
        """bon show --current outputs working line and tactical steps."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "--current", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Working: Test action with steps (bon-child)" in result.stdout
        # Step 1 (index 0) completed, step 2 (index 1) current, step 3 pending
        assert "✓ 1. Step one" in result.stdout
        assert "→ 2. Step two [current]" in result.stdout
        assert "3. Step three" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_show_current_no_active_tactical(self, bon_dir_with_fixture, monkeypatch):
        """bon show --current silently exits when no tactical steps active."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "--current", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert result.stdout == ""


class TestShowPrefixTolerant:
    """Test prefix-tolerant ID matching."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_show_by_suffix(self, bon_dir_with_fixture, monkeypatch):
        """Can show item by suffix only."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("show", "aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "User auth" in result.stdout


class TestShowJsonUpdatedAt:
    """updated_at is non-null in --json even for never-edited items (bon-jejuge)."""

    def test_never_edited_item_reports_updated_at_equal_created_at(self, bon_dir):
        new = run_bon(
            "new", "Fresh outcome",
            "--why", "w", "--what", "x", "--done", "d", "-q",
            cwd=bon_dir,
        )
        item_id = new.stdout.strip()

        result = run_bon("show", item_id, "--json", cwd=bon_dir)

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["created_at"], "created_at must be set on creation"
        assert data["updated_at"] == data["created_at"], (
            "a never-edited item must report updated_at == created_at, not null"
        )

    def test_edited_item_keeps_its_real_updated_at(self, bon_dir):
        new = run_bon(
            "new", "Fresh outcome",
            "--why", "w", "--what", "x", "--done", "d", "-q",
            cwd=bon_dir,
        )
        item_id = new.stdout.strip()
        run_bon("edit", item_id, "--title", "Edited title", cwd=bon_dir)

        result = run_bon("show", item_id, "--json", cwd=bon_dir)

        data = json.loads(result.stdout)
        # The edit stamps a fresh updated_at; normalization must not clobber it.
        assert data["updated_at"] >= data["created_at"]


def test_show_renders_local_time_beside_utc_stamp(bon_dir):
    """bon-dalepu/lomede: raw Z stamps beside local wall-clock sense manufactured
    phantom race reports — show renders both."""
    import json
    item = {
        "id": "bon-zzstmp", "type": "action", "title": "Stamped",
        "brief": {"why": "w", "what": "x", "done": "d"}, "status": "open",
        "parent": None, "order": 1, "created_at": "2026-08-16T21:04:32Z",
        "created_by": "test", "waiting_for": None,
    }
    (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")
    result = run_bon("show", "bon-zzstmp", cwd=bon_dir)
    assert result.returncode == 0
    import re
    assert re.search(r"Created: 2026-08-16T21:04:32Z \(\d{4}-\d{2}-\d{2} \d{2}:\d{2} local\)", result.stdout), result.stdout
