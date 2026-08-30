"""Tests for CLI-owned git sync on JSONL boards (bon-guritu).

The fixture builds a bare origin plus two clones and drives BOTH clones
through the bon CLI only — the --done criterion is that convergence needs
no human git. Hermetic git: global/system config are pointed at /dev/null
so a developer's gpgsign or hooks can't leak into the run.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from bon.gitsync import merge_items
from conftest import run_bon

GIT_ENV = dict(
    os.environ,
    GIT_CONFIG_GLOBAL="/dev/null",
    GIT_CONFIG_SYSTEM="/dev/null",
    GIT_TERMINAL_PROMPT="0",
)


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, env=GIT_ENV,
    )


def bon(cwd, *args):
    return run_bon(*args, cwd=cwd, env=GIT_ENV)


def board_titles(clone: Path) -> set[str]:
    titles = set()
    for line in (clone / ".bon" / "items.jsonl").read_text().splitlines():
        if line.strip():
            titles.add(json.loads(line)["title"])
    return titles


def board_items(clone: Path) -> dict[str, dict]:
    out = {}
    for line in (clone / ".bon" / "items.jsonl").read_text().splitlines():
        if line.strip():
            item = json.loads(line)
            out[item["id"]] = item
    return out


def new_item(clone: Path, title: str) -> str:
    result = bon(clone, "new", title, "--why", "w", "--what", "x", "--done", "d", "-q")
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


@pytest.fixture
def two_clones(tmp_path):
    """Bare origin + clone A carrying an adopted board + fresh clone B."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   capture_output=True, text=True, env=GIT_ENV, check=True)

    a = tmp_path / "A"
    git(tmp_path, "clone", str(origin), str(a))
    git(a, "config", "user.name", "Clone A")
    git(a, "config", "user.email", "a@test.local")
    (a / "seed.txt").write_text("seed\n")
    git(a, "add", "seed.txt")
    git(a, "commit", "-m", "initial")
    git(a, "push", "-u", "origin", "main")

    # Board adoption: init, then commit the board — tracking items.jsonl
    # is the deliberate step that switches the sync on.
    result = bon(a, "init", "--prefix", "t")
    assert result.returncode == 0, result.stderr
    git(a, "add", "-f", ".bon")
    git(a, "commit", "-m", "adopt board")
    git(a, "push")

    b = tmp_path / "B"
    git(tmp_path, "clone", str(origin), str(b))
    git(b, "config", "user.name", "Clone B")
    git(b, "config", "user.email", "b@test.local")
    return a, b, origin


class TestDivergentClonesConverge:
    def test_two_clones_editing_different_items_converge(self, two_clones):
        """The --done criterion: convergence with no human git."""
        a, b, origin = two_clones

        id_a = new_item(a, "Item from A")
        # The verb committed and pushed by itself.
        status = git(a, "status", "--porcelain", "--", ".bon")
        assert status.stdout.strip() == ""
        assert "bon: new" in git(origin, "log", "--format=%s", "-1").stdout

        # B never saw Item from A — its verb must fetch, rebase, and push.
        id_b = new_item(b, "Item from B")
        assert board_titles(b) == {"Item from A", "Item from B"}
        assert git(b, "status", "--porcelain", "--", ".bon").stdout.strip() == ""

        # A's next verb converges A too.
        result = bon(a, "edit", id_a, "--why", "updated on A")
        assert result.returncode == 0, result.stderr
        assert board_titles(a) == {"Item from A", "Item from B"}

        # Origin holds everything: a third clone sees both items.
        c = a.parent / "C"
        git(a.parent, "clone", str(origin), str(c))
        assert board_titles(c) == {"Item from A", "Item from B"}
        assert id_b in board_items(c)

    def test_same_item_edit_is_one_loud_conflict(self, two_clones):
        a, b, origin = two_clones
        item_id = new_item(a, "Contested item")

        # B converges first (via its own verb), then A edits and pushes.
        new_item(b, "B warms up")
        result = bon(a, "edit", item_id, "--why", "A's why")
        assert result.returncode == 0, result.stderr

        # B, behind again, edits the same item: loud refusal, nothing lost.
        result = bon(b, "edit", item_id, "--why", "B's why")
        assert result.returncode != 0
        assert "conflict" in result.stderr.lower()
        assert item_id in result.stderr
        # Origin's version is in B's tree; B's change was not applied.
        assert board_items(b)[item_id]["brief"]["why"] == "A's why"


