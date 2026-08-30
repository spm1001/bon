"""Tests for the draw-down baton (bon-jeweke).

The --done, verbatim: "Drawing down an item another session last worked
surfaces that session's handoff; a fresh item surfaces nothing."
"""
import json

from conftest import run_bon


def _seed_item(bon_dir, item_id="bon-thread", title="Threaded work"):
    item = {
        "id": item_id,
        "type": "action",
        "title": title,
        "brief": {"why": "w", "what": "1. Step one 2. Step two", "done": "d"},
        "status": "open",
        "order": 1,
    }
    items_file = bon_dir / ".bon" / "items.jsonl"
    existing = items_file.read_text() if items_file.exists() else ""
    items_file.write_text(existing + json.dumps(item) + "\n")
    return item_id


def _write_handoff(bon_dir, name, items_line, day="2026-08-30"):
    hdir = bon_dir / "handoffs"
    hdir.mkdir(exist_ok=True)
    (hdir / name).write_text(
        f"# Handoff — {day}\n\n"
        "session_id: deadbeef\n"
        "purpose: worked the thread\n"
        f"items: {items_line}\n"
        "format: fond-v1\n\n"
        "## For the next Claude\n"
    )


def test_cited_item_surfaces_the_handoff(bon_dir, monkeypatch):
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    _write_handoff(bon_dir, "2026-08-30-1100-deadbeef.md", item_id)

    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton (2026-08-30)" in result.stdout
    assert "2026-08-30-1100-deadbeef.md" in result.stdout
    assert "worked the thread" in result.stdout


def test_fresh_item_surfaces_nothing(bon_dir, monkeypatch):
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    _write_handoff(bon_dir, "2026-08-30-1100-deadbeef.md", "bon-someoneelse")

    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton" not in result.stdout


def test_newest_citing_handoff_wins(bon_dir, monkeypatch):
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    _write_handoff(bon_dir, "2026-08-29-0900-earlier1.md", item_id, day="2026-08-29")
    _write_handoff(bon_dir, "2026-08-30-1415-later002.md", item_id, day="2026-08-30")

    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "2026-08-30-1415-later002.md" in result.stdout
    assert "earlier1" not in result.stdout


def test_id_match_is_word_bounded(bon_dir, monkeypatch):
    """bon-thread must not match a handoff citing bon-threadier."""
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    _write_handoff(bon_dir, "2026-08-30-1100-deadbeef.md", "bon-threadier")

    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton" not in result.stdout


def test_room_handoffs_are_found(bon_dir, monkeypatch):
    """The baton follows the ticket into room-level handoffs dirs."""
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    room = bon_dir / "somewhere" / "deep"
    room.mkdir(parents=True)
    hdir = room / "handoffs"
    hdir.mkdir()
    (hdir / "2026-08-30-1200-roomroom.md").write_text(
        "# Handoff — 2026-08-30\n\nsession_id: roomroom\n"
        "purpose: room thread\n"
        f"items: {item_id}\nformat: fond-v1\n"
    )

    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton (2026-08-30)" in result.stdout
    assert "roomroom" in result.stdout


# --- Essayeur refutation repairs (2026-08-30) ---------------------------------

def test_vendored_clone_handoffs_are_never_batons(bon_dir, monkeypatch):
    """A handoffs dir behind a foreign .git/.bon boundary (a vendored plugin
    cache, a nested repo) is another repo's territory — never served."""
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    vendored = bon_dir / "plugins" / "cache" / "somepkg"
    (vendored / "handoffs").mkdir(parents=True)
    (vendored / ".git").mkdir()
    (vendored / "handoffs" / "2026-08-30-1100-vendored.md").write_text(
        "# Handoff — 2026-08-30\n\nsession_id: x\npurpose: foreign\n"
        f"items: {item_id}\nformat: fond-v1\n"
    )
    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton" not in result.stdout


def test_nonconforming_names_rank_by_mtime_not_sentinel(bon_dir, monkeypatch):
    """A drifted filename/title must not hand a STALE handoff the confident
    'last session' label — mtime replaces the 0000 sentinels."""
    import os as _os
    import time as _time
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    hdir = bon_dir / "handoffs"
    hdir.mkdir(exist_ok=True)
    old = hdir / "2026-08-30-0900-morning1.md"
    old.write_text(f"# Handoff — 2026-08-30\n\npurpose: STALE morning pass\nitems: {item_id}\n")
    new = hdir / "evening-wrap.md"  # no v4 HHMM, nonconforming title
    new.write_text(f"# Campaign close — 2026-08-30\n\npurpose: the real latest\nitems: {item_id}\n")
    now = _time.time()
    _os.utime(old, (now - 7200, now - 7200))
    _os.utime(new, (now, now))
    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "the real latest" in result.stdout
    assert "STALE" not in result.stdout


def test_items_line_past_800_bytes_is_still_read(bon_dir, monkeypatch):
    """A long purpose line must not push the citation out of the head read
    (a real 1,232-byte metadata block exists in the estate)."""
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    hdir = bon_dir / "handoffs"
    hdir.mkdir(exist_ok=True)
    long_purpose = "p" * 900
    (hdir / "2026-08-30-1100-deadbeef.md").write_text(
        f"# Handoff — 2026-08-30\n\nsession_id: x\npurpose: {long_purpose}\n"
        f"items: {item_id}\nformat: fond-v1\n"
    )
    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton (2026-08-30)" in result.stdout


def test_wrapped_items_line_is_still_read(bon_dir, monkeypatch):
    """A continuation line under items: (a plausible LLM rendering of a long
    list) still counts as cited."""
    monkeypatch.chdir(bon_dir)
    item_id = _seed_item(bon_dir)
    hdir = bon_dir / "handoffs"
    hdir.mkdir(exist_ok=True)
    others = ", ".join(f"bon-filler{i:02d}" for i in range(12))
    (hdir / "2026-08-30-1100-deadbeef.md").write_text(
        "# Handoff — 2026-08-30\n\nsession_id: x\npurpose: p\n"
        f"items: {others},\n  {item_id}\n"
        "format: fond-v1\n"
    )
    result = run_bon("work", item_id, cwd=bon_dir)
    assert result.returncode == 0, result.stderr
    assert "Baton (2026-08-30)" in result.stdout
