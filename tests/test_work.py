"""Tests for bon work command."""
import json
import re

import pytest
from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestParseStepsFromWhat:
    """Unit tests for parse_steps_from_what."""

    def test_single_line(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("1. First 2. Second 3. Third") == ["First", "Second", "Third"]

    def test_newlines_between_steps(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("1. First\n2. Second\n3. Third") == ["First", "Second", "Third"]

    def test_newlines_within_steps_normalized(self):
        """Newlines within step text should be collapsed to spaces."""
        from bon.cli import parse_steps_from_what
        result = parse_steps_from_what("1. First step\nwith detail\n2. Second step\n3. Third")
        assert result == ["First step with detail", "Second step", "Third"]

    def test_version_numbers_not_split(self):
        """v2.0 should not be treated as step boundary."""
        from bon.cli import parse_steps_from_what
        result = parse_steps_from_what("1. Create v2.0 config 2. Test 3. Ship")
        assert result == ["Create v2.0 config", "Test", "Ship"]

    def test_paren_style_delimiters(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("1) First 2) Second 3) Third") == ["First", "Second", "Third"]

    def test_trailing_newline(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("1. First\n2. Second\n") == ["First", "Second"]

    def test_double_newlines(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("1. First\n\n2. Second\n\n3. Third") == ["First", "Second", "Third"]

    def test_no_steps_returns_none(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("Just some text with no numbers") is None

    def test_single_step(self):
        from bon.cli import parse_steps_from_what
        assert parse_steps_from_what("1. Only one step") == ["Only one step"]

    def test_preamble_text_ignored(self):
        from bon.cli import parse_steps_from_what
        result = parse_steps_from_what("Setup: 1. Config 2. Test 3. Deploy")
        assert result == ["Config", "Test", "Deploy"]

    def test_inline_step_reference_not_split(self):
        # bon-narato: "(step 3)" inside a step is a cross-reference, not a boundary
        from bon.cli import parse_steps_from_what
        result = parse_steps_from_what(
            "1. Sync dotfiles — the keychain symlink (step 3) keeps agy in NATIVE "
            "keychain mode 2. Pull repos 3. Recreate the keychain symlink 4. Verify"
        )
        assert result == [
            "Sync dotfiles — the keychain symlink (step 3) keeps agy in NATIVE keychain mode",
            "Pull repos",
            "Recreate the keychain symlink",
            "Verify",
        ]

    def test_step_reference_to_next_expected_not_split(self):
        # "step 2)" where 2 IS the next expected number still must not split
        from bon.cli import parse_steps_from_what
        result = parse_steps_from_what(
            "1. Create the config (step 2) reads it on boot 2. Wire up the reader"
        )
        assert result == [
            "Create the config (step 2) reads it on boot",
            "Wire up the reader",
        ]

    def test_out_of_sequence_number_not_split(self):
        from bon.cli import parse_steps_from_what
        result = parse_steps_from_what("1. Check ports 80 and 443) stay open 2. Deploy")
        assert result == ["Check ports 80 and 443) stay open", "Deploy"]

    def test_ten_steps_with_inline_reference(self):
        # Reconstruction of the cornichon bon-vafape --what (the original
        # item predates the Dolt era and is gone): 10 steps, inline
        # "(step 3)" in step 1, must extract to exactly 10.
        from bon.cli import parse_steps_from_what
        what = (
            "1. Sync the dotfiles — the keychain symlink (step 3) keeps agy in "
            "NATIVE keychain mode on the Mac 2. Pull all repos 3. Recreate the "
            "keychain symlink 4. Install the launchd agent 5. Verify agy auth "
            "6. Run the smoke test 7. Check tailscale status 8. Update the "
            "roster 9. Document the recipe 10. Close out the bon"
        )
        result = parse_steps_from_what(what)
        assert len(result) == 10
        assert result[0].endswith("on the Mac")
        assert result[9] == "Close out the bon"


class TestWorkParseWhat:
    """Test parsing steps from --what field."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_parses_what(self, bon_dir_with_fixture, monkeypatch):
        """bon work parses numbered steps from --what."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # First, update bon-ccc to have numbered steps in --what
        result = run_bon(
            "edit", "bon-ccc",
            "--what", "1. Add login button 2. Add redirect flow 3. Test integration",
            cwd=bon_dir_with_fixture
        )
        assert result.returncode == 0

        # Now work on it
        result = run_bon("work", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "→ 1. Add login button [current]" in result.stdout
        assert "2. Add redirect flow" in result.stdout
        assert "3. Test integration" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_parses_multiline_what(self, bon_dir_with_fixture, monkeypatch):
        """bon work correctly parses steps from multiline --what."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Set --what with embedded newlines (as Claude might produce)
        result = run_bon(
            "edit", "bon-ccc",
            "--what", "1. Add login button\n2. Add redirect flow\n3. Test integration",
            cwd=bon_dir_with_fixture
        )
        assert result.returncode == 0

        result = run_bon("work", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "→ 1. Add login button [current]" in result.stdout
        assert "2. Add redirect flow" in result.stdout
        assert "3. Test integration" in result.stdout


class TestWorkExplicitSteps:
    """Test providing explicit steps."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_explicit_steps(self, bon_dir_with_fixture, monkeypatch):
        """bon work accepts explicit steps as arguments."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon(
            "work", "bon-ccc",
            "Step A", "Step B", "Step C",
            cwd=bon_dir_with_fixture
        )

        assert result.returncode == 0
        assert "→ 1. Step A [current]" in result.stdout
        assert "2. Step B" in result.stdout
        assert "3. Step C" in result.stdout


class TestWorkProseErrors:
    """Test error when --what has no numbered steps."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_prose_what_errors(self, bon_dir_with_fixture, monkeypatch):
        """bon work errors when --what has prose without numbers."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-ccc has "Login button in header, redirect flow" - no numbers
        result = run_bon("work", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "No numbered steps" in result.stderr


class TestWorkOutcomeErrors:
    """Test error when trying to add steps to outcome."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_outcome_errors_with_children(self, bon_dir_with_fixture, monkeypatch):
        """bon work on outcome with children shows them."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "bon-aaa", "Step 1", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "is an outcome" in result.stderr
        assert "Tactical steps are for actions" in result.stderr
        assert "Did you mean one of its actions?" in result.stderr
        assert "bon-ccc" in result.stderr  # Shows child action

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_work_outcome_errors_no_children(self, bon_dir_with_fixture, monkeypatch):
        """bon work on outcome without children suggests creating one."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "bon-aaa", "Step 1", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "is an outcome" in result.stderr
        assert "No actions yet" in result.stderr
        assert "bon new" in result.stderr


class TestWorkSerialEnforcement:
    """Test serial execution constraint."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_another_active_errors(self, bon_dir_with_fixture, monkeypatch):
        """bon work errors when another action has active steps."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-child already has tactical steps in progress
        # Try to create a new action and work on it
        result = run_bon(
            "new", "Another action",
            "--for", "bon-parent",
            "--why", "Test", "--what", "Test", "--done", "Test",
            cwd=bon_dir_with_fixture
        )
        assert result.returncode == 0

        # Get the new action ID
        new_id = result.stdout.strip().split()[-1]

        # Now try to work on the new action
        result = run_bon("work", new_id, "Step 1", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "bon-child has active steps" in result.stderr


class TestWorkProgressProtection:
    """Test protection of in-progress steps."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_progress_requires_force(self, bon_dir_with_fixture, monkeypatch):
        """bon work errors when steps in progress, unless --force."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-child has tactical at current=1
        result = run_bon("work", "bon-child", "New steps", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Steps in progress" in result.stderr
        assert "--force" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_force_restarts(self, bon_dir_with_fixture, monkeypatch):
        """bon work --force restarts steps."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon(
            "work", "bon-child", "--force",
            "New step A", "New step B",
            cwd=bon_dir_with_fixture
        )

        assert result.returncode == 0
        assert "→ 1. New step A [current]" in result.stdout


class TestWorkStatus:
    """Test bon work --status."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_status_shows_current(self, bon_dir_with_fixture, monkeypatch):
        """bon work --status shows current tactical state."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "--status", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Working on: Test action with steps" in result.stdout
        assert "✓ 1. Step one" in result.stdout
        assert "→ 2. Step two [current]" in result.stdout
        assert "3. Step three" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_status_no_tactical(self, bon_dir_with_fixture, monkeypatch):
        """bon work --status when no tactical active."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "--status", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "No active tactical steps" in result.stdout


class TestWorkClear:
    """Test bon work --clear."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_clear(self, bon_dir_with_fixture, monkeypatch):
        """bon work --clear removes tactical steps."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "--clear", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Cleared tactical steps from bon-child" in result.stdout

        # Verify tactical removed
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        child = next(i for i in items if i["id"] == "bon-child")
        assert "tactical" not in child

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_clear_no_tactical(self, bon_dir_with_fixture, monkeypatch):
        """bon work --clear is silent when no tactical active."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "--clear", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert result.stdout == ""


def _write_tactical_store(tmp_path, specs):
    """Helper: create a bon dir with actions in given tactical states.

    specs: list of (item_id, current, session) — session None means unscoped,
    current None means no tactical at all.
    """
    bon_dir = tmp_path / ".bon"
    bon_dir.mkdir()
    (bon_dir / "prefix").write_text("bon")
    lines = []
    for item_id, current, session in specs:
        item = {
            "id": item_id,
            "type": "action",
            "title": f"Action {item_id}",
            "brief": {"why": "Testing", "what": "1. Step one 2. Step two 3. Step three", "done": "Done"},
            "status": "open",
            "parent": None,
            "order": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "test",
            "waiting_for": None,
        }
        if current is not None:
            tactical = {"steps": ["Step one", "Step two", "Step three"], "current": current}
            if session is not None:
                tactical["session"] = session
            item["tactical"] = tactical
        lines.append(json.dumps(item))
    (bon_dir / "items.jsonl").write_text("\n".join(lines) + "\n")


def _load_store(tmp_path):
    """Helper: read items.jsonl back as {id: item}."""
    lines = (tmp_path / ".bon" / "items.jsonl").read_text().strip().split("\n")
    return {json.loads(line)["id"]: json.loads(line) for line in lines}


class TestWorkClearFinished:
    """--clear must reach a finished (--no-complete) tactical — the bon-rucape zombie.

    A tactical left at current == len(steps) via `bon step --no-complete` is
    visible to --status and the prompt hook but was invisible to --clear
    (silent no-op) and the serial-claim guard. --clear gains the same
    finished-tactical fallback --status already has.
    """

    def test_clear_reaches_finished_tactical(self, tmp_path, monkeypatch):
        """Bare --clear releases a finished --no-complete tactical (rucape's bug)."""
        import os
        session = os.path.realpath(str(tmp_path))
        _write_tactical_store(tmp_path, [("bon-zombie", 3, session)])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", cwd=tmp_path)

        assert result.returncode == 0
        assert "Cleared tactical steps from bon-zombie" in result.stdout
        store = _load_store(tmp_path)
        assert "tactical" not in store["bon-zombie"]
        assert store["bon-zombie"]["updated_by"] == "cleared"

    def test_clear_prefers_active_over_finished(self, tmp_path, monkeypatch):
        """With both an active and a finished tactical, bare --clear takes the active one."""
        import os
        session = os.path.realpath(str(tmp_path))
        _write_tactical_store(tmp_path, [("bon-live", 1, session), ("bon-zombie", 3, session)])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", cwd=tmp_path)

        assert result.returncode == 0
        assert "Cleared tactical steps from bon-live" in result.stdout
        store = _load_store(tmp_path)
        assert "tactical" not in store["bon-live"]
        assert "tactical" in store["bon-zombie"]


class TestWorkClearTargeted:
    """bon work --clear ID clears a specific item's tactical."""

    def test_clear_targeted_leaves_active_claim_alone(self, tmp_path, monkeypatch):
        """--clear ID clears that item, not the session's active claim."""
        import os
        session = os.path.realpath(str(tmp_path))
        _write_tactical_store(tmp_path, [("bon-live", 1, session), ("bon-zombie", 3, session)])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", "bon-zombie", cwd=tmp_path)

        assert result.returncode == 0
        assert "Cleared tactical steps from bon-zombie" in result.stdout
        store = _load_store(tmp_path)
        assert "tactical" not in store["bon-zombie"]
        assert "tactical" in store["bon-live"]

    def test_clear_targeted_flag_after_id(self, tmp_path, monkeypatch):
        """bon work ID --clear works too (REMAINDER swallows trailing flags)."""
        import os
        session = os.path.realpath(str(tmp_path))
        _write_tactical_store(tmp_path, [("bon-zombie", 3, session)])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "bon-zombie", "--clear", cwd=tmp_path)

        assert result.returncode == 0
        assert "Cleared tactical steps from bon-zombie" in result.stdout
        store = _load_store(tmp_path)
        assert "tactical" not in store["bon-zombie"]

    def test_clear_targeted_other_session_refuses(self, tmp_path, monkeypatch):
        """--clear ID refuses another session's tactical without --force."""
        _write_tactical_store(tmp_path, [("bon-other", 1, "host:/some/other/repo")])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", "bon-other", cwd=tmp_path)

        assert result.returncode == 1
        assert "another session" in result.stderr
        assert "--force" in result.stderr
        store = _load_store(tmp_path)
        assert "tactical" in store["bon-other"]

    def test_clear_targeted_force_overrides(self, tmp_path, monkeypatch):
        """--clear ID --force clears another session's tactical."""
        _write_tactical_store(tmp_path, [("bon-other", 1, "host:/some/other/repo")])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", "bon-other", "--force", cwd=tmp_path)

        assert result.returncode == 0
        assert "Cleared tactical steps from bon-other" in result.stdout
        store = _load_store(tmp_path)
        assert "tactical" not in store["bon-other"]

    def test_clear_targeted_not_found(self, tmp_path, monkeypatch):
        """--clear ID errors on unknown ID."""
        _write_tactical_store(tmp_path, [("bon-zombie", 3, None)])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", "bon-nonexistent", cwd=tmp_path)

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_clear_targeted_no_tactical_silent(self, tmp_path, monkeypatch):
        """--clear ID is silent when the item has no tactical."""
        _write_tactical_store(tmp_path, [("bon-bare", None, None)])
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "--clear", "bon-bare", cwd=tmp_path)

        assert result.returncode == 0
        assert result.stdout == ""


class TestWorkDoneAction:
    """Test errors on done actions."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_done_action_errors(self, bon_dir_with_fixture, monkeypatch):
        """bon work errors on already-done actions."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is done
        result = run_bon("work", "bon-bbb", "Step 1", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "already complete" in result.stderr


class TestWorkErrors:
    """Test various error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_not_found(self, bon_dir_with_fixture, monkeypatch):
        """bon work errors when item not found."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("work", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_work_not_initialized(self, tmp_path, monkeypatch):
        """bon work errors when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "bon-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr

    def test_work_no_args(self, bon_dir, monkeypatch):
        """bon work with no args errors."""
        monkeypatch.chdir(bon_dir)

        result = run_bon("work", cwd=bon_dir)

        assert result.returncode == 1
        assert "Usage:" in result.stderr


class TestWorkUpdatedAt:
    """Verify work sets updated_at timestamp."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_work_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """bon work sets updated_at on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("work", "bon-ccc", "Step A", "Step B", cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        ccc = json.loads(lines[2])
        assert "updated_at" in ccc
        assert ISO_RE.match(ccc["updated_at"])

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_tactical"], indirect=True)
    def test_work_clear_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """bon work --clear sets updated_at on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("work", "--clear", cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        child = next(json.loads(line) for line in lines if json.loads(line)["id"] == "bon-child")
        assert "updated_at" in child
        assert ISO_RE.match(child["updated_at"])


def _write_item_with_session(tmp_path, session_path, current=1):
    """Helper: create a bon dir with an action whose tactical points to session_path."""
    bon_dir = tmp_path / ".bon"
    bon_dir.mkdir()
    (bon_dir / "prefix").write_text("bon")
    item = {
        "id": "bon-child",
        "type": "action",
        "title": "Test action with steps",
        "brief": {"why": "Testing", "what": "1. Step one 2. Step two 3. Step three", "done": "Done"},
        "status": "open",
        "parent": None,
        "order": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "created_by": "test",
        "waiting_for": None,
        "tactical": {
            "steps": ["Step one", "Step two", "Step three"],
            "current": current,
            "session": session_path,
        },
    }
    (bon_dir / "items.jsonl").write_text(json.dumps(item) + "\n")


class TestWorkOrphanedSession:
    """Test re-claiming tactical steps after directory rename."""

    def test_reclaim_orphaned_preserves_progress(self, tmp_path, monkeypatch):
        """bon work re-claims tactical from non-existent session, preserving step progress."""
        _write_item_with_session(tmp_path, "/nonexistent/old/repo", current=1)
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "bon-child", cwd=tmp_path)

        assert result.returncode == 0
        assert "Re-claimed" in result.stdout
        assert "directory no longer exists" in result.stdout
        # Step progress preserved — still at step 2
        assert "✓ 1. Step one" in result.stdout
        assert "→ 2. Step two [current]" in result.stdout
        assert "3. Step three" in result.stdout

    def test_reclaim_updates_session_in_storage(self, tmp_path, monkeypatch):
        """Re-claim updates tactical.session to new CWD on disk."""
        _write_item_with_session(tmp_path, "/nonexistent/old/repo", current=1)
        monkeypatch.chdir(tmp_path)

        run_bon("work", "bon-child", cwd=tmp_path)

        lines = (tmp_path / ".bon" / "items.jsonl").read_text().strip().split("\n")
        item = json.loads(lines[0])
        import os
        assert item["tactical"]["session"] == os.path.realpath(str(tmp_path))
        assert item["tactical"]["current"] == 1  # preserved

    def test_existing_session_still_errors(self, tmp_path, monkeypatch):
        """When other session path exists on disk, cross-session conflict still errors."""
        other_worktree = tmp_path / "other-worktree"
        other_worktree.mkdir()
        _write_item_with_session(tmp_path, str(other_worktree), current=1)
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "bon-child", cwd=tmp_path)

        assert result.returncode == 1
        assert "active steps from another worktree" in result.stderr

    def test_reclaim_at_step_zero(self, tmp_path, monkeypatch):
        """Re-claim works even when orphaned tactical is at step 0."""
        _write_item_with_session(tmp_path, "/nonexistent/old/repo", current=0)
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "bon-child", cwd=tmp_path)

        assert result.returncode == 0
        assert "Re-claimed" in result.stdout
        assert "→ 1. Step one [current]" in result.stdout

    def test_reclaim_sets_updated_by_reclaimed(self, tmp_path, monkeypatch):
        """Re-claim sets updated_by to 'reclaimed' for audit trail."""
        _write_item_with_session(tmp_path, "/nonexistent/old/repo", current=1)
        monkeypatch.chdir(tmp_path)

        run_bon("work", "bon-child", cwd=tmp_path)

        lines = (tmp_path / ".bon" / "items.jsonl").read_text().strip().split("\n")
        item = json.loads(lines[0])
        assert item["updated_by"] == "reclaimed"

    def test_force_on_orphaned_restarts(self, tmp_path, monkeypatch):
        """--force on orphaned tactical restarts from scratch (doesn't preserve)."""
        _write_item_with_session(tmp_path, "/nonexistent/old/repo", current=2)
        monkeypatch.chdir(tmp_path)

        result = run_bon("work", "bon-child", "--force", "Fresh A", "Fresh B", cwd=tmp_path)

        assert result.returncode == 0
        # Restarted, not re-claimed
        assert "Re-claimed" not in result.stdout
        assert "→ 1. Fresh A [current]" in result.stdout
        assert "2. Fresh B" in result.stdout


# --- --release: hand back a claim, keep the progress (bon-kewimu) ----------

def _board(bon_dir) -> dict:
    text = (bon_dir / ".bon" / "items.jsonl").read_text().strip()
    return {i["id"]: i for i in (json.loads(ln) for ln in text.splitlines() if ln)}


def _make_action(bon_dir, title: str, steps: str) -> str:
    payload = json.dumps({
        "type": "action", "title": title,
        "brief": {"why": "w", "what": steps, "done": "d"},
    })
    result = run_bon("new", "-q", cwd=bon_dir, input=payload)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TestWorkRelease:
    """A tactical can be parked on purpose without losing its progress.

    bon-jagoha sat at step 4 of 6 waiting for a scheduled review ceremony.
    The claim is directory-keyed and serially enforced, so it refused every
    other `bon work` in that repo — and all three escapes destroyed the
    progress: done would be a lie, `bon wait` silently discards tactical,
    `--clear` pops it. `bon someday` refuses outright on an active tactical,
    so the parking verb was the one thing that could not help.
    """

    def test_release_keeps_steps_and_position(self, bon_dir):
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta 3. gamma 4. delta")
        run_bon("work", a, cwd=bon_dir)
        run_bon("step", cwd=bon_dir)
        run_bon("step", cwd=bon_dir)

        result = run_bon("work", "--release", cwd=bon_dir)
        assert result.returncode == 0, result.stderr

        tactical = _board(bon_dir)[a]["tactical"]
        assert tactical["released"] is True
        assert tactical["current"] == 2
        assert tactical["steps"] == ["alpha", "beta", "gamma", "delta"]
        assert _board(bon_dir)[a]["updated_by"] == "released"

    def test_release_frees_the_session_to_claim_another_action(self, bon_dir):
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        b = _make_action(bon_dir, "Other job", "1. one 2. two")
        run_bon("work", a, cwd=bon_dir)

        blocked = run_bon("work", b, cwd=bon_dir)
        assert blocked.returncode == 1
        assert "--release" in blocked.stderr, "the block must name the non-destructive escape"

        run_bon("work", "--release", cwd=bon_dir)
        freed = run_bon("work", b, cwd=bon_dir)
        assert freed.returncode == 0, freed.stderr

    def test_released_tactical_is_not_injected_into_prompts(self, bon_dir):
        """`bon show --current` feeds the UserPromptSubmit hook."""
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)
        assert "Working" in run_bon("show", "--current", cwd=bon_dir).stdout

        run_bon("work", "--release", cwd=bon_dir)
        assert run_bon("show", "--current", cwd=bon_dir).stdout.strip() == ""

    def test_resume_needs_no_force_and_keeps_progress(self, bon_dir):
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta 3. gamma")
        run_bon("work", a, cwd=bon_dir)
        run_bon("step", cwd=bon_dir)
        run_bon("work", "--release", cwd=bon_dir)

        result = run_bon("work", a, cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert "Resumed" in result.stdout

        item = _board(bon_dir)[a]
        assert item["tactical"]["current"] == 1, "resume must not restart at step 1"
        assert "released" not in item["tactical"]
        assert item["updated_by"] == "reclaimed"

    def test_status_reports_a_released_tactical(self, bon_dir):
        """Silence here would hide deliberately parked work."""
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)
        run_bon("work", "--release", cwd=bon_dir)

        result = run_bon("work", "--status", cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert "Released tactical" in result.stdout
        assert a in result.stdout
        assert "Resume with" in result.stdout

    def test_step_after_release_reports_nothing_in_progress(self, bon_dir):
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)
        run_bon("work", "--release", cwd=bon_dir)

        result = run_bon("step", cwd=bon_dir)
        assert result.returncode == 1
        assert "No steps in progress" in result.stderr

    def test_release_by_explicit_id(self, bon_dir):
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)

        result = run_bon("work", "--release", a, cwd=bon_dir)
        assert result.returncode == 0, result.stderr
        assert _board(bon_dir)[a]["tactical"]["released"] is True

    def test_release_is_idempotent(self, bon_dir):
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)
        run_bon("work", "--release", cwd=bon_dir)

        result = run_bon("work", "--release", a, cwd=bon_dir)
        assert result.returncode == 0
        assert "Already released" in result.stdout

    def test_release_with_nothing_claimed_says_so(self, bon_dir):
        _make_action(bon_dir, "Unclaimed", "1. alpha")
        result = run_bon("work", "--release", cwd=bon_dir)
        assert result.returncode == 1
        assert "No tactical claim" in result.stderr

    def test_clear_still_discards(self, bon_dir):
        """--release and --clear are a pair; --clear keeps its old meaning."""
        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)
        run_bon("step", cwd=bon_dir)

        run_bon("work", "--clear", cwd=bon_dir)
        assert "tactical" not in _board(bon_dir)[a]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["action_with_scoped_tactical"], indirect=True)
    def test_releasing_another_sessions_claim_needs_force(self, bon_dir_with_fixture):
        result = run_bon("work", "--release", "bon-child", cwd=bon_dir_with_fixture)
        assert result.returncode == 1
        assert "belongs to another session" in result.stderr

        forced = run_bon("work", "--release", "bon-child", "--force", cwd=bon_dir_with_fixture)
        assert forced.returncode == 0, forced.stderr
        item = _board(bon_dir_with_fixture)["bon-child"]
        assert item["tactical"]["released"] is True
        assert item["tactical"]["current"] == 1, "another session's progress must survive too"


class TestReleaseReaderParity:
    """The raw-JSONL readers must agree with the CLI about what is current.

    Both bypass storage.py — bon-read.sh serves no-CLI surfaces and
    bon-tactical.sh falls back to raw JSONL when bon is not on PATH — so each
    needs the released check independently. Blast radius lives in consumers.
    """

    def test_bon_read_sh_current_is_silent_after_release(self, bon_dir):
        import subprocess
        from pathlib import Path

        a = _make_action(bon_dir, "Long job", "1. alpha 2. beta")
        run_bon("work", a, cwd=bon_dir)

        script = Path(__file__).parent.parent / "scripts" / "bon-read.sh"
        before = subprocess.run(["bash", str(script), "current"], cwd=bon_dir,
                                capture_output=True, text=True)
        assert "Working" in before.stdout

        run_bon("work", "--release", cwd=bon_dir)
        after = subprocess.run(["bash", str(script), "current"], cwd=bon_dir,
                               capture_output=True, text=True)
        assert after.stdout.strip() == "", "a released tactical is not current work"


class TestOrientationBreadcrumb:
    """bon work re-declares the statusline orientation breadcrumb (bon-monevu).

    Contract shared with the open skill's step 3: ~/.claude/state/oriented/
    <CLAUDE_CODE_SESSION_ID> holds one line, "<CLAUDE_PID> <board root>".
    /open writes it for the repo oriented on; the draw-down rewrites it for the
    board claimed, because that is where a session commits to work.
    """

    @staticmethod
    def _env(home, **extra):
        import os
        env = os.environ.copy()
        for var in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID", "CLAUDE_CODE_CHILD_SESSION"):
            env.pop(var, None)
        env["HOME"] = str(home)
        env.update(extra)
        return env

    @staticmethod
    def _crumb(home, sid):
        return home / ".claude" / "state" / "oriented" / sid

    def test_claim_writes_board_root_not_cwd(self, bon_dir, tmp_path):
        import os
        home = tmp_path / "home"; home.mkdir()
        a = _make_action(bon_dir, "Claimed", "1. alpha 2. beta")
        sub = bon_dir / "src"; sub.mkdir()
        env = self._env(home, CLAUDE_CODE_SESSION_ID="sess-claim", CLAUDE_PID="4242")

        result = run_bon("work", a, cwd=sub, env=env)

        assert result.returncode == 0, result.stderr
        crumb = self._crumb(home, "sess-claim")
        assert crumb.read_text() == f"4242 {os.path.realpath(bon_dir)}\n"

    def test_no_harness_env_writes_nothing(self, bon_dir, tmp_path):
        home = tmp_path / "home"; home.mkdir()
        a = _make_action(bon_dir, "Bare shell", "1. alpha 2. beta")

        result = run_bon("work", a, cwd=bon_dir, env=self._env(home))

        assert result.returncode == 0, result.stderr
        assert not (home / ".claude").exists()

    def test_child_session_skips_the_write(self, bon_dir, tmp_path):
        """A dispatched worker inherits its parent's session id and pid; its
        write would overwrite the parent's breadcrumb with a token that passes
        every liveness check. Skipping is the safe direction."""
        home = tmp_path / "home"; home.mkdir()
        a = _make_action(bon_dir, "Worker", "1. alpha 2. beta")
        env = self._env(home, CLAUDE_CODE_SESSION_ID="sess-parent", CLAUDE_PID="4242",
                        CLAUDE_CODE_CHILD_SESSION="1")

        result = run_bon("work", a, cwd=bon_dir, env=env)

        assert result.returncode == 0, result.stderr
        assert not self._crumb(home, "sess-parent").exists()

    def test_status_release_clear_do_not_write(self, bon_dir, tmp_path):
        home = tmp_path / "home"; home.mkdir()
        a = _make_action(bon_dir, "Read-only verbs", "1. alpha 2. beta")
        env = self._env(home, CLAUDE_CODE_SESSION_ID="sess-ro", CLAUDE_PID="4242")

        assert run_bon("work", "--status", cwd=bon_dir, env=env).returncode == 0
        assert not self._crumb(home, "sess-ro").exists()

        run_bon("work", a, cwd=bon_dir, env=self._env(home))     # claim without identity
        assert run_bon("work", "--release", cwd=bon_dir, env=env).returncode == 0
        assert run_bon("work", "--clear", a, cwd=bon_dir, env=env).returncode == 0
        assert not self._crumb(home, "sess-ro").exists()

    def test_resume_after_release_rewrites(self, bon_dir, tmp_path):
        """Resuming a released tactical is a fresh commitment to the board."""
        import os
        home = tmp_path / "home"; home.mkdir()
        a = _make_action(bon_dir, "Resumed", "1. alpha 2. beta")
        env = self._env(home, CLAUDE_CODE_SESSION_ID="sess-resume", CLAUDE_PID="4242")
        run_bon("work", a, cwd=bon_dir, env=env)
        crumb = self._crumb(home, "sess-resume")
        crumb.write_text("4242 /somewhere/else\n")
        run_bon("work", "--release", cwd=bon_dir, env=env)

        result = run_bon("work", a, cwd=bon_dir, env=env)

        assert result.returncode == 0, result.stderr
        assert "Resumed" in result.stdout
        assert crumb.read_text() == f"4242 {os.path.realpath(bon_dir)}\n"

    def test_write_failure_does_not_fail_the_claim(self, bon_dir, tmp_path):
        """The breadcrumb is advisory: an unwritable HOME costs one stderr line,
        never the claim — and the line says why it fired."""
        blocker = tmp_path / "blocker"; blocker.write_text("not a directory")
        a = _make_action(bon_dir, "Unwritable", "1. alpha 2. beta")
        env = self._env(blocker / "home", CLAUDE_CODE_SESSION_ID="sess-fail", CLAUDE_PID="4242")

        result = run_bon("work", a, cwd=bon_dir, env=env)

        assert result.returncode == 0, result.stderr
        assert "[current]" in result.stdout
        assert "breadcrumb not written" in result.stderr

    def test_session_id_cannot_escape_the_state_dir(self, bon_dir, tmp_path):
        home = tmp_path / "home"; home.mkdir()
        a = _make_action(bon_dir, "Traversal", "1. alpha 2. beta")
        env = self._env(home, CLAUDE_CODE_SESSION_ID="../escaped", CLAUDE_PID="4242")

        result = run_bon("work", a, cwd=bon_dir, env=env)

        assert result.returncode == 0, result.stderr
        assert not (home / ".claude" / "state" / "escaped").exists()
        assert not (home / ".claude" / "state" / "oriented").exists()
