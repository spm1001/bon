"""
Tests for auto-handoff.sh — the mechanical safety net for sessions
that end without /close.

Tests the three paths:
1. Mechanical fallback (no transcript) — always available
2. LLM path with failing claude -p — should fall back to mechanical
3. Single quotes in context data — should not break the script
"""

import os
import subprocess
import stat
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).parent.parent
AUTO_HANDOFF = REPO_ROOT / "scripts" / "auto-handoff.sh"


@pytest.fixture
def bon_project(tmp_path):
    """A minimal bon project with .bon/ directory."""
    bon_dir = tmp_path / ".bon"
    bon_dir.mkdir()
    handoffs_dir = bon_dir / "handoffs"
    handoffs_dir.mkdir()
    # Initialize a git repo so git log doesn't fail
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"},
    )
    return tmp_path


def run_auto_handoff(cwd, session_id, transcript=None, extra_path=None):
    """Run auto-handoff.sh and return the result."""
    args = [str(AUTO_HANDOFF), str(cwd), session_id]
    if transcript:
        args.append(str(transcript))
    env = {**os.environ}
    if extra_path:
        env["PATH"] = f"{extra_path}:{env['PATH']}"
    return subprocess.run(
        args, capture_output=True, text=True, env=env, timeout=10,
    )


def read_handoff(bon_project, session_id):
    """Read the handoff file written by auto-handoff.sh."""
    short_id = session_id[:8]
    handoff_file = bon_project / ".bon" / "handoffs" / f"{short_id}.md"
    if handoff_file.exists():
        return handoff_file.read_text()
    return None


class TestMechanicalFallback:
    """No transcript → mechanical handoff written directly."""

    def test_writes_handoff_file(self, bon_project):
        sid = "aabbccdd-1234-5678-9abc-def012345678"
        result = run_auto_handoff(bon_project, sid)
        assert result.returncode == 0
        content = read_handoff(bon_project, sid)
        assert content is not None
        assert "# Handoff" in content
        assert "(auto)" in content
        assert f"session_id: {sid}" in content

    def test_has_required_sections(self, bon_project):
        sid = "bbccddee-1234-5678-9abc-def012345678"
        run_auto_handoff(bon_project, sid)
        content = read_handoff(bon_project, sid)
        assert "## Done" in content
        assert "## Next" in content
        assert "## Gotchas" in content
        assert "no reflective close" in content

    def test_no_session_id_does_nothing(self, bon_project):
        result = run_auto_handoff(bon_project, "")
        assert result.returncode == 0
        handoffs = list((bon_project / ".bon" / "handoffs").glob("*.md"))
        assert len(handoffs) == 0

    def test_skips_if_handoff_exists(self, bon_project):
        sid = "ccddaabb-1234-5678-9abc-def012345678"
        short_id = sid[:8]
        handoff_file = bon_project / ".bon" / "handoffs" / f"{short_id}.md"
        handoff_file.write_text("existing handoff")
        run_auto_handoff(bon_project, sid)
        assert handoff_file.read_text() == "existing handoff"


class TestSingleQuotes:
    """Single quotes in git messages should not break the script."""

    def test_mechanical_path_with_single_quote_commits(self, bon_project):
        """Git messages with single quotes don't break the mechanical path."""
        subprocess.run(
            ["git", "-C", str(bon_project), "commit", "--allow-empty",
             "-m", "fix: don't break on apostrophes"],
            capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"},
        )
        sid = "ddaabbcc-1234-5678-9abc-def012345678"
        result = run_auto_handoff(bon_project, sid)
        assert result.returncode == 0
        content = read_handoff(bon_project, sid)
        assert content is not None
        assert "## Done" in content


class TestLLMFallback:
    """When claude -p fails, should fall back to mechanical handoff."""

    @pytest.fixture
    def mock_bin(self, tmp_path):
        """Directory with mock claude and ccconv that simulate failure."""
        bin_dir = tmp_path / "mock_bin"
        bin_dir.mkdir()
        return bin_dir

    def _write_mock(self, bin_dir, name, script):
        mock = bin_dir / name
        mock.write_text(script)
        mock.chmod(mock.stat().st_mode | stat.S_IEXEC)

    def test_failed_claude_falls_back_to_mechanical(self, bon_project, mock_bin):
        """If claude -p returns empty, mechanical handoff is written."""
        # Mock ccconv: outputs a fake conversation
        self._write_mock(mock_bin, "ccconv", dedent("""\
            #!/bin/bash
            echo "Human: hello"
            echo "Assistant: hi there"
        """))
        # Mock claude: returns empty (simulating failure)
        self._write_mock(mock_bin, "claude", dedent("""\
            #!/bin/bash
            exit 0
        """))
        # Create a fake transcript
        transcript = bon_project / "transcript.jsonl"
        transcript.write_text('{"type":"message"}\n')

        sid = "eeffaabb-1234-5678-9abc-def012345678"
        run_auto_handoff(bon_project, sid, transcript=transcript, extra_path=str(mock_bin))

        # The nohup background process needs a moment
        import time
        time.sleep(2)

        content = read_handoff(bon_project, sid)
        assert content is not None
        assert "## Done" in content
        assert "LLM handoff generation failed" in content

    def test_failed_ccconv_falls_back_to_mechanical(self, bon_project, mock_bin):
        """If ccconv returns empty, mechanical handoff is written."""
        # Mock ccconv: returns nothing
        self._write_mock(mock_bin, "ccconv", dedent("""\
            #!/bin/bash
            exit 0
        """))
        # Mock claude: should not be called
        self._write_mock(mock_bin, "claude", dedent("""\
            #!/bin/bash
            echo "This should not appear"
        """))
        transcript = bon_project / "transcript.jsonl"
        transcript.write_text('{"type":"message"}\n')

        sid = "ffaabbcc-1234-5678-9abc-def012345678"
        run_auto_handoff(bon_project, sid, transcript=transcript, extra_path=str(mock_bin))

        import time
        time.sleep(2)

        content = read_handoff(bon_project, sid)
        assert content is not None
        assert "## Done" in content
        # ccconv failure fallback doesn't have the LLM-specific gotcha
        assert "LLM handoff generation failed" not in content

    def test_single_quotes_in_llm_path(self, bon_project, mock_bin):
        """Single quotes in git messages don't break the temp script."""
        subprocess.run(
            ["git", "-C", str(bon_project), "commit", "--allow-empty",
             "-m", "fix: it's a 'quoted' message"],
            capture_output=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                 "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"},
        )
        # Mock ccconv: outputs conversation
        self._write_mock(mock_bin, "ccconv", dedent("""\
            #!/bin/bash
            echo "Human: fix the issue"
            echo "Assistant: done"
        """))
        # Mock claude: returns empty (so we can check fallback works)
        self._write_mock(mock_bin, "claude", dedent("""\
            #!/bin/bash
            exit 0
        """))
        transcript = bon_project / "transcript.jsonl"
        transcript.write_text('{"type":"message"}\n')

        sid = "aabb1122-1234-5678-9abc-def012345678"
        run_auto_handoff(bon_project, sid, transcript=transcript, extra_path=str(mock_bin))

        import time
        time.sleep(2)

        content = read_handoff(bon_project, sid)
        assert content is not None
        assert "## Done" in content
