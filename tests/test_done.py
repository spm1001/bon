"""Tests for bon done command."""
import json

import pytest
from conftest import run_bon


class TestDoneBasic:
    """Test basic bon done behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_marks_item(self, bon_dir_with_fixture, monkeypatch):
        """bon done marks item as done with timestamp."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("done", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: bon-aaa" in result.stdout

        # Verify the item was updated
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["status"] == "done"
        assert "done_at" in item
        assert item["done_at"].endswith("Z")

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_action(self, bon_dir_with_fixture, monkeypatch):
        """Can mark an action as done."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-ccc is the open action
        result = run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: bon-ccc" in result.stdout


class TestDoneNote:
    """Test --note flag on bon done."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_with_note(self, bon_dir_with_fixture, monkeypatch):
        """bon done --note stores completion context."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("done", "bon-aaa", "--note", "Verified in production", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: bon-aaa" in result.stdout

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["done_note"] == "Verified in production"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_without_note(self, bon_dir_with_fixture, monkeypatch):
        """bon done without --note has no done_note field."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        assert "done_note" not in ccc

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_note_in_log(self, bon_dir_with_fixture, monkeypatch):
        """bon log shows note on completed items."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("done", "bon-aaa", "--note", "Shipped to prod", cwd=bon_dir_with_fixture)
        result = run_bon("log", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Shipped to prod" in result.stdout

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_note_in_show(self, bon_dir_with_fixture, monkeypatch):
        """bon show displays note on completed items."""
        monkeypatch.chdir(bon_dir_with_fixture)

        run_bon("done", "bon-aaa", "--note", "Customer confirmed fix", cwd=bon_dir_with_fixture)
        result = run_bon("show", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Note: Customer confirmed fix" in result.stdout


class TestDoneAlready:
    """Test bon done on already-done items."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_already_done(self, bon_dir_with_fixture, monkeypatch):
        """bon done on already-done item is a no-op."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb is already done
        result = run_bon("done", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Already done: bon-bbb" in result.stdout


class TestDoneUnblock:
    """Test the critical unblock behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["waiting_dependency"], indirect=True)
    def test_done_unblocks_waiters(self, bon_dir_with_fixture, monkeypatch):
        """Completing an item clears waiting_for on waiters."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb (Run tests) is waiting for bon-ccc (Security review)
        # Complete bon-ccc
        result = run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: bon-ccc" in result.stdout
        assert "Unblocked: bon-bbb" in result.stdout

        # Verify bon-bbb is now unblocked
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        bbb = next(i for i in items if i["id"] == "bon-bbb")
        assert bbb["waiting_for"] is None

    @pytest.mark.parametrize("bon_dir_with_fixture", ["all_waiting"], indirect=True)
    def test_done_unblocks_chain(self, bon_dir_with_fixture, monkeypatch):
        """Unblocking happens one level at a time."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # bon-bbb waits for "external counsel" (free text)
        # bon-ccc waits for bon-bbb
        # Complete bon-bbb
        result = run_bon("done", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Unblocked: bon-ccc" in result.stdout

        # bon-ccc is now unblocked
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        assert ccc["waiting_for"] is None


class TestDoneErrors:
    """Test bon done error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("done", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    def test_done_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("done", "bon-aaa", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestDoneClearsTactical:
    """Test that bon done clears tactical steps."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_clears_tactical_steps(self, bon_dir_with_fixture, monkeypatch):
        """bon done on action with active tactical clears them."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Set up tactical steps on bon-ccc (open action)
        run_bon("work", "bon-ccc", "step one", "step two", cwd=bon_dir_with_fixture)

        # Done it mid-tactical
        result = run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        # Verify tactical is cleared
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = [json.loads(line) for line in lines]
        ccc = next(i for i in items if i["id"] == "bon-ccc")
        assert "tactical" not in ccc

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_done_then_work_on_different_action(self, bon_dir_with_fixture, monkeypatch):
        """bon done X && bon work Y succeeds without manual --clear."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Create a second open action
        run_bon("new", "Second action", "--outcome", "bon-aaa",
                "--why", "test", "--what", "1. do thing", "--done", "done",
                cwd=bon_dir_with_fixture)

        # Set up tactical on bon-ccc, then done it
        run_bon("work", "bon-ccc", "step one", "step two", cwd=bon_dir_with_fixture)
        run_bon("done", "bon-ccc", cwd=bon_dir_with_fixture)

        # Now work on the new action — should succeed without --clear
        result = run_bon("work", "--status", cwd=bon_dir_with_fixture)
        assert "No active tactical" in result.stdout


class TestDonePrefixTolerant:
    """Test prefix-tolerant ID matching."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_done_by_suffix(self, bon_dir_with_fixture, monkeypatch):
        """Can mark done by suffix only."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("done", "aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Done: bon-aaa" in result.stdout


class TestAlreadyDoneNote:
    """bon-civelu: a --note on an already-done item attaches instead of vanishing."""

    def _seed(self, bon_dir, with_note=False):
        import json
        item = {"id": "bon-gone", "type": "action", "title": "Closed elsewhere",
                "brief": {"why": "w", "what": "x", "done": "d"}, "status": "done",
                "order": 1, "created_at": "2026-06-10T20:00:00Z", "created_by": "t",
                "done_at": "2026-06-10T20:30:00Z"}
        if with_note:
            item["done_note"] = "the original note"
        (bon_dir / ".bon" / "items.jsonl").write_text(json.dumps(item) + "\n")

    def test_note_attaches_when_absent(self, bon_dir):
        import json
        self._seed(bon_dir)
        result = run_bon("done", "bon-gone", "--note", "late attribution", cwd=bon_dir)
        assert result.returncode == 0
        assert "note attached" in result.stdout
        stored = json.loads((bon_dir / ".bon" / "items.jsonl").read_text())
        assert stored["done_note"] == "late attribution"

    def test_existing_note_not_overwritten(self, bon_dir):
        import json
        self._seed(bon_dir, with_note=True)
        result = run_bon("done", "bon-gone", "--note", "usurper", cwd=bon_dir)
        assert result.returncode == 0
        assert "note attached" not in result.stdout
        stored = json.loads((bon_dir / ".bon" / "items.jsonl").read_text())
        assert stored["done_note"] == "the original note"

    def test_discarded_note_says_so(self, bon_dir):
        """A --note that will not be stored is announced, never silently dropped
        (bon-pufezi), with the repair verb named."""
        self._seed(bon_dir, with_note=True)
        result = run_bon("done", "bon-gone", "--note", "usurper", cwd=bon_dir)
        assert result.returncode == 0
        assert "NOT stored" in result.stderr
        assert "bon edit" in result.stderr

    def test_no_note_passed_no_warning(self, bon_dir):
        """Negative control: plain re-done of a done item stays quiet."""
        self._seed(bon_dir, with_note=True)
        result = run_bon("done", "bon-gone", cwd=bon_dir)
        assert result.returncode == 0
        assert "NOT stored" not in result.stderr


class TestRecloseNote:
    """bon-pufezi: a re-close's completion context reflects the LAST close.

    The July note said DROPPED; the item was reopened and genuinely completed
    in August; bon show still reported the July note as the completion story.
    The note survives `bon reopen` (readable while deciding what to do) and
    clears at re-close unless a fresh note replaces it.
    """

    def _cycle(self, bon_dir):
        run_bon("new", "Cycled", "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir)
        import json
        item_id = json.loads(
            (bon_dir / ".bon" / "items.jsonl").read_text().strip())["id"]
        run_bon("done", item_id, "--note", "Dropped — tracked elsewhere",
                cwd=bon_dir)
        run_bon("reopen", item_id, cwd=bon_dir)
        return item_id

    def _stored(self, bon_dir):
        import json
        return json.loads((bon_dir / ".bon" / "items.jsonl").read_text().strip())

    def test_note_survives_reopen(self, bon_dir):
        """The first close's reasoning stays readable while the item is open."""
        self._cycle(bon_dir)
        assert self._stored(bon_dir)["done_note"] == "Dropped — tracked elsewhere"

    def test_reclose_without_note_clears_stale_note(self, bon_dir):
        """Re-closing with no note drops the old one rather than let it lie."""
        item_id = self._cycle(bon_dir)
        run_bon("done", item_id, cwd=bon_dir)
        assert "done_note" not in self._stored(bon_dir)

    def test_reclose_with_note_overwrites(self, bon_dir):
        """A fresh note is this close's story."""
        item_id = self._cycle(bon_dir)
        run_bon("done", item_id, "--note", "Actually completed", cwd=bon_dir)
        assert self._stored(bon_dir)["done_note"] == "Actually completed"

    def test_first_close_still_stores_note(self, bon_dir):
        """Control: the ordinary first-close path is untouched."""
        run_bon("new", "Once", "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir)
        item_id = self._stored(bon_dir)["id"]
        run_bon("done", item_id, "--note", "first and only", cwd=bon_dir)
        assert self._stored(bon_dir)["done_note"] == "first and only"
