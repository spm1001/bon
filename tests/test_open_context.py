"""
Tests for scripts/open-context.sh orientation output (section 3).

The orientation must surface BOTH top-level outcomes and standalone actions,
and never emit a bare section header. A standalone-only board previously
rendered as empty because the filter grepped only column-0 outcome lines
(bon-cuvice, observed live on spm1001/passe 2026-07-21).
"""

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
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


# --- Preview budgeting (bon-peluge) ------------------------------------
#
# Claude Code persists oversized hook output to a file and shows only the
# first ~2KB as preview. A handoff inlined BEFORE the orientation skeleton
# spends that whole budget on its Done bullets, pushing UNDERSTANDING=, the
# item list and the Suggested picks past the cut. Observed live 2026-07-21
# on spm1001/passe (10.4KB emitted), and again 2026-07-27 in an unrelated
# session that had to go read the persisted file to find "For Claudes to
# come". The skeleton goes first; the body — which is on disk either way —
# goes last, with its path stated up front so a truncated preview is still
# navigable.

PREVIEW_BUDGET = 2000

BIG_HANDOFF = """# Handoff — 2026-07-20

session_id: deadbeef
purpose: A big session that produced a long handoff
format: fond-v1

## For the next Claude

### Done
{filler}

### Opportunities
- **test-solo**: the suggested pick that must survive truncation

## For Claudes to come

DURABLE_KNOWLEDGE_TAIL_MARKER
"""


def write_handoff(tmp_path: Path, body: str) -> Path:
    hdir = tmp_path / ".bon" / "handoffs"
    hdir.mkdir(parents=True, exist_ok=True)
    path = hdir / "2026-07-20-deadbeef.md"
    path.write_text(body)
    return path


def big_handoff_text() -> str:
    filler = "\n".join(f"- Did a fairly wordy thing number {i}" for i in range(220))
    return BIG_HANDOFF.format(filler=filler)


def test_big_handoff_skeleton_fits_the_preview_budget(tmp_path):
    """Everything load-bearing lands inside the first 2KB, not past the cut."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    (tmp_path / ".bon" / "understanding.md").write_text("# Understanding\n")
    write_handoff(tmp_path, big_handoff_text())
    result = run_open_context(tmp_path, OUTCOME, STANDALONE)
    assert result.returncode == 0

    preview = result.stdout[:PREVIEW_BUDGET]
    assert "Last session" in preview
    assert "UNDERSTANDING=" in preview
    assert "HANDOFF=" in preview
    assert "Outcomes we're working towards:" in preview
    assert "Users can frobnicate" in preview
    assert "Standalone actions:" in preview
    assert "From the last handoff's Opportunities:" in preview


def test_big_handoff_body_is_not_emitted_at_all(tmp_path):
    """The body has an address, so it is not emitted — bon-tebete.

    Emitting it last was not enough: it still blew the budget from the back,
    and it was 78% of this repo's own hook output (9425 of 12183 bytes,
    measured 2026-08-04). It is doubly redundant — the script already extracts
    the purpose line and the Opportunities bullets, and /open step 1 reads the
    file itself for the "For Claudes to come" synthesis.
    """
    (tmp_path / ".bon").mkdir(exist_ok=True)
    path = write_handoff(tmp_path, big_handoff_text())
    # STANDALONE is test-solo, which the Opportunities bullet names — without it
    # the mosase liveness filter correctly drops the bullet as a closed item.
    result = run_open_context(tmp_path, OUTCOME, STANDALONE)
    assert result.returncode == 0

    out = result.stdout
    assert "DURABLE_KNOWLEDGE_TAIL_MARKER" not in out, "body must not be inlined"
    assert "Did a fairly wordy thing number 0" not in out, "Done bullets must not be inlined"
    assert "# Handoff —" not in out, "no handoff header means no body"
    # Delivery is the path, and the extracted hot parts.
    assert f"HANDOFF={path}" in out
    assert "A big session that produced a long handoff" in out
    assert "the suggested pick that must survive truncation" in out


def test_whole_output_fits_the_budget_even_with_a_big_handoff(tmp_path):
    """Not just the skeleton — the ENTIRE emission stays small (bon-tebete).

    This is the property that stops the persist-and-preview from firing, which
    is what forced a remedial Read of the hook's own output file.
    """
    (tmp_path / ".bon").mkdir(exist_ok=True)
    (tmp_path / ".bon" / "understanding.md").write_text("# Understanding\n")
    write_handoff(tmp_path, big_handoff_text())
    result = run_open_context(tmp_path, OUTCOME, STANDALONE)
    assert result.returncode == 0
    assert len(result.stdout) < PREVIEW_BUDGET, (
        f"whole output must fit the preview, got {len(result.stdout)} bytes"
    )


def test_handoff_path_is_emitted(tmp_path):
    """A truncated preview still tells the reader where the full text lives."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    path = write_handoff(tmp_path, big_handoff_text())
    result = run_open_context(tmp_path, OUTCOME)
    assert result.returncode == 0
    assert f"HANDOFF={path}" in result.stdout


