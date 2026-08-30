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
