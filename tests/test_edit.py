"""Tests for bon edit command (flag-based, non-interactive)."""
import json
import re

import pytest
from conftest import run_bon

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestEditBasic:
    """Test basic bon edit behavior."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_title(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --title changes title."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--title", "New Title", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        assert "Updated: bon-aaa" in result.stdout

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_why(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --why changes brief.why."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--why", "New reason", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["why"] == "New reason"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_what(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --what changes brief.what."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--what", "New deliverable", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["what"] == "New deliverable"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_brief_done(self, bon_dir_with_fixture, monkeypatch):
        """bon edit --done changes brief.done."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--done", "New criteria", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["brief"]["done"] == "New criteria"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_multiple_fields(self, bon_dir_with_fixture, monkeypatch):
        """bon edit can change multiple fields at once."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa",
                        "--title", "New Title",
                        "--why", "New reason",
                        "--what", "New deliverable",
                        cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert item["title"] == "New Title"
        assert item["brief"]["why"] == "New reason"
        assert item["brief"]["what"] == "New deliverable"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_requires_flag(self, bon_dir_with_fixture, monkeypatch):
        """Edit with no flags is an error."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "At least one edit flag required" in result.stderr


class TestEditValidation:
    """Test bon edit validation."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Cannot set parent to non-existent ID."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-ccc", "--parent", "bon-nonexistent", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent 'bon-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_edit_parent_must_be_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Cannot set parent to an action."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-ccc is an action, try to set its parent to bon-bbb (also an action)

        result = run_bon("edit", "bon-ccc", "--parent", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Parent must be an outcome" in result.stderr


class TestEditReorder:
    """Test bon edit reordering."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_outcomes(self, bon_dir_with_fixture, monkeypatch):
        """Changing order shifts siblings."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-aaa has order 1, bon-bbb has order 2
        # Move bon-bbb to order 1

        result = run_bon("edit", "bon-bbb", "--order", "1", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-bbb should now be order 1
        assert items["bon-bbb"]["order"] == 1
        # bon-aaa should have shifted to order 2
        assert items["bon-aaa"]["order"] == 2

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_edit_reorder_move_down(self, bon_dir_with_fixture, monkeypatch):
        """Moving order down shifts siblings up."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-aaa has order 1, bon-bbb has order 2
        # Move bon-aaa to order 2 (moving DOWN)

        result = run_bon("edit", "bon-aaa", "--order", "2", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-aaa should now be order 2
        assert items["bon-aaa"]["order"] == 2
        # bon-bbb should have shifted to order 1
        assert items["bon-bbb"]["order"] == 1


class TestEditReparent:
    """Test bon edit reparenting."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_action_to_different_outcome(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting action moves it to new outcome at end."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-ccc is under bon-aaa, move it to bon-bbb

        result = run_bon("edit", "bon-ccc", "--parent", "bon-bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-ccc should now be under bon-bbb
        assert items["bon-ccc"]["parent"] == "bon-bbb"
        # bon-ccc should be at order 2 (after bon-ddd which is at order 1)
        assert items["bon-ccc"]["order"] == 2

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_resolves_short_id(self, bon_dir_with_fixture, monkeypatch):
        """--parent accepts a short ID and stores the canonical full ID."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bbb (without bon- prefix) should resolve to bon-bbb on storage

        result = run_bon("edit", "bon-ccc", "--parent", "bbb", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # Stored parent must be the canonical "bon-bbb", not the short "bbb"
        assert items["bon-ccc"]["parent"] == "bon-bbb"

        # And the hierarchy should render the reparented item correctly
        list_result = run_bon("list", cwd=bon_dir_with_fixture)
        assert list_result.returncode == 0
        # bon-ccc should appear under bon-bbb in the rendered hierarchy
        # (format_hierarchical does exact-match against parent ID, so a short-form
        # storage would orphan it)
        bbb_idx = list_result.stdout.find("bon-bbb")
        ccc_idx = list_result.stdout.find("bon-ccc")
        assert bbb_idx >= 0 and ccc_idx > bbb_idx, \
            f"bon-ccc should appear under bon-bbb in hierarchy:\n{list_result.stdout}"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_closes_gap_in_old_parent(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting closes the gap left in old parent's ordering."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # First, create a second outcome to reparent to
        run_bon("new", "Second outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        # Get the new outcome's ID
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        new_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Second outcome":
                new_outcome_id = item["id"]
                break

        # Now create another action under bon-aaa to have order 3
        run_bon("new", "Third action",
                "--for", "bon-aaa",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        # Verify setup: bon-bbb (order 1), bon-ccc (order 2), new action (order 3)
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        actions_under_aaa = [json.loads(line) for line in lines
                           if json.loads(line).get("parent") == "bon-aaa"]
        assert len(actions_under_aaa) == 3

        # Now reparent bon-ccc (order 2) to the new outcome
        result = run_bon("edit", "bon-ccc", "--parent", new_outcome_id, cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        # Check that the third action (was order 3) is now order 2
        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        third_action = [i for i in items.values()
                       if i.get("parent") == "bon-aaa" and i["title"] == "Third action"][0]
        assert third_action["order"] == 2  # Gap closed

    @pytest.mark.parametrize("bon_dir_with_fixture", ["multiple_outcomes"], indirect=True)
    def test_reparent_to_outcome_with_no_actions(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting to outcome with no actions sets order to 1."""
        monkeypatch.chdir(bon_dir_with_fixture)

        # Create a third outcome with no actions
        run_bon("new", "Empty outcome",
                "--why", "w", "--what", "x", "--done", "d",
                cwd=bon_dir_with_fixture)

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        empty_outcome_id = None
        for line in lines:
            item = json.loads(line)
            if item["title"] == "Empty outcome":
                empty_outcome_id = item["id"]
                break

        # Reparent bon-ccc to the empty outcome
        result = run_bon("edit", "bon-ccc", "--parent", empty_outcome_id, cwd=bon_dir_with_fixture)
        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        assert items["bon-ccc"]["parent"] == empty_outcome_id
        assert items["bon-ccc"]["order"] == 1

    @pytest.mark.parametrize("bon_dir_with_fixture", ["outcome_with_actions"], indirect=True)
    def test_reparent_to_none_makes_standalone(self, bon_dir_with_fixture, monkeypatch):
        """Reparenting to 'none' makes action standalone."""
        monkeypatch.chdir(bon_dir_with_fixture)
        # bon-ccc is under bon-aaa

        result = run_bon("edit", "bon-ccc", "--parent", "none", cwd=bon_dir_with_fixture)

        assert result.returncode == 0

        lines = (bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip().split("\n")
        items = {json.loads(line)["id"]: json.loads(line) for line in lines}

        # bon-ccc should now be standalone (no parent)
        assert items["bon-ccc"].get("parent") is None


class TestEditErrors:
    """Test bon edit error cases."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_not_found(self, bon_dir_with_fixture, monkeypatch):
        """Error when item doesn't exist."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-nonexistent", "--title", "X", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Item 'bon-nonexistent' not found" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_outcome_cannot_have_parent(self, bon_dir_with_fixture, monkeypatch):
        """Error when trying to set parent on outcome."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--parent", "something", cwd=bon_dir_with_fixture)

        assert result.returncode == 1
        assert "Cannot set --outcome on an outcome" in result.stderr

    def test_edit_not_initialized(self, tmp_path, monkeypatch):
        """Error when not initialized."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("edit", "bon-aaa", "--title", "X", cwd=tmp_path)

        assert result.returncode == 1
        assert "Not initialized" in result.stderr


class TestEditUpdatedAt:
    """Verify edit sets updated_at timestamp."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_edit_sets_updated_at(self, bon_dir_with_fixture, monkeypatch):
        """bon edit sets updated_at on the item."""
        monkeypatch.chdir(bon_dir_with_fixture)

        result = run_bon("edit", "bon-aaa", "--title", "New Title", cwd=bon_dir_with_fixture)

        assert result.returncode == 0
        item = json.loads((bon_dir_with_fixture / ".bon" / "items.jsonl").read_text().strip())
        assert "updated_at" in item
        assert ISO_RE.match(item["updated_at"])


# --- JSON on stdin (bon-cefisu) --------------------------------------------

def _items(bon_dir) -> dict:
    """Every item in the board, keyed by id."""
    text = (bon_dir / ".bon" / "items.jsonl").read_text().strip()
    return {i["id"]: i for i in (json.loads(ln) for ln in text.splitlines() if ln)}


# Nested quotes, a backtick command substitution, $VAR, a newline and a
# trailing backslash — the content that mangles silently through flags.
# infra's iw-kaliwu brief is the real instance behind this shape.
HOSTILE = (
    'Run `curl -H "Content-Type: application/json" -d \'{"q":"$VAR"}\' https://x/api`\n'
    "then check $HOME/.config — 'single' and \"double\" quotes, a backtick ` "
    "and a $dollar.\nTrailing backslash: \\\\"
)


class TestEditJsonStdin:
    """bon edit reads JSON from a pipe, so shell quoting can't mangle a brief.

    bon new got this path because flag quoting silently corrupts technical
    content; edit had the identical exposure and no escape hatch. The failure
    is invisible — a mangled field looks exactly like an edited one.
    """

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_piped_json_needs_no_flag(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"how": "Use Redis locks"}')
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir_with_fixture)["bon-aaa"]["brief"]["how"] == "Use Redis locks"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_hostile_content_survives_byte_identical(self, bon_dir_with_fixture):
        """The done criterion: quotes, backticks and a shell variable round-trip."""
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input=json.dumps({"how": HOSTILE}))
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir_with_fixture)["bon-aaa"]["brief"]["how"] == HOSTILE

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_brief_fields_accepted_nested(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"brief": {"why": "nested reason"}}')
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir_with_fixture)["bon-aaa"]["brief"]["why"] == "nested reason"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_brief_fields_accepted_flat(self, bon_dir_with_fixture):
        """A flat key must apply, not be silently dropped.

        Claude's prior is item["why"] over item["brief"]["why"]. Ignoring the
        flat form would apply nothing and still print "Updated" — a no-op
        wearing a success message, which is worse than any error.
        """
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"why": "flat reason"}')
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir_with_fixture)["bon-aaa"]["brief"]["why"] == "flat reason"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_absent_keys_are_left_alone(self, bon_dir_with_fixture):
        before = _items(bon_dir_with_fixture)["bon-aaa"]
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"how": "only this"}')
        assert result.returncode == 0, result.stderr
        after = _items(bon_dir_with_fixture)["bon-aaa"]
        assert after["brief"]["why"] == before["brief"]["why"]
        assert after["brief"]["what"] == before["brief"]["what"]
        assert after["brief"]["done"] == before["brief"]["done"]
        assert after["title"] == before["title"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_title_and_order_via_json(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"title": "Renamed", "order": 3}')
        assert result.returncode == 0, result.stderr
        item = _items(bon_dir_with_fixture)["bon-aaa"]
        assert item["title"] == "Renamed"
        assert item["order"] == 3

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_empty_how_clears_the_field(self, bon_dir_with_fixture):
        run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture, input='{"how": "temp"}')
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture, input='{"how": ""}')
        assert result.returncode == 0, result.stderr
        assert "how" not in _items(bon_dir_with_fixture)["bon-aaa"]["brief"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_flags_take_the_flag_path_even_with_a_pipe(self, bon_dir_with_fixture):
        """A flag means the caller chose flags; stdin must not be consumed."""
        result = run_bon("edit", "bon-aaa", "--title", "By flag",
                         cwd=bon_dir_with_fixture, input='{"why": "ignored"}')
        assert result.returncode == 0, result.stderr
        item = _items(bon_dir_with_fixture)["bon-aaa"]
        assert item["title"] == "By flag"
        assert item["brief"]["why"] == "New devs struggling with auth setup"


class TestEditJsonStdinGuards:
    """A JSON edit that changes nothing must never report success."""

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_unknown_key_is_an_error_not_a_silent_drop(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"wyh": "typo"}')
        assert result.returncode == 1
        assert "Unknown field" in result.stderr
        assert "wyh" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_same_key_flat_and_nested_is_refused(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"why": "a", "brief": {"why": "b"}}')
        assert result.returncode == 1
        assert "pick one" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_non_string_value_is_refused(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture,
                         input='{"why": ["a list"]}')
        assert result.returncode == 1
        assert "must be a string" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_non_object_json_is_refused(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture, input='["why"]')
        assert result.returncode == 1
        assert "must be an object" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_malformed_json_is_refused(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture, input='{"why": ')
        assert result.returncode == 1
        assert "Invalid JSON" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_explicit_json_flag_with_empty_stdin_says_so(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-aaa", "--json", cwd=bon_dir_with_fixture, input="")
        assert result.returncode == 1
        assert "stdin was empty" in result.stderr

    @pytest.mark.parametrize("bon_dir_with_fixture", ["single_outcome"], indirect=True)
    def test_empty_pipe_falls_through_to_the_flag_message(self, bon_dir_with_fixture):
        """An empty pipe is no input at all, not malformed JSON."""
        result = run_bon("edit", "bon-aaa", cwd=bon_dir_with_fixture, input="")
        assert result.returncode == 1
        assert "At least one edit flag required" in result.stderr


class TestEditNote:
    """--note is the repair path for a closing note damaged by shell quoting.

    `bon done --note` refuses to overwrite an existing note, so before this
    flag a mangled done_note was permanent on the item (bon-cefisu, second
    witness: a backticked identifier inside double quotes was command-
    substituted away by the shell, the word vanished, and the command
    exited 0).
    """

    @pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
    def test_note_sets_the_closing_note_on_a_done_item(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-bbb", "--note", "Closed after review",
                         cwd=bon_dir_with_fixture)
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir_with_fixture)["bon-bbb"]["done_note"] == "Closed after review"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
    def test_note_repairs_a_note_done_would_refuse_to_overwrite(self, bon_dir_with_fixture):
        """The whole point: done won't replace it, so edit must."""
        run_bon("edit", "bon-bbb", "--note", "mangled  text", cwd=bon_dir_with_fixture)
        # bon done refuses to touch an existing note on an already-done item
        again = run_bon("done", "bon-bbb", "--note", "the real note",
                        cwd=bon_dir_with_fixture)
        assert "Already done" in again.stdout
        assert _items(bon_dir_with_fixture)["bon-bbb"]["done_note"] == "mangled  text"
        # edit --note is the way back
        fixed = run_bon("edit", "bon-bbb", "--note", "the real note",
                        cwd=bon_dir_with_fixture)
        assert fixed.returncode == 0, fixed.stderr
        assert _items(bon_dir_with_fixture)["bon-bbb"]["done_note"] == "the real note"

    @pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
    def test_note_via_json_survives_hostile_content(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-bbb", cwd=bon_dir_with_fixture,
                         input=json.dumps({"note": HOSTILE}))
        assert result.returncode == 0, result.stderr
        assert _items(bon_dir_with_fixture)["bon-bbb"]["done_note"] == HOSTILE

    @pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
    def test_empty_note_clears_it(self, bon_dir_with_fixture):
        run_bon("edit", "bon-bbb", "--note", "temp", cwd=bon_dir_with_fixture)
        result = run_bon("edit", "bon-bbb", "--note", "", cwd=bon_dir_with_fixture)
        assert result.returncode == 0, result.stderr
        assert "done_note" not in _items(bon_dir_with_fixture)["bon-bbb"]

    @pytest.mark.parametrize("bon_dir_with_fixture", ["mixed_done_open"], indirect=True)
    def test_note_on_an_open_item_is_refused_with_the_right_verb(self, bon_dir_with_fixture):
        result = run_bon("edit", "bon-ccc", "--note", "premature",
                         cwd=bon_dir_with_fixture)
        assert result.returncode == 1
        assert "still open" in result.stderr
        assert "bon done bon-ccc --note" in result.stderr


# ---------------------------------------------------------------------------
# --append-how — atomic annotation (bon-siciri verdict b)
# ---------------------------------------------------------------------------
# Annotating an item used to mean hand-rolled read-modify-write on --how,
# whose failure mode is silent replacement (carte-vudusu). Append is a verb.

def _mk(bon_dir, how=None):
    args = ["new", "Annotated things stay whole", "--why", "w", "--what", "x",
            "--done", "d", "-q"]
    if how:
        args += ["--how", how]
    r = run_bon(*args, cwd=bon_dir)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _how_of(bon_dir, item_id):
    r = run_bon("show", item_id, "--json", cwd=bon_dir)
    return json.loads(r.stdout)["brief"]["how"]


class TestAppendHow:
    def test_append_to_existing(self, bon_dir):
        oid = _mk(bon_dir, how="Original approach.")
        r = run_bon("edit", oid, "--append-how", "UPDATE: new fact.", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert _how_of(bon_dir, oid) == "Original approach.\n\nUPDATE: new fact."

    def test_append_to_absent_sets(self, bon_dir):
        oid = _mk(bon_dir)
        r = run_bon("edit", oid, "--append-how", "First note.", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert _how_of(bon_dir, oid) == "First note."

    def test_append_via_json_stdin(self, bon_dir):
        oid = _mk(bon_dir, how="Base.")
        r = run_bon("edit", oid, cwd=bon_dir,
                    input='{"append_how": "Quotes \\"survive\\" the pipe."}')
        assert r.returncode == 0, r.stderr
        assert _how_of(bon_dir, oid) == 'Base.\n\nQuotes "survive" the pipe.'

    def test_conflict_with_how_errors(self, bon_dir):
        oid = _mk(bon_dir, how="Base.")
        r = run_bon("edit", oid, "--how", "X", "--append-how", "Y", cwd=bon_dir)
        assert r.returncode == 1
        assert "ambiguous" in r.stderr
        assert _how_of(bon_dir, oid) == "Base."  # untouched

    def test_empty_append_errors(self, bon_dir):
        oid = _mk(bon_dir, how="Base.")
        r = run_bon("edit", oid, "--append-how", "  ", cwd=bon_dir)
        assert r.returncode == 1
        assert _how_of(bon_dir, oid) == "Base."

    def test_works_on_done_items(self, bon_dir):
        oid = _mk(bon_dir, how="Base.")
        run_bon("done", oid, cwd=bon_dir)
        r = run_bon("edit", oid, "--append-how", "Post-close note.", cwd=bon_dir)
        assert r.returncode == 0, r.stderr
        assert _how_of(bon_dir, oid).endswith("Post-close note.")