def test_no_handoff_emits_no_handoff_path(tmp_path):
    """Boards with no handoff yet stay quiet — no empty HANDOFF= line."""
    result = run_open_context(tmp_path, OUTCOME)
    assert result.returncode == 0
    assert "HANDOFF=" not in result.stdout


# --- Same-day ranking (notes-sovike) ------------------------------------

def test_same_day_tie_prefers_filename_time_over_mtime(tmp_path):
    """Two same-day handoffs, mtimes INVERTED — as a clone or sync rebase can
    leave them, since checkout order is arbitrary. The v4 filename carries the
    true write time, so the reader must trust it over mtime (notes-sovike).
    """
    import os
    hdir = tmp_path / ".bon" / "handoffs"
    hdir.mkdir(parents=True)
    superseded = hdir / "2026-07-31-0901-ffffffff.md"
    latest = hdir / "2026-07-31-1813-11111111.md"
    superseded.write_text("# Handoff — 2026-07-31\n\npurpose: pass 1 (superseded)\n")
    latest.write_text("# Handoff — 2026-07-31\n\npurpose: pass 2 supersedes pass 1\n")
    t = datetime.now(timezone.utc).timestamp()
    os.utime(latest, (t - 3600, t - 3600))   # rebase wrote the stale file last
    os.utime(superseded, (t, t))
    result = run_open_context(tmp_path, OUTCOME)
    assert result.returncode == 0
    assert f"HANDOFF={latest}" in result.stdout, (
        "same-day tie must be broken by the filename's HHMM, not by mtime"
    )


def test_same_day_v3_names_still_rank_by_mtime(tmp_path):
    """Old-style names carry no time — within a day they keep ranking by
    mtime, exactly as before the v4 scheme (no retro-rename, no regression).
    """
    import os
    hdir = tmp_path / ".bon" / "handoffs"
    hdir.mkdir(parents=True)
    older = hdir / "2026-07-31-ffffffff.md"
    newer = hdir / "2026-07-31-11111111.md"
    older.write_text("# Handoff — 2026-07-31\n\npurpose: earlier v3\n")
    newer.write_text("# Handoff — 2026-07-31\n\npurpose: later v3\n")
    t = datetime.now(timezone.utc).timestamp()
    os.utime(older, (t - 3600, t - 3600))
    os.utime(newer, (t, t))
    result = run_open_context(tmp_path, OUTCOME)
    assert result.returncode == 0
    assert f"HANDOFF={newer}" in result.stdout


