"""Tests for bon migrate-repo command."""
import subprocess
import sys

import pytest
from conftest import run_arc


def git_init(path):
    """Initialize a git repo with initial commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True)
    # Need an initial commit for git mv to work
    (path / ".gitkeep").touch()
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True)


def make_arc_dir(path, prefix="arc", items=""):
    """Create .arc/ with prefix and items."""
    arc = path / ".arc"
    arc.mkdir()
    (arc / "prefix").write_text(prefix)
    (arc / "items.jsonl").write_text(items)


class TestMigrateRepoBasic:
    """Basic migrate-repo functionality."""

    def test_renames_arc_to_bon(self, tmp_path):
        """Renames .arc/ → .bon/ in non-git directory."""
        make_arc_dir(tmp_path)

        result = run_arc("migrate-repo", cwd=tmp_path)

        assert result.returncode == 0
        assert (tmp_path / ".bon").is_dir()
        assert not (tmp_path / ".arc").exists()
        assert (tmp_path / ".bon" / "items.jsonl").exists()

    def test_updates_default_prefix(self, tmp_path):
        """Updates prefix from 'arc' to 'bon' when it was the default."""
        make_arc_dir(tmp_path, prefix="arc")

        run_arc("migrate-repo", cwd=tmp_path)

        assert (tmp_path / ".bon" / "prefix").read_text() == "bon"

    def test_preserves_custom_prefix(self, tmp_path):
        """Keeps custom prefixes unchanged."""
        make_arc_dir(tmp_path, prefix="mise")

        run_arc("migrate-repo", cwd=tmp_path)

        assert (tmp_path / ".bon" / "prefix").read_text() == "mise"

    def test_preserves_items(self, tmp_path):
        """Items file content is preserved."""
        items = '{"id":"arc-abc","type":"outcome","title":"Test","status":"open"}\n'
        make_arc_dir(tmp_path, items=items)

        run_arc("migrate-repo", cwd=tmp_path)

        assert (tmp_path / ".bon" / "items.jsonl").read_text() == items

    def test_output_message(self, tmp_path):
        """Reports what was done."""
        make_arc_dir(tmp_path)

        result = run_arc("migrate-repo", cwd=tmp_path)

        assert "Migrated .arc/ → .bon/" in result.stdout
        assert "prefix: 'arc' → 'bon'" in result.stdout

    def test_output_no_prefix_change(self, tmp_path):
        """Does not mention prefix when it wasn't changed."""
        make_arc_dir(tmp_path, prefix="garde")

        result = run_arc("migrate-repo", cwd=tmp_path)

        assert "Migrated .arc/ → .bon/" in result.stdout
        assert "prefix" not in result.stdout


class TestMigrateRepoErrors:
    """Error conditions."""

    def test_error_bon_already_exists(self, tmp_path):
        """Errors when .bon/ already exists."""
        make_arc_dir(tmp_path)
        (tmp_path / ".bon").mkdir()

        result = run_arc("migrate-repo", cwd=tmp_path)

        assert result.returncode == 1
        assert ".bon/ already exists" in result.stderr

    def test_error_no_arc_dir(self, tmp_path):
        """Errors when .arc/ doesn't exist."""
        result = run_arc("migrate-repo", cwd=tmp_path)

        assert result.returncode == 1
        assert "No .arc/ directory found" in result.stderr


class TestMigrateRepoDryRun:
    """Dry run mode."""

    def test_dry_run_no_changes(self, tmp_path):
        """Dry run doesn't modify anything."""
        make_arc_dir(tmp_path)

        result = run_arc("migrate-repo", "--dry-run", cwd=tmp_path)

        assert result.returncode == 0
        assert "Dry run" in result.stdout
        assert (tmp_path / ".arc").is_dir()
        assert not (tmp_path / ".bon").exists()

    def test_dry_run_reports_prefix_update(self, tmp_path):
        """Dry run reports prefix would be updated."""
        make_arc_dir(tmp_path)

        result = run_arc("migrate-repo", "--dry-run", cwd=tmp_path)

        assert "update .bon/prefix: 'arc' → 'bon'" in result.stdout

    def test_dry_run_reports_gitattributes(self, tmp_path):
        """Dry run reports .gitattributes would be updated."""
        make_arc_dir(tmp_path)
        (tmp_path / ".gitattributes").write_text(".arc/*.jsonl merge=union\n")

        result = run_arc("migrate-repo", "--dry-run", cwd=tmp_path)

        assert "update .gitattributes" in result.stdout

    def test_dry_run_no_prefix_report_for_custom(self, tmp_path):
        """Dry run doesn't mention prefix for custom prefixes."""
        make_arc_dir(tmp_path, prefix="mise")

        result = run_arc("migrate-repo", "--dry-run", cwd=tmp_path)

        assert "prefix" not in result.stdout


