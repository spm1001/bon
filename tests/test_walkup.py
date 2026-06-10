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


class TestClonedBoardDetection:
    """cepumi/vibejo: a clone with knowledge files but gitignored markers
    must fail loudly, not present a phantom empty store."""

    def _make_cloned_shape(self, root):
        bon = root / ".bon"
        (bon / "handoffs").mkdir(parents=True)
        (bon / "handoffs" / "abc123.md").write_text("# Handoff — 2026-06-01\n")
        (bon / "understanding.md").write_text("# Understanding\n")

    def test_cloned_shape_fails_loudly_at_root(self, tmp_path):
        self._make_cloned_shape(tmp_path)
        result = run_bon("list", cwd=tmp_path)
        assert result.returncode != 0
        assert "fresh clone" in result.stderr
        assert "bon init --prefix" in result.stderr

    def test_cloned_shape_diagnosed_from_subdir(self, tmp_path):
        self._make_cloned_shape(tmp_path)
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src"
        sub.mkdir()
        result = run_bon("list", cwd=sub)
        assert result.returncode != 0
        assert "fresh clone" in result.stderr

    def test_stash_without_git_not_diagnosed_from_subdir(self, tmp_path):
        # ~/.bon-style stash with no .git stays unadopted from below
        self._make_cloned_shape(tmp_path)
        sub = tmp_path / "somedir"
        sub.mkdir()
        result = run_bon("list", cwd=sub)
        assert result.returncode != 0
        assert "Not initialized" in result.stderr

    def test_reconnect_recipe_works_end_to_end(self, tmp_path):
        self._make_cloned_shape(tmp_path)
        result = run_bon("init", "--prefix", "plg", cwd=tmp_path)
        assert result.returncode == 0
        assert "Reconnected" in result.stdout
        # Knowledge files untouched, marker restored
        assert (tmp_path / ".bon" / "understanding.md").read_text() == "# Understanding\n"
        assert (tmp_path / ".bon" / "prefix").read_text() == "plg"
        assert run_bon("list", cwd=tmp_path).returncode == 0

    def test_init_preserves_existing_items_jsonl(self, tmp_path):
        bon = tmp_path / ".bon"
        bon.mkdir()
        line = '{"id":"plg-aaa","type":"outcome","title":"T","brief":{"why":"w","what":"x","done":"d"},"status":"open","order":1,"created_at":"2026-06-10T20:00:00Z","created_by":"t"}\n'
        (bon / "items.jsonl").write_text(line)
        result = run_bon("init", "--prefix", "plg", cwd=tmp_path)
        assert result.returncode == 0
        assert (bon / "items.jsonl").read_text() == line

    def test_init_with_prefix_still_refuses(self, tmp_path):
        bon = tmp_path / ".bon"
        bon.mkdir()
        (bon / "prefix").write_text("x")
        result = run_bon("init", "--prefix", "y", cwd=tmp_path)
        assert result.returncode != 0
        assert "already exists" in result.stderr