def test_suggested_precedes_the_item_lists(tmp_path):
    """The baton outranks the landscape: Suggested is small and curated."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    write_handoff(tmp_path, big_handoff_text())
    result = run_open_context(tmp_path, OUTCOME, STANDALONE)
    assert result.returncode == 0
    out = result.stdout
    assert out.index("From the last handoff's Opportunities:") < out.index(
        "Outcomes we're working towards:"
    )


def test_long_standalone_list_is_capped_and_says_so(tmp_path):
    """A capped list states its remainder — a silent cut reads as completeness."""
    many = [
        {
            "id": f"test-s{i:02d}",
            "type": "action",
            "title": f"Standalone item number {i}",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "status": "open",
            "order": i,
        }
        for i in range(20)
    ]
    result = run_open_context(tmp_path, *many)
    assert result.returncode == 0
    out = result.stdout
    assert "Standalone actions:" in out
    assert "… +8 more — full list: bon list" in out
    # First 12 shown, the rest elided but accounted for.
    assert "Standalone item number 0" in out
    assert "Standalone item number 19" not in out


def test_short_standalone_list_has_no_cap_line(tmp_path):
    """Under the cap, no residue — the honest line only appears when it's true."""
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    assert "Fix the widget" in result.stdout
    assert "more — full list" not in result.stdout


def test_long_outcome_list_is_capped_and_says_so(tmp_path):
    """Outcomes cap like standalone does — bon-tebete closes the asymmetry.

    bon-wokapu capped the standalone pile and left outcomes uncapped: the same
    growing list with the same failure mode. Inert on a small board; a guard
    against a large one.
    """
    many = [
        {
            "id": f"test-o{i:02d}",
            "type": "outcome",
            "title": f"Outcome number {i} is true",
            "brief": {"why": "w", "what": "x", "done": "d"},
            "status": "open",
            "order": i,
        }
        for i in range(20)
    ]
    result = run_open_context(tmp_path, *many)
    assert result.returncode == 0
    out = result.stdout
    assert "Outcomes we're working towards:" in out
    assert "… +8 more — full list: bon list" in out
    assert "Outcome number 0 is true" in out
    assert "Outcome number 19 is true" not in out


def test_short_outcome_list_has_no_cap_line(tmp_path):
    """Under the cap, no residue — this board has 10 outcomes, so it must stay quiet."""
    result = run_open_context(tmp_path, OUTCOME)
    assert result.returncode == 0
    assert "Users can frobnicate" in result.stdout
    assert "more — full list" not in result.stdout


# --- Orientation truthfulness (bon-bafume cluster) -----------------------
#
# Four papercuts, three sessions, one day (2026-08-02): the age string showed
# clone age not session age (bon-wakaju); suggestions named items closed since
# the handoff (bon-mosase); Suggested was unbounded and ate the 2KB preview
# (bon-wokapu); and the "Suggested" label misrepresented deliberate-inaction
# notes as invitations (bon-dokahi).


def handoff_headed(day: str, opportunities: str) -> str:
    return (
        f"# Handoff — {day}\n\nsession_id: cafebabe\npurpose: test session\n"
        f"format: fond-v1\n\n## For the next Claude\n\n### Done\n- something\n\n"
        f"### Opportunities\n{opportunities}\n\n## For Claudes to come\n\ntail\n"
    )


def test_age_string_uses_header_date_not_clone_mtime(tmp_path):
    """A months-old handoff with a fresh mtime shows months, not 'just now'.

    A clone flattens every mtime to checkout time, so mtime-derived age reads
    as days-since-clone (bon-wakaju: a 2026-03-30 handoff shown as '26d ago')."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    old_day = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    write_handoff(tmp_path, handoff_headed(old_day, "- **test-solo**: a pick"))
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    m = re.search(r"Last session \((\d+)d ago\)", result.stdout)
    assert m, f"expected day-granularity age, got: {result.stdout[:200]!r}"
    assert 89 <= int(m.group(1)) <= 91


def test_age_same_day_keeps_fine_granularity(tmp_path):
    """When mtime agrees with the header date, the finer mtime age survives."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    write_handoff(tmp_path, handoff_headed(today, "- **test-solo**: a pick"))
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    assert re.search(r"Last session \((just now|\d+m ago|\d+h ago)\)", result.stdout)