class TestMigrateRepoGitattributes:
    """Gitattributes handling."""

    def test_updates_gitattributes(self, tmp_path):
        """Updates .arc/ references in .gitattributes."""
        make_arc_dir(tmp_path)
        (tmp_path / ".gitattributes").write_text(".arc/*.jsonl merge=union\n")

        run_arc("migrate-repo", cwd=tmp_path)

        content = (tmp_path / ".gitattributes").read_text()
        assert ".bon/*.jsonl merge=union" in content
        assert ".arc/" not in content

    def test_no_gitattributes(self, tmp_path):
        """Works fine when no .gitattributes exists."""
        make_arc_dir(tmp_path)

        result = run_arc("migrate-repo", cwd=tmp_path)

        assert result.returncode == 0
        assert ".gitattributes" not in result.stdout

    def test_gitattributes_without_arc_refs(self, tmp_path):
        """Leaves .gitattributes alone if no .arc/ references."""
        make_arc_dir(tmp_path)
        (tmp_path / ".gitattributes").write_text("*.md linguist-documentation\n")

        run_arc("migrate-repo", cwd=tmp_path)

        content = (tmp_path / ".gitattributes").read_text()
        assert content == "*.md linguist-documentation\n"


class TestMigrateRepoArchive:
    """Archive file handling."""

    def test_preserves_archive_jsonl(self, tmp_path):
        """Archive file survives migration."""
        make_arc_dir(tmp_path)
        archive = '{"id":"arc-old","type":"outcome","title":"Done","status":"done","archived_at":"2025-01-01T00:00:00Z"}\n'
        (tmp_path / ".arc" / "archive.jsonl").write_text(archive)

        run_arc("migrate-repo", cwd=tmp_path)

        assert (tmp_path / ".bon" / "archive.jsonl").read_text() == archive
        assert not (tmp_path / ".arc").exists()


class TestMigrateRepoGit:
    """Git integration."""

    def test_uses_git_mv(self, tmp_path):
        """Uses git mv in a git repo."""
        git_init(tmp_path)
        make_arc_dir(tmp_path)
        subprocess.run(["git", "add", ".arc"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add arc"], cwd=tmp_path, capture_output=True)

        result = run_arc("migrate-repo", cwd=tmp_path)

        assert result.returncode == 0
        assert "committed" in result.stdout
        assert (tmp_path / ".bon").is_dir()
        assert not (tmp_path / ".arc").exists()

    def test_git_commit_message(self, tmp_path):
        """Commits with the standard message."""
        git_init(tmp_path)
        make_arc_dir(tmp_path)
        subprocess.run(["git", "add", ".arc"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add arc"], cwd=tmp_path, capture_output=True)

        run_arc("migrate-repo", cwd=tmp_path)

        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_path, capture_output=True, text=True
        )
        assert "arc→bon migration" in log.stdout

    def test_git_with_gitattributes(self, tmp_path):
        """Commits both rename and gitattributes update."""
        git_init(tmp_path)
        make_arc_dir(tmp_path)
        (tmp_path / ".gitattributes").write_text(".arc/*.jsonl merge=union\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add arc"], cwd=tmp_path, capture_output=True)

        run_arc("migrate-repo", cwd=tmp_path)

        # Check gitattributes was updated and committed
        content = (tmp_path / ".gitattributes").read_text()
        assert ".bon/*.jsonl" in content

        # Check nothing is unstaged
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_path, capture_output=True, text=True
        )
        assert status.stdout.strip() == ""
