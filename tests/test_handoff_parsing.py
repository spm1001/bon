"""
Tests for handoff discovery and section parsing in open-context.sh.

Verifies that Amp-format handoffs (amp- prefix, source: amp metadata,
thread_url field) are discovered and parsed correctly alongside CC handoffs.

The parsing logic under test:
  - Discovery: ls -t *.md finds amp- prefixed files
  - Purpose: grep "^purpose:" extracts the purpose line
  - Sections: sed '/^## Done/,/^## /' extraction for Done/Next/Gotchas

These are the same sed/grep commands used in open-context.sh lines 93-254.
"""

import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

REPO_ROOT = Path(__file__).parent.parent


# --- Test fixtures ---

AMP_HANDOFF = dedent("""\
    # Handoff — 2026-02-15

    session_id: amp:T-019c637e-cb27-720c-b1db-302c17c7f3a0
    purpose: Fix push notifications and desktop folder chooser
    source: amp
    thread_url: https://ampcode.com/threads/T-019c637e-cb27-720c-b1db-302c17c7f3a0

    ## Done
    - Fixed push notifications failing with BadJwtToken
    - Fixed desktop browser stuck on Reconnecting
    - Added build version tracking

    ## Gotchas
    - Running npm run build while Vite dev server is running bakes DEV=true into the bundle

    ## Risks
    - The dist dev-mode check is still heuristic

    ## Next
    - End-to-end push test script
    - Verify second notification on iOS
""")

CC_HANDOFF = dedent("""\
    # Handoff — 2026-02-14

    session_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    purpose: Refactored session hooks for speed

    ## Done
    - Replaced Python CLI reads with jq
    - Session start under 100ms

    ## Next
    - Test on Mac
""")

AUTO_HANDOFF = dedent("""\
    # Auto-generated handoff — 2026-02-13

    session_id: deadbeef-1234-5678-9abc-def012345678
    purpose: Session ended without /close

    ## Done
    (no commits detected in session)

    ## Next
    - Continue filing skill work
""")


def write_handoff(directory: Path, filename: str, content: str, mtime_offset: int = 0) -> Path:
    """Write a handoff file with optional mtime adjustment for ls -t ordering."""
    filepath = directory / filename
    filepath.write_text(content)
    if mtime_offset != 0:
        import os
        import time
        t = time.time() + mtime_offset
        os.utime(filepath, (t, t))
    return filepath


