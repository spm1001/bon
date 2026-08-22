"""Tests for bon move (cross-repo transfer)."""
import json
import os
from pathlib import Path

import pytest
from conftest import run_bon


def make_board(root: Path, prefix: str) -> Path:
    """Create an initialized JSONL board at root."""
    bon = root / ".bon"
    bon.mkdir(parents=True)
    (bon / "items.jsonl").touch()
    (bon / "prefix").write_text(prefix)
    return root


def seed(root: Path, *items: dict) -> None:
    path = root / ".bon" / "items.jsonl"
    with open(path, "a") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")


def read_items(root: Path) -> dict[str, dict]:
    path = root / ".bon" / "items.jsonl"
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            item = json.loads(line)
            out[item["id"]] = item
    return out


def action(item_id, title="Move me", parent=None, status="open", waiting_for=None, **extra):
    item = {
        "id": item_id,
        "type": "action",
        "title": title,
        "brief": {"why": "original why", "how": "original how",
                  "what": "original what", "done": "original done"},
        "status": status,
        "parent": parent,
        "order": 1,
        "created_at": "2026-06-01T00:00:00Z",
        "created_by": "test",
        "waiting_for": waiting_for,
    }
    item.update(extra)
    return item


def outcome(item_id, title="Things are better", **extra):
    item = {
        "id": item_id,
        "type": "outcome",
        "title": title,
        "brief": {"why": "w", "what": "x", "done": "d"},
        "status": "open",
        "order": 1,
        "created_at": "2026-06-01T00:00:00Z",
        "created_by": "test",
    }
    item.update(extra)
    return item


@pytest.fixture
def two_boards(tmp_path):
    source = make_board(tmp_path / "source", "src")
    target = make_board(tmp_path / "target", "tgt")
    return source, target


