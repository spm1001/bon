"""Tests for interactive mode (prompt_brief)."""
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from arc.cli import prompt_brief
from conftest import run_arc


class TestPromptBrief:
    """Test prompt_brief() function directly."""

    def test_valid_brief_returned(self):
        """Valid input returns complete brief dict."""
        with patch('builtins.input', side_effect=["Because reasons", "A thing", "It works"]):
            brief = prompt_brief()

        assert brief == {
            "why": "Because reasons",
            "what": "A thing",
            "done": "It works",
        }

    def test_empty_why_rejected(self):
        """Empty 'why' causes exit."""
        with patch('builtins.input', side_effect=["", "A thing", "It works"]):
            with pytest.raises(SystemExit):
                prompt_brief()

    def test_empty_what_rejected(self):
        """Empty 'what' causes exit."""
        with patch('builtins.input', side_effect=["Because reasons", "", "It works"]):
            with pytest.raises(SystemExit):
                prompt_brief()

    def test_empty_done_rejected(self):
        """Empty 'done' causes exit."""
        with patch('builtins.input', side_effect=["Because reasons", "A thing", ""]):
            with pytest.raises(SystemExit):
                prompt_brief()

    def test_whitespace_only_rejected(self):
        """Whitespace-only input rejected."""
        with patch('builtins.input', side_effect=["   ", "A thing", "It works"]):
            with pytest.raises(SystemExit):
                prompt_brief()

    def test_input_stripped(self):
        """Input is stripped of leading/trailing whitespace."""
        with patch('builtins.input', side_effect=["  Because reasons  ", "  A thing  ", "  It works  "]):
            brief = prompt_brief()

        assert brief["why"] == "Because reasons"
        assert brief["what"] == "A thing"
        assert brief["done"] == "It works"


class TestInteractiveCLI:
    """Test CLI with interactive mode triggered."""

    def test_interactive_mode_creates_item(self, arc_dir, monkeypatch):
        """Interactive mode creates item when no brief flags given."""
        monkeypatch.chdir(arc_dir)

        # Mock isatty to return True, then provide input
        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', side_effect=["Test why", "Test what", "Test done"]):
                # Import and call main directly to use mocked stdin
                from arc.cli import main
                with patch('sys.argv', ['arc', 'new', 'Interactive test']):
                    main()

        # Verify item created
        import json
        items = (arc_dir / ".arc" / "items.jsonl").read_text().strip()
        item = json.loads(items)
        assert item["title"] == "Interactive test"
        assert item["brief"]["why"] == "Test why"
        assert item["brief"]["what"] == "Test what"
        assert item["brief"]["done"] == "Test done"

    def test_flags_bypass_interactive(self, arc_dir, monkeypatch):
        """Providing all brief flags bypasses interactive prompt."""
        monkeypatch.chdir(arc_dir)

        # Even with TTY, flags should bypass prompts
        result = run_arc(
            "new", "Non-interactive",
            "--why", "Flag why",
            "--what", "Flag what",
            "--done", "Flag done",
            cwd=arc_dir
        )

        assert result.returncode == 0

        import json
        items = (arc_dir / ".arc" / "items.jsonl").read_text().strip()
        item = json.loads(items)
        assert item["brief"]["why"] == "Flag why"

    def test_partial_flags_with_tty_uses_interactive(self, arc_dir, monkeypatch):
        """Partial flags with TTY still prompts for all fields."""
        monkeypatch.chdir(arc_dir)

        # Provide only --why, should prompt for all three
        with patch('sys.stdin.isatty', return_value=True):
            with patch('builtins.input', side_effect=["Interactive why", "Interactive what", "Interactive done"]):
                from arc.cli import main
                with patch('sys.argv', ['arc', 'new', 'Partial flags', '--why', 'Ignored']):
                    main()

        import json
        items = (arc_dir / ".arc" / "items.jsonl").read_text().strip()
        item = json.loads(items)
        # Interactive input should be used, not the flag
        assert item["brief"]["why"] == "Interactive why"