def extract_purpose(filepath: Path) -> str:
    """Reproduce open-context.sh purpose extraction (line 101)."""
    result = subprocess.run(
        ["bash", "-c", f'grep "^purpose:" "{filepath}" 2>/dev/null | head -1 | cut -d: -f2- | xargs'],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def extract_section(filepath: Path, section: str) -> str:
    """Reproduce open-context.sh section extraction (lines 224-226)."""
    result = subprocess.run(
        ["bash", "-c",
         f"sed -n '/^## {section}/,/^## /{{/^## {section}/d;/^## /d;p;}}' "
         f'"{filepath}" 2>/dev/null | grep -v \'^$\' | head -3 | sed \'s/^- //\''],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def discover_latest(directory: Path) -> str:
    """Reproduce open-context.sh handoff discovery (line 95)."""
    result = subprocess.run(
        ["bash", "-c", f'ls -t "{directory}"/*.md 2>/dev/null | head -1'],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


# --- Discovery ---

class TestDiscovery:
    """ls -t finds amp- and cc-prefixed handoff files."""

    def test_amp_handoff_discovered(self, tmp_path):
        write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        latest = discover_latest(tmp_path)
        assert latest.endswith("amp-019c637e.md")

    def test_latest_is_most_recent(self, tmp_path):
        """Most recently modified file wins, regardless of prefix."""
        write_handoff(tmp_path, "a1b2c3d4.md", CC_HANDOFF, mtime_offset=-10)
        write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF, mtime_offset=0)
        latest = discover_latest(tmp_path)
        assert "amp-019c637e.md" in latest

    def test_cc_handoff_wins_when_newer(self, tmp_path):
        write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF, mtime_offset=-10)
        write_handoff(tmp_path, "a1b2c3d4.md", CC_HANDOFF, mtime_offset=0)
        latest = discover_latest(tmp_path)
        assert "a1b2c3d4.md" in latest

    def test_empty_directory(self, tmp_path):
        latest = discover_latest(tmp_path)
        assert latest == ""

    def test_auto_handoff_discovered(self, tmp_path):
        write_handoff(tmp_path, "deadbeef.md", AUTO_HANDOFF)
        latest = discover_latest(tmp_path)
        assert latest.endswith("deadbeef.md")


# --- Purpose extraction ---

class TestPurposeExtraction:
    """grep ^purpose: extracts from both amp and cc handoffs."""

    def test_amp_purpose(self, tmp_path):
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        assert extract_purpose(f) == "Fix push notifications and desktop folder chooser"

    def test_cc_purpose(self, tmp_path):
        f = write_handoff(tmp_path, "a1b2c3d4.md", CC_HANDOFF)
        assert extract_purpose(f) == "Refactored session hooks for speed"

    def test_auto_handoff_purpose(self, tmp_path):
        f = write_handoff(tmp_path, "deadbeef.md", AUTO_HANDOFF)
        assert extract_purpose(f) == "Session ended without /close"


# --- Section extraction ---

class TestSectionExtraction:
    """sed section parsing works on amp handoff format."""

    def test_amp_done(self, tmp_path):
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        done = extract_section(f, "Done")
        assert "Fixed push notifications" in done
        assert "Fixed desktop browser" in done
        assert "Added build version" in done

    def test_amp_next(self, tmp_path):
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        nxt = extract_section(f, "Next")
        assert "End-to-end push test" in nxt
        assert "Verify second notification" in nxt

    def test_amp_gotchas(self, tmp_path):
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        gotchas = extract_section(f, "Gotchas")
        assert "DEV=true" in gotchas

    def test_cc_done(self, tmp_path):
        f = write_handoff(tmp_path, "a1b2c3d4.md", CC_HANDOFF)
        done = extract_section(f, "Done")
        assert "Replaced Python CLI reads" in done

    def test_missing_section_returns_empty(self, tmp_path):
        f = write_handoff(tmp_path, "a1b2c3d4.md", CC_HANDOFF)
        gotchas = extract_section(f, "Gotchas")
        assert gotchas == ""

    def test_section_stops_at_next_heading(self, tmp_path):
        """Done section doesn't bleed into Gotchas."""
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        done = extract_section(f, "Done")
        assert "DEV=true" not in done

    def test_auto_handoff_done_with_parenthetical(self, tmp_path):
        """Auto-generated handoffs have '(no commits detected)' style content."""
        f = write_handoff(tmp_path, "deadbeef.md", AUTO_HANDOFF)
        done = extract_section(f, "Done")
        assert "no commits detected" in done

    def test_last_section_without_trailing_heading(self, tmp_path):
        """Next is the last section in the amp handoff — no ## after it."""
        # The sed range /^## Next/,/^## / won't match if there's no trailing ##.
        # open-context.sh handles this because sed treats EOF as end-of-range.
        handoff = dedent("""\
            # Handoff

            purpose: Test

            ## Next
            - This is the only section
            - And there's nothing after it
        """)
        f = write_handoff(tmp_path, "test.md", handoff)
        nxt = extract_section(f, "Next")
        assert "This is the only section" in nxt
        assert "nothing after it" in nxt


# --- Amp-specific metadata ---

class TestAmpMetadata:
    """Amp handoffs have extra fields that shouldn't break parsing."""

    def test_source_field_doesnt_confuse_purpose(self, tmp_path):
        """source: amp line shouldn't be picked up as purpose."""
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        purpose = extract_purpose(f)
        assert "amp" != purpose
        assert "Fix push" in purpose

    def test_thread_url_doesnt_confuse_purpose(self, tmp_path):
        f = write_handoff(tmp_path, "amp-019c637e.md", AMP_HANDOFF)
        purpose = extract_purpose(f)
        assert "ampcode.com" not in purpose

    def test_reflection_section_not_in_done(self, tmp_path):
        """Reflection section (present in amp handoffs) stays separate from Done."""
        handoff = dedent("""\
            # Handoff

            purpose: Test reflection boundary

            ## Done
            - Actual work done

            ## Reflection
            **Agent observed:** Something insightful
        """)
        f = write_handoff(tmp_path, "test.md", handoff)
        done = extract_section(f, "Done")
        assert "Actual work" in done
        assert "insightful" not in done