class TestOfflineBehaviour:
    def test_offline_writes_locally_warns_once_pushes_later(self, two_clones):
        a, b, origin = two_clones
        item_id = new_item(a, "Shared item")
        new_item(b, "B converges")  # brings Shared item into B

        url = git(b, "remote", "get-url", "origin").stdout.strip()
        git(b, "remote", "set-url", "origin", str(b.parent / "nonexistent.git"))

        result = bon(b, "edit", item_id, "--how", "offline change")
        assert result.returncode == 0, result.stderr
        assert "could not reach the remote" in result.stderr
        # Committed locally, ready to travel.
        assert git(b, "log", "--format=%s", "-1").stdout.startswith("bon: edit")
        assert board_items(b)[item_id]["brief"]["how"] == "offline change"

        # Back online: the next verb carries the backlog to origin.
        git(b, "remote", "set-url", "origin", url)
        result = bon(b, "edit", item_id, "--done", "done differently")
        assert result.returncode == 0, result.stderr
        c = b.parent / "C-offline"
        git(b.parent, "clone", str(origin), str(c))
        item = board_items(c)[item_id]
        assert item["brief"]["how"] == "offline change"
        assert item["brief"]["done"] == "done differently"


class TestGuards:
    def test_dirty_tree_defers_rebase_and_push(self, two_clones):
        a, b, origin = two_clones
        new_item(b, "B item")          # B pushes; A is now behind
        (a / "seed.txt").write_text("uncommitted local work\n")

        origin_tip = git(origin, "rev-parse", "main").stdout.strip()
        result = bon(a, "new", "A item", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0, result.stderr
        assert "uncommitted changes" in result.stderr
        # No rebase happened: the dirty file is intact, no rebase state dir.
        assert (a / "seed.txt").read_text() == "uncommitted local work\n"
        assert not (a / ".git" / "rebase-merge").exists()
        # Nothing was pushed.
        assert git(origin, "rev-parse", "main").stdout.strip() == origin_tip

    def test_unpushed_non_board_commits_block_the_push(self, two_clones):
        a, b, origin = two_clones
        (a / "seed.txt").write_text("code work\n")
        git(a, "add", "seed.txt")
        git(a, "commit", "-m", "wip: deliberate unpushed code")

        origin_tip = git(origin, "rev-parse", "main").stdout.strip()
        result = bon(a, "new", "Board move", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0, result.stderr
        assert "non-board" in result.stderr
        # Board committed locally, but the wip commit was not published.
        assert git(origin, "rev-parse", "main").stdout.strip() == origin_tip

    def test_untracked_board_never_syncs(self, tmp_path):
        repo = tmp_path / "solo"
        repo.mkdir()
        git(tmp_path, "init", "-b", "main", str(repo))
        git(repo, "config", "user.name", "Solo")
        git(repo, "config", "user.email", "solo@test.local")
        (repo / "seed.txt").write_text("seed\n")
        git(repo, "add", "seed.txt")
        git(repo, "commit", "-m", "initial")

        result = bon(repo, "init", "--prefix", "t")
        assert result.returncode == 0, result.stderr
        result = bon(repo, "new", "Local only", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0, result.stderr
        # No sync commit was minted; the board file is simply untracked.
        assert git(repo, "log", "--format=%s", "-1").stdout.strip() == "initial"

    def test_sync_marker_off_disables(self, two_clones):
        a, b, origin = two_clones
        (a / ".bon" / "sync").write_text("off\n")
        tip = git(a, "rev-parse", "HEAD").stdout.strip()
        result = bon(a, "new", "Unsynced", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0, result.stderr
        assert git(a, "rev-parse", "HEAD").stdout.strip() == tip


class TestMergeItems:
    def base(self):
        return [
            {"id": "t-one", "title": "one", "v": 1},
            {"id": "t-two", "title": "two", "v": 1},
        ]

    def test_disjoint_edits_merge(self):
        base = self.base()
        ours = [dict(base[0], v=2), base[1]]
        theirs = [base[0], dict(base[1], v=3)]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == []
        by_id = {i["id"]: i for i in merged}
        assert by_id["t-one"]["v"] == 2
        assert by_id["t-two"]["v"] == 3

    def test_both_modified_differently_conflicts(self):
        base = self.base()
        ours = [dict(base[0], v=2), base[1]]
        theirs = [dict(base[0], v=3), base[1]]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == ["t-one"]

    def test_both_modified_identically_is_clean(self):
        base = self.base()
        ours = [dict(base[0], v=2), base[1]]
        theirs = [dict(base[0], v=2), base[1]]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == []

    def test_our_delete_their_modify_conflicts(self):
        base = self.base()
        ours = [base[0]]  # deleted t-two (archive)
        theirs = [base[0], dict(base[1], v=9)]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == ["t-two"]

    def test_our_modify_their_delete_conflicts(self):
        base = self.base()
        ours = [base[0], dict(base[1], v=9)]
        theirs = [base[0]]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == ["t-two"]

    def test_clean_delete_applies(self):
        base = self.base()
        ours = [base[0]]  # archived t-two
        theirs = list(base)
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == []
        assert {i["id"] for i in merged} == {"t-one"}

    def test_both_added_same_id_different_content_conflicts(self):
        base = self.base()
        ours = base + [{"id": "t-new", "title": "ours"}]
        theirs = base + [{"id": "t-new", "title": "theirs"}]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == ["t-new"]

    def test_their_addition_survives_our_write(self):
        base = self.base()
        ours = base + [{"id": "t-mine", "title": "mine"}]
        theirs = base + [{"id": "t-theirs", "title": "theirs"}]
        merged, conflicts = merge_items(base, ours, theirs)
        assert conflicts == []
        assert {i["id"] for i in merged} == {"t-one", "t-two", "t-mine", "t-theirs"}


class TestWhileApartCollisions:
    """The essayeur's refutation (2026-08-30): a same-item edit that reaches
    git as a COMMITTED line (offline backlog) bypassed the load-snapshot
    check, and union merge + newest-wins dedup silently discarded one side.
    The repair: resolve loudly and losslessly at every integration."""

    def test_offline_collision_is_loud_and_lossless(self, two_clones):
        import time
        a, b, origin = two_clones
        item_id = new_item(a, "Contested while apart")
        new_item(b, "B converges")  # brings the item into B

        # B goes offline and edits the item (committed locally).
        url = git(b, "remote", "get-url", "origin").stdout.strip()
        git(b, "remote", "set-url", "origin", str(b.parent / "nowhere.git"))
        result = bon(b, "edit", item_id, "--why", "B's offline why")
        assert result.returncode == 0, result.stderr

        # A edits the same item online, LATER, so A's timestamp wins.
        time.sleep(1.1)
        result = bon(a, "edit", item_id, "--why", "A's later why")
        assert result.returncode == 0, result.stderr

        # B reconnects; an unrelated verb integrates the backlog.
        git(b, "remote", "set-url", "origin", url)
        result = bon(b, "new", "Unrelated", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0, result.stderr

        # Loud: the collision is named. Lossless: the displaced version is
        # in the sidecar, and the board holds the newest.
        assert "edited on two clones while apart" in result.stderr
        assert item_id in result.stderr
        assert board_items(b)[item_id]["brief"]["why"] == "A's later why"
        sidecar = b / ".bon" / "sync-conflicts.jsonl"
        assert sidecar.is_file()
        displaced = [json.loads(l) for l in sidecar.read_text().splitlines()]
        assert any(d["id"] == item_id and d["brief"]["why"] == "B's offline why"
                   for d in displaced)

        # The sidecar travels: origin carries it, so the other clone hears.
        c = b.parent / "C-collision"
        git(b.parent, "clone", str(origin), str(c))
        assert (c / ".bon" / "sync-conflicts.jsonl").is_file()

        # Standing cue: B's next verb still warns until the file is cleared.
        result = bon(b, "new", "Another", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0
        assert "unreviewed sync conflicts" in result.stderr
        (b / ".bon" / "sync-conflicts.jsonl").unlink()
        result = bon(b, "new", "Third", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0
        assert "unreviewed sync conflicts" not in result.stderr

    def test_reverse_collision_preserves_the_pushed_edit(self, two_clones):
        """When the offline edit is NEWER, the displaced version is the one
        that had already pushed — it must land in the sidecar, not vanish."""
        import time
        a, b, origin = two_clones
        item_id = new_item(a, "Reverse contest")
        new_item(b, "B converges")

        result = bon(a, "edit", item_id, "--why", "A's earlier why")
        assert result.returncode == 0, result.stderr

        url = git(b, "remote", "get-url", "origin").stdout.strip()
        git(b, "remote", "set-url", "origin", str(b.parent / "nowhere.git"))
        time.sleep(1.1)
        result = bon(b, "edit", item_id, "--why", "B's later offline why")
        assert result.returncode == 0, result.stderr
        git(b, "remote", "set-url", "origin", url)

        result = bon(b, "new", "Trigger", "--why", "w", "--what", "x",
                     "--done", "d", "-q")
        assert result.returncode == 0, result.stderr
        assert "edited on two clones while apart" in result.stderr
        assert board_items(b)[item_id]["brief"]["why"] == "B's later offline why"
        sidecar = b / ".bon" / "sync-conflicts.jsonl"
        displaced = [json.loads(l) for l in sidecar.read_text().splitlines()]
        assert any(d["id"] == item_id and d["brief"]["why"] == "A's earlier why"
                   for d in displaced)


class TestResolveUnionArtifacts:
    def _ctx(self, tmp_path):
        from bon.gitsync import SyncContext
        bon_dir = tmp_path / ".bon"
        bon_dir.mkdir(exist_ok=True)
        return SyncContext(tmp_path, bon_dir, "origin", "main", "origin/main")

    def test_material_duplicates_resolve_and_sidecar(self, tmp_path, capsys):
        from bon.gitsync import resolve_union_artifacts
        ctx = self._ctx(tmp_path)
        old = {"id": "t-dup", "title": "old", "updated_at": "2026-08-30T10:00:00Z"}
        new = {"id": "t-dup", "title": "new", "updated_at": "2026-08-30T11:00:00Z"}
        (tmp_path / ".bon" / "items.jsonl").write_text(
            json.dumps(old) + "\n" + json.dumps(new) + "\n")
        assert resolve_union_artifacts(ctx) is True
        lines = (tmp_path / ".bon" / "items.jsonl").read_text().splitlines()
        assert len(lines) == 1 and json.loads(lines[0])["title"] == "new"
        displaced = json.loads(
            (tmp_path / ".bon" / "sync-conflicts.jsonl").read_text().strip())
        assert displaced["title"] == "old"
        assert "t-dup" in capsys.readouterr().err

    def test_identical_duplicates_dedup_silently(self, tmp_path, capsys):
        from bon.gitsync import resolve_union_artifacts
        ctx = self._ctx(tmp_path)
        item = {"id": "t-same", "title": "same"}
        (tmp_path / ".bon" / "items.jsonl").write_text(
            json.dumps(item) + "\n" + json.dumps(item) + "\n")
        assert resolve_union_artifacts(ctx) is False
        assert not (tmp_path / ".bon" / "sync-conflicts.jsonl").exists()

    def test_conflict_markers_bail_untouched(self, tmp_path):
        from bon.gitsync import resolve_union_artifacts
        ctx = self._ctx(tmp_path)
        content = '{"id": "t-x", "title": "a"}\n<<<<<<< HEAD\n'
        (tmp_path / ".bon" / "items.jsonl").write_text(content)
        assert resolve_union_artifacts(ctx) is False
        assert (tmp_path / ".bon" / "items.jsonl").read_text() == content


class TestSidecarLifecycle:
    """Post-repair essayeur (2026-08-30): the sidecar's own lifecycle must
    not wedge the sync. Deleting it (the warning's own instruction) has to
    commit and travel; the displaced clone hears its cue on the FIRST verb
    the sidecar arrives, not one verb late."""

    def _collide(self, a, b):
        """Produce a while-apart collision resolved on B (sidecar pushed)."""
        import time
        item_id = new_item(a, "Lifecycle contest")
        new_item(b, "B converges")
        url = git(b, "remote", "get-url", "origin").stdout.strip()
        git(b, "remote", "set-url", "origin", str(b.parent / "nowhere2.git"))
        assert bon(b, "edit", item_id, "--why", "B offline").returncode == 0
        time.sleep(1.1)
        assert bon(a, "edit", item_id, "--why", "A later").returncode == 0
        git(b, "remote", "set-url", "origin", url)
        r = bon(b, "new", "Integrator", "--why", "w", "--what", "x",
                "--done", "d", "-q")
        assert r.returncode == 0 and "while apart" in r.stderr
        return item_id

    def test_sidecar_deletion_commits_travels_and_unwedges(self, two_clones):
        a, b, origin = two_clones
        self._collide(a, b)

        # Review done: delete the sidecar, exactly as the warning says.
        (b / ".bon" / "sync-conflicts.jsonl").unlink()
        # Make B behind so a wedge would show as a defer.
        id_a2 = new_item(a, "A moves on")
        r = bon(b, "new", "B after review", "--why", "w", "--what", "x",
                "--done", "d", "-q")
        assert r.returncode == 0, r.stderr
        # Not wedged: no defer warning, B converged, tree clean.
        assert "uncommitted changes" not in r.stderr
        assert id_a2 in board_items(b)
        assert git(b, "status", "--porcelain", "--", ".bon").stdout.strip() == ""
        # The deletion travelled: a fresh clone has no sidecar.
        c = b.parent / "C-lifecycle"
        git(b.parent, "clone", str(origin), str(c))
        assert not (c / ".bon" / "sync-conflicts.jsonl").exists()

    def test_displaced_clone_hears_cue_on_first_verb(self, two_clones):
        a, b, origin = two_clones
        self._collide(a, b)
        # A is the displaced party; the sidecar arrives in A's next rebase.
        r = bon(a, "new", "A first verb after displacement", "--why", "w",
                "--what", "x", "--done", "d", "-q")
        assert r.returncode == 0, r.stderr
        assert "unreviewed sync conflicts" in r.stderr
