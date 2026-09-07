"""The same opening collector can be used without Claude state or project writes."""

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "open-context.sh"


def snapshot(root):
    """Include the Git index, legacy handoffs, cache files and empty directories."""
    return {
        str(path.relative_to(root)): (
            path.lstat().st_mode,
            path.read_bytes() if path.is_file() else None,
        )
        for path in root.rglob("*")
    }


@pytest.fixture
def estate(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    repo = home / "repo with spaces"
    (repo / ".bon").mkdir(parents=True)
    (repo / ".bon/prefix").write_text("test")
    (repo / ".bon/items.jsonl").write_text("")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    room = repo / "work/room"
    room.mkdir(parents=True)
    (room / "understanding.md").write_text("Room knowledge; read this separately.")
    return home, repo, room


def handoff(directory, name, purpose="Resume this work"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"purpose: {purpose}\n# Handoff — {name[:10]}\n")
    return path


def collect(estate, target=None, *args, bin_dir=None):
    home, _, room = estate
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    if bin_dir:
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
    before = snapshot(home)
    result = subprocess.run(
        ["bash", str(SCRIPT), "--read-only", *args, str(target or room)],
        cwd=home, env=env, capture_output=True, text=True, timeout=20,
    )
    assert snapshot(home) == before, "Read-only arrival mutated the estate"
    return result


def test_arrival_from_home_preserves_legacy_index_ledger_and_cache(estate):
    home, repo, room = estate
    (room / "AGENTS.md").write_text("Room instructions")
    (room / "START_HERE.md").write_text("Current routing")
    current = handoff(room / "handoffs", "2026-09-07-1200-room.md")
    (current.parent / "LEDGER.md").write_text(f"- [ ] 2026-09-07 [{current.name}]({current.name})\n")
    handoff(repo / ".bon/handoffs", "2026-09-06-1100-legacy.md")
    cache = home / ".claude/.session-context/old/bon.txt"
    cache.parent.mkdir(parents=True)
    cache.write_text("Preserve existing runtime state")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    result = collect(estate)
    assert result.returncode == 0, result.stderr
    for field, value in (
        ("LAUNCH_DIR", home), ("SELECTED_DIR", room), ("BOARD_ROOT", repo),
        ("REPOSITORY", repo), ("UNDERSTANDING", room / "understanding.md"),
        ("HANDOFF", current), ("LEDGER", current.parent / "LEDGER.md"),
    ):
        assert f"{field}={value}\n" in result.stdout
    assert f"READ_SOURCE={room / 'AGENTS.md'}" in result.stdout
    assert "LEGACY_HANDOFF_DIR=" in result.stdout
    assert "processing remains pending" in result.stdout
    assert "Migrated" not in result.stdout
    assert "BOARD_READ=ok (no items" in result.stdout


def test_nearest_scope_does_not_select_newer_foreign_handoff(estate):
    home, repo, room = estate
    current = handoff(room / "handoffs", "2026-09-01-1200-room.md")
    root = handoff(repo / "handoffs", "2026-09-02-1200-root.md", "Root baton")
    foreign = handoff(home / ".bon/handoffs", "2026-09-03-1200-global.md", "FOREIGN CONTENT")
    result = collect(estate)
    assert result.returncode == 0, result.stderr
    assert f"HANDOFF={current}\n" in result.stdout
    assert f"OTHER_HANDOFF_DIR={root.parent}" in result.stdout
    assert f"OTHER_HANDOFF_DIR={foreign.parent}" in result.stdout
    assert "FOREIGN CONTENT" not in result.stdout
    board = collect(estate, None, "--scope", "board")
    assert board.returncode == 0, board.stderr
    assert f"HANDOFF={root}\n" in board.stdout
    assert "FOREIGN CONTENT" not in board.stdout


def test_pending_unlisted_and_broken_ledger_entries_are_visible(estate):
    _, _, room = estate
    older = handoff(room / "handoffs", "2026-09-07-1100-old.md")
    newer = handoff(room / "handoffs", "2026-09-07-1200-new.md")
    orphan = handoff(room / "handoffs", "2026-09-07-1130-orphan.md")
    (room / "handoffs/LEDGER.md").write_text(
        f"- [ ] today [new]({newer.name})\n"
        f"- [ ] today [old]({older.name})\n"
        "- [ ] today [missing](gone.md)\n"
        "* [ ] unparseable line\n"
    )
    result = collect(estate)
    assert result.returncode == 0, result.stderr
    positions = [result.stdout.index(f"UNPROCESSED={p}") for p in (older, orphan, newer)]
    assert positions == sorted(positions)
    assert "[no ledger line" in result.stdout
    assert "files that no longer exist" in result.stdout
    assert "format the sweep cannot parse" in result.stdout


def test_empty_scope_does_not_abort_or_invent_a_baton(estate):
    _, _, room = estate
    (room / "handoffs").mkdir()
    result = collect(estate)
    assert result.returncode == 0, result.stderr
    assert "HANDOFF=none found in selected scope" in result.stdout
    assert "TACTICAL=none reported" in result.stdout
    assert "Nothing in progress" not in result.stdout


def test_preview_budgets_report_omissions_and_retain_source_paths(estate):
    _, repo, room = estate
    entries = []
    for i in range(9):
        path = handoff(room / "handoffs", f"2026-09-07-12{i:02d}-item.md", "p" * 20000)
        entries.append(f"- [ ] today [{path.name}]({path.name})\n")
    (room / "handoffs/LEDGER.md").write_text("".join(entries))
    items = [
        {"id": f"test-{i}", "type": "action", "title": "x" * 10000, "status": "open"}
        for i in range(20)
    ]
    (repo / ".bon/items.jsonl").write_text("\n".join(map(json.dumps, items)))
    result = collect(estate)
    assert result.returncode == 0, result.stderr
    assert "preview shortened" in result.stdout
    assert "+8 more" in result.stdout
    assert "+3 more" in result.stdout
    assert f"LEDGER={room / 'handoffs/LEDGER.md'}" in result.stdout
    assert len(result.stdout.encode()) < 12000


def test_failed_dolt_reads_are_not_reported_as_empty_or_service_outage(estate):
    home, repo, room = estate
    (repo / ".bon/backend").write_text("dolt")
    handoff(room / "handoffs", "2026-09-07-1200-readable.md")
    fake_bin = home / "bin"
    fake_bin.mkdir()
    fake = fake_bin / "bon"
    fake.write_text(
        "#!/bin/sh\n"
        '[ "$BON_SKIP_SCHEMA_INIT" = 1 ] || exit 88\n'
        '[ -f "$PYTHONPATH/bon/dolt.py" ] || exit 89\n'
        "echo 'transport failed' >&2\nexit 17\n"
    )
    fake.chmod(0o755)
    result = collect(estate, bin_dir=fake_bin)
    assert result.returncode == 1
    assert "BOARD_READ_FAILED:" in result.stdout
    assert "exit 17" in result.stdout
    assert "TACTICAL=unknown" in result.stdout
    assert "BOARD_READ=ok" not in result.stdout
    assert "systemctl" not in result.stdout
    assert "HANDOFF=" in result.stdout


def test_dolt_without_cli_reports_unavailable_reader(estate):
    _, repo, _ = estate
    (repo / ".bon/backend").write_text("dolt")
    result = collect(estate)
    assert result.returncode == 1
    assert "Board reader unavailable" in result.stdout


def test_invalid_target_and_scope_fail_without_writes(estate):
    home, _, _ = estate
    assert collect(estate, home / "missing").returncode != 0
    assert collect(estate, None, "--scope", "unknown").returncode == 2


def test_rank_uses_header_and_filename_even_after_checkout_flattens_mtime(estate):
    _, _, room = estate
    older = handoff(room / "handoffs", "2026-09-07-1100-old.md")
    newer = handoff(room / "handoffs", "2026-09-07-1200-new.md")
    os.utime(older, (2000000000, 2000000000))
    os.utime(newer, (1000000000, 1000000000))
    result = collect(estate)
    assert result.returncode == 0, result.stderr
    assert f"HANDOFF={newer}\n" in result.stdout
