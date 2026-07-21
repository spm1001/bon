"""
Tests for scripts/open-context.sh orientation output (section 3).

The orientation must surface BOTH top-level outcomes and standalone actions,
and never emit a bare section header. A standalone-only board previously
rendered as empty because the filter grepped only column-0 outcome lines
(bon-cuvice, observed live on spm1001/passe 2026-07-21).
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OPEN_CONTEXT = REPO_ROOT / "scripts" / "open-context.sh"


def run_open_context(tmp_path: Path, *items: dict) -> subprocess.CompletedProcess:
    """Set up a JSONL board in tmp_path and run open-context.sh from it.

    HOME is pointed at the sandbox so the script's context-dir writes
    ($HOME/.claude/.session-context) never touch the real home.
    """
    bon_dir = tmp_path / ".bon"
    bon_dir.mkdir(exist_ok=True)
    (bon_dir / "prefix").write_text("test")
    content = "\n".join(json.dumps(i) for i in items)
    (bon_dir / "items.jsonl").write_text(content + "\n" if content else "")
    return subprocess.run(
        ["bash", str(OPEN_CONTEXT)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"HOME": str(tmp_path), "PATH": "/usr/local/bin:/usr/bin:/bin"},
    )


OUTCOME = {
    "id": "test-out",
    "type": "outcome",
    "title": "Users can frobnicate",
    "brief": {"why": "w", "what": "x", "done": "d"},
    "status": "open",
    "order": 1,
}

STANDALONE = {
    "id": "test-solo",
    "type": "action",
    "title": "Fix the widget",
    "brief": {"why": "w", "what": "x", "done": "d"},
    "status": "open",
    "order": 1,
}

DONE_STANDALONE = {
    "id": "test-fini",
    "type": "action",
    "title": "Old finished thing",
    "brief": {"why": "w", "what": "x", "done": "d"},
    "status": "done",
    "order": 2,
}


def test_outcomes_only_board(tmp_path):
    """Outcomes render under their header; no standalone section appears."""
    result = run_open_context(tmp_path, OUTCOME)
    assert result.returncode == 0
    assert "Outcomes we're working towards:" in result.stdout
    assert "Users can frobnicate" in result.stdout
    assert "Standalone actions:" not in result.stdout


def test_standalone_only_board_shows_items(tmp_path):
    """A standalone-only board surfaces its actions (the bon-cuvice bug)."""
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    assert "Standalone actions:" in result.stdout
    assert "Fix the widget" in result.stdout


def test_standalone_only_board_no_bare_outcomes_header(tmp_path):
    """No bare 'Outcomes' header when there are no outcome lines."""
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    assert "Outcomes we're working towards:" not in result.stdout


def test_mixed_board_shows_both_sections(tmp_path):
    """Outcomes and standalone actions each render under their own header."""
    result = run_open_context(tmp_path, OUTCOME, STANDALONE)
    assert result.returncode == 0
    assert "Outcomes we're working towards:" in result.stdout
    assert "Users can frobnicate" in result.stdout
    assert "Standalone actions:" in result.stdout
    assert "Fix the widget" in result.stdout


def test_done_standalone_not_shown(tmp_path):
    """Completed standalone actions stay out of the orientation."""
    result = run_open_context(tmp_path, STANDALONE, DONE_STANDALONE)
    assert result.returncode == 0
    assert "Fix the widget" in result.stdout
    assert "Old finished thing" not in result.stdout