def test_suggested_drops_bullets_whose_items_closed(tmp_path):
    """A suggestion naming only closed this-board items is omitted — and the
    omission is stated, never silent (bon-mosase)."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    opportunities = (
        "- **test-solo**: still-open pick\n"
        "- **test-fini**: closed pick that must vanish\n"
        "- foreign coordinate stays (zzz-abcdef)"
    )
    write_handoff(tmp_path, handoff_headed("2026-07-20", opportunities))
    result = run_open_context(tmp_path, STANDALONE, DONE_STANDALONE)
    assert result.returncode == 0
    # Scope to the orientation skeleton: the handoff BODY (section 8) is
    # emitted in full by design, so the original bullets reappear there.
    skeleton = result.stdout.split("# Handoff —")[0]
    assert "still-open pick" in skeleton
    assert "closed pick that must vanish" not in skeleton
    assert "foreign coordinate stays" in skeleton  # other boards can't be checked here
    assert "1 omitted — their items have closed" in skeleton


def test_all_suggestions_closed_says_so(tmp_path):
    """Every named item closed → an honest one-liner, not a silent absence."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    write_handoff(
        tmp_path, handoff_headed("2026-07-20", "- **test-fini**: finished pick")
    )
    result = run_open_context(tmp_path, STANDALONE, DONE_STANDALONE)
    assert result.returncode == 0
    skeleton = result.stdout.split("# Handoff —")[0]
    assert "have since closed" in skeleton
    assert "finished pick" not in skeleton


def fat_opportunities() -> str:
    return "\n".join(
        f"- Fat opportunity number {i:02d} is here. Followed by a very long "
        f"elaboration sentence that repeats itself at some length to model the "
        f"wordy handoff bullets observed on the infra board on 2026-08-02."
        for i in range(18)
    )


def test_fat_opportunities_are_bounded_and_say_so(tmp_path):
    """Bullets trim to their first sentence, the count is capped, and the
    remainder is stated (bon-wokapu: 18 wordy lines ate the whole preview)."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    write_handoff(tmp_path, handoff_headed("2026-07-20", fat_opportunities()))
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    out = result.stdout
    suggested_block = out.split("From the last handoff's Opportunities:")[1].split(
        "\n\n"
    )[0]
    assert "Fat opportunity number 00 is here." in suggested_block
    assert "Followed by a very long" not in suggested_block  # first sentence only
    assert "… +12 more in the handoff" in suggested_block
    assert "Fat opportunity number 17" not in suggested_block


def test_fat_opportunities_keep_skeleton_in_budget(tmp_path):
    """With a fat Opportunities section, the whole skeleton still previews."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    (tmp_path / ".bon" / "understanding.md").write_text("# Understanding\n")
    write_handoff(tmp_path, handoff_headed("2026-07-20", fat_opportunities()))
    result = run_open_context(tmp_path, OUTCOME, STANDALONE)
    assert result.returncode == 0
    preview = result.stdout[:PREVIEW_BUDGET]
    assert "UNDERSTANDING=" in preview
    assert "Outcomes we're working towards:" in preview
    assert "Standalone actions:" in preview


def test_suggested_label_names_its_source(tmp_path):
    """The label says where the lines come from instead of vouching for them
    (bon-dokahi: 3 of 4 'suggestions' were deliberate-inaction notes)."""
    (tmp_path / ".bon").mkdir(exist_ok=True)
    write_handoff(tmp_path, handoff_headed("2026-07-20", "- **test-solo**: a pick"))
    result = run_open_context(tmp_path, STANDALONE)
    assert result.returncode == 0
    assert "From the last handoff's Opportunities:" in result.stdout
    assert "Suggested:" not in result.stdout