class TestMoveRoundTrip:
    def test_move_creates_equivalent_item_in_target(self, two_boards):
        source, target = two_boards
        seed(source, action("src-mova"))

        result = run_bon("move", "src-mova", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Moved: src-mova → tgt-" in result.stdout
        # JSONL targets aren't auto-committed — the move must say so
        assert "commit" in result.stderr

        moved = [i for i in read_items(target).values() if i["id"].startswith("tgt-")]
        assert len(moved) == 1
        new = moved[0]
        assert new["type"] == "action"
        assert new["title"] == "Move me"
        assert new["status"] == "open"
        assert new["parent"] is None
        assert new["brief"]["how"] == "original how"
        assert new["brief"]["what"] == "original what"
        assert new["brief"]["done"] == "original done"
        # Provenance appended, original why preserved
        assert new["brief"]["why"].startswith("original why")
        assert "[Moved from src-mova" in new["brief"]["why"]

    def test_source_closed_with_cross_reference(self, two_boards):
        source, target = two_boards
        seed(source, action("src-mova"))

        run_bon("move", "src-mova", "--to", str(target), cwd=source)

        src = read_items(source)["src-mova"]
        new_id = next(i for i in read_items(target) if i.startswith("tgt-"))
        assert src["status"] == "done"
        assert src["updated_by"] == "moved"
        assert src["done_note"].startswith(f"Moved to {new_id}")
        assert str(target) in src["done_note"]

    def test_quiet_prints_only_new_id(self, two_boards):
        source, target = two_boards
        seed(source, action("src-mova"))

        result = run_bon("move", "src-mova", "--to", str(target), "-q", cwd=source)

        new_id = result.stdout.strip()
        assert new_id.startswith("tgt-")
        assert "\n" not in new_id
        assert new_id in read_items(target)

    def test_move_outcome_without_children(self, two_boards):
        source, target = two_boards
        seed(source, outcome("src-outco"))

        result = run_bon("move", "src-outco", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        moved = [i for i in read_items(target).values() if i["id"].startswith("tgt-")]
        assert len(moved) == 1
        assert moved[0]["type"] == "outcome"


class TestMoveDropsContext:
    def test_parent_dropped_with_provenance(self, two_boards):
        source, target = two_boards
        seed(source, outcome("src-paren", title="Parent outcome"),
             action("src-child", parent="src-paren"))

        result = run_bon("move", "src-child", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        new = next(i for i in read_items(target).values() if i["id"].startswith("tgt-"))
        assert new["parent"] is None
        assert "was under src-paren 'Parent outcome'" in new["brief"]["why"]
        assert "stays here" in result.stderr
        # Parent outcome untouched in source
        assert read_items(source)["src-paren"]["status"] == "open"

    def test_waiting_for_dropped_with_provenance(self, two_boards):
        source, target = two_boards
        seed(source, action("src-block", title="Blocker"),
             action("src-mova", waiting_for=["src-block"], wait_note="why blocked"))

        result = run_bon("move", "src-mova", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        new = next(i for i in read_items(target).values() if i["id"].startswith("tgt-"))
        assert new["waiting_for"] is None
        assert "was waiting for src-block" in new["brief"]["why"]
        assert "don't cross repos" in result.stderr

    def test_waiters_in_source_unblocked_and_named(self, two_boards):
        source, target = two_boards
        seed(source, action("src-mova"),
             action("src-waitr", waiting_for=["src-mova"], wait_note="blocked on mova"))

        result = run_bon("move", "src-mova", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        waiter = read_items(source)["src-waitr"]
        assert waiter["waiting_for"] is None
        assert "wait_note" not in waiter
        assert "Unblocked here: src-waitr" in result.stdout


class TestMoveErrors:
    def test_target_not_initialized(self, two_boards, tmp_path):
        source, _ = two_boards
        bare = tmp_path / "bare"
        bare.mkdir()
        seed(source, action("src-mova"))

        result = run_bon("move", "src-mova", "--to", str(bare), cwd=source)

        assert result.returncode == 1
        assert "Target not initialized" in result.stderr
        assert str(bare) in result.stderr

    def test_target_path_missing(self, two_boards):
        source, _ = two_boards
        seed(source, action("src-mova"))

        result = run_bon("move", "src-mova", "--to", "/nonexistent/nowhere", cwd=source)

        assert result.returncode == 1
        assert "does not exist" in result.stderr

    def test_source_not_found(self, two_boards):
        source, target = two_boards

        result = run_bon("move", "src-ghost", "--to", str(target), cwd=source)

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_done_item_refused(self, two_boards):
        source, target = two_boards
        seed(source, action("src-mova", status="done"))

        result = run_bon("move", "src-mova", "--to", str(target), cwd=source)

        assert result.returncode == 1
        assert "already done" in result.stderr

    def test_outcome_with_children_refused(self, two_boards):
        source, target = two_boards
        seed(source, outcome("src-paren"), action("src-child", parent="src-paren"))

        result = run_bon("move", "src-paren", "--to", str(target), cwd=source)

        assert result.returncode == 1
        assert "child item(s)" in result.stderr
        # Nothing landed in the target
        assert not [i for i in read_items(target) if i.startswith("tgt-")]

    def test_same_repo_refused(self, two_boards):
        source, _ = two_boards
        seed(source, action("src-mova"))

        result = run_bon("move", "src-mova", "--to", str(source), cwd=source)

        assert result.returncode == 1
        assert "this repo" in result.stderr


class TestMoveNameResolution:
    def test_bare_name_resolves_under_repos_buckets(self, tmp_path):
        home = tmp_path / "home"
        target = make_board(home / "repos" / "owner" / "myrepo", "tgt")
        source = make_board(tmp_path / "source", "src")
        seed(source, action("src-mova"))
        env = {**os.environ, "HOME": str(home)}

        result = run_bon("move", "src-mova", "--to", "myrepo", cwd=source, env=env)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert [i for i in read_items(target) if i.startswith("tgt-")]

    def test_bare_name_no_match_errors(self, tmp_path):
        home = tmp_path / "home"
        (home / "repos").mkdir(parents=True)
        source = make_board(tmp_path / "source", "src")
        seed(source, action("src-mova"))
        env = {**os.environ, "HOME": str(home)}

        result = run_bon("move", "src-mova", "--to", "nowhere", cwd=source, env=env)

        assert result.returncode == 1
        assert "No repo named 'nowhere'" in result.stderr

    def test_ambiguous_name_errors(self, tmp_path):
        home = tmp_path / "home"
        make_board(home / "repos" / "alice" / "myrepo", "ta")
        make_board(home / "repos" / "bob" / "myrepo", "tb")
        source = make_board(tmp_path / "source", "src")
        seed(source, action("src-mova"))
        env = {**os.environ, "HOME": str(home)}

        result = run_bon("move", "src-mova", "--to", "myrepo", cwd=source, env=env)

        assert result.returncode == 1
        assert "Ambiguous" in result.stderr


class TestMoveSubtree:
    """The refusal message tells you to move or close the children first.
    Because `move` closes the source item rather than deleting it, that
    instruction used to be unfollowable: the parent's child count never fell
    to zero, so an outcome with any action could never be moved at all.
    """

    def test_done_children_do_not_block(self, two_boards):
        source, target = two_boards
        seed(
            source,
            outcome("src-paren"),
            action("src-child", parent="src-paren", status="done"),
        )

        result = run_bon("move", "src-paren", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        moved = [i for i in read_items(target).values() if i["id"].startswith("tgt-")]
        assert len(moved) == 1
        assert moved[0]["type"] == "outcome"

    def test_children_then_parent_completes(self, two_boards):
        """The documented workflow, end to end."""
        source, target = two_boards
        seed(
            source,
            outcome("src-paren"),
            action("src-chila", parent="src-paren"),
            action("src-chilb", parent="src-paren"),
        )

        for child in ("src-chila", "src-chilb"):
            r = run_bon("move", child, "--to", str(target), cwd=source)
            assert r.returncode == 0, f"stderr: {r.stderr}"

        result = run_bon("move", "src-paren", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        landed = [i for i in read_items(target) if i.startswith("tgt-")]
        assert len(landed) == 3

    def test_open_child_still_refused(self, two_boards):
        source, target = two_boards
        seed(source, outcome("src-paren"), action("src-child", parent="src-paren"))

        result = run_bon("move", "src-paren", "--to", str(target), cwd=source)

        assert result.returncode == 1
        assert "open child item(s)" in result.stderr
        assert not [i for i in read_items(target) if i.startswith("tgt-")]

    def test_standalone_warning_names_the_repair(self, two_boards):
        """Re-parenting in the target is manual, so the warning must say how."""
        source, target = two_boards
        seed(source, outcome("src-paren"), action("src-child", parent="src-paren"))

        result = run_bon("move", "src-child", "--to", str(target), cwd=source)

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "--parent" in result.stderr
