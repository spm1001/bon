"""Tests for bon help command."""

from conftest import run_bon


class TestHelpBasic:
    """Test basic bon help behavior."""

    def test_help_no_args(self, tmp_path, monkeypatch):
        """bon help shows main help."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("help", cwd=tmp_path)

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "new" in result.stdout
        assert "list" in result.stdout
        assert "done" in result.stdout

    def test_help_specific_command(self, tmp_path, monkeypatch):
        """bon help <command> shows command help."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("help", "new", cwd=tmp_path)

        assert result.returncode == 0
        assert "new" in result.stdout.lower()
        assert "--outcome" in result.stdout
        assert "--why" in result.stdout

    def test_help_unknown_command(self, tmp_path, monkeypatch):
        """bon help <unknown> shows error."""
        monkeypatch.chdir(tmp_path)

        result = run_bon("help", "nonexistent", cwd=tmp_path)

        assert result.returncode == 1
        assert "Unknown command: nonexistent" in result.stderr


class TestHelpDoesNotRequireInit:
    """Help should work without .bon/ directory."""

    def test_help_works_without_init(self, tmp_path, monkeypatch):
        """bon help works even when not initialized."""
        monkeypatch.chdir(tmp_path)
        # No .bon/ directory

        result = run_bon("help", cwd=tmp_path)

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
