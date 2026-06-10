"""Walk-up discovery of .bon from subdirectories (bon-vomidi)."""
import json
import os

from conftest import run_bon

from bon.storage import _reset_backend, _reset_data_dir, get_session_identity


def _make_board(root):
    """Initialize a JSONL board with one item at root."""
    bon = root / ".bon"
    bon.mkdir()
    (bon / "prefix").write_text("walk")
    (bon / "items.jsonl").write_text(json.dumps({
        "id": "walk-aaa", "type": "outcome", "title": "Walk-up outcome",
        "brief": {"why": "w", "what": "x", "done": "d"},
        "status": "open", "order": 1,
        "created_at": "2026-06-10T20:00:00Z", "created_by": "test",
    }) + "\n")


class TestWalkUpDiscovery:
    def test_list_from_repo_root(self, tmp_path):
        _make_board(tmp_path)
        result = run_bon("list", cwd=tmp_path)
        assert result.returncode == 0
        assert "Walk-up outcome" in result.stdout

    def test_list_from_subdir(self, tmp_path):
        _make_board(tmp_path)
        sub = tmp_path / "work" / "deep"
        sub.mkdir(parents=True)
        result = run_bon("list", cwd=sub)
        assert result.returncode == 0
        assert "Walk-up outcome" in result.stdout

    def test_nested_repo_is_a_boundary(self, tmp_path):
        _make_board(tmp_path)
        nested = tmp_path / "vendored-repo"
        nested.mkdir()
        (nested / ".git").mkdir()
        result = run_bon("list", cwd=nested)
        assert result.returncode != 0
        assert "Not initialized" in result.stderr

    def test_git_file_is_a_boundary(self, tmp_path):
        # Worktrees and submodules have a .git *file*, not a directory
        _make_board(tmp_path)
        nested = tmp_path / "worktree"
        nested.mkdir()
        (nested / ".git").write_text("gitdir: /elsewhere\n")
        result = run_bon("list", cwd=nested)
        assert result.returncode != 0
        assert "Not initialized" in result.stderr

    def test_bare_handoff_stash_not_adopted(self, tmp_path):
        # ~/.bon holds handoffs but no prefix file — it is not a board
        (tmp_path / ".bon").mkdir()
        sub = tmp_path / "somedir"
        sub.mkdir()
        result = run_bon("list", cwd=sub)
        assert result.returncode != 0
        assert "Not initialized" in result.stderr

    def test_bare_bon_at_cwd_still_counts(self, tmp_path):
        # At CWD a .bon without prefix keeps its old behavior (passes the
        # init check, fails later on prefix) — only the upward walk filters
        (tmp_path / ".bon").mkdir()
        result = run_bon("list", cwd=tmp_path)
        assert "Not initialized" not in result.stderr

    def test_init_in_subdir_creates_nested_board(self, tmp_path):
        # bon init stays CWD-local, like git init
        _make_board(tmp_path)
        sub = tmp_path / "subproject"
        sub.mkdir()
        result = run_bon("init", "--prefix", "nested", cwd=sub)
        assert result.returncode == 0
        assert (sub / ".bon" / "prefix").read_text() == "nested"


class TestSessionIdentityScope:
    def test_subdir_shares_root_identity(self, tmp_path, monkeypatch):
        _make_board(tmp_path)
        sub = tmp_path / "work"
        sub.mkdir()

        monkeypatch.chdir(tmp_path)
        _reset_data_dir(); _reset_backend()
        root_identity = get_session_identity()

        monkeypatch.chdir(sub)
        _reset_data_dir(); _reset_backend()
        sub_identity = get_session_identity()

        assert sub_identity == root_identity
        assert root_identity == os.path.realpath(tmp_path)

    def test_uninitialized_degrades_to_cwd(self, tmp_path, monkeypatch):
        plain = tmp_path / "plain"
        plain.mkdir()
        monkeypatch.chdir(plain)
        _reset_data_dir(); _reset_backend()
        assert get_session_identity() == os.path.realpath(plain)
