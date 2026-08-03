"""
Tests for scripts/close-context.sh — the values /close writes a handoff from.

Three regressions are anchored here, all of them silent in production:

bon-casovo — SESSION_ID was derived with `ls -t` over the project's JSONL dir,
which returns whoever WROTE most recently. That is a race readout, not an
identity: it handed four sessions a stranger's id in nine days and escaped
destroying a completed handoff three times by luck. The id suffix exists FOR
transcript linkage, so a wrong id is worse than no id — it sends a future
lookup confidently into the wrong conversation. Reproduced live 2026-08-03 with
two concurrent sessions in this repo: both computed 2026-08-03-248babd0.md.

bon-suvise — the container scan-down globbed downward into vendored plugin
clones, so /close from a boardless repo resolved HANDOFF_DIR into
plugins/marketplaces/trousse-personal/.bon/handoffs: gitignored cache that
marketplace sync clobbers.

bon-kizeje — a repo that gitignores `.bon/` wholesale also ignores its
handoffs, so `git add` refuses and the handoff never syncs. Observed in
mit-plongeur, whose 13 handoffs are all force-added by hand.
"""

import subprocess
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CLOSE_CONTEXT = REPO_ROOT / "scripts" / "close-context.sh"

TODAY = date.today().strftime("%Y-%m-%d")


def run_close(cwd: Path, home: Path, session_id: str | None = "abcd1234-1111-2222-3333-444444444444") -> dict:
    """Run close-context.sh from `cwd` and parse its KEY=value output.

    HOME is isolated so the global ~/.bon/handoffs fallback can't reach the
    machine's real handoffs. `session_id=None` simulates a harness that does
    not export CLAUDE_CODE_SESSION_ID.
    """
    env = {
        "HOME": str(home),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
    }
    if session_id is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session_id
    result = subprocess.run(
        ["bash", str(CLOSE_CONTEXT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )
    parsed = {}
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, _, value = line.partition("=")
            parsed[key] = value
    parsed["_stdout"] = result.stdout
    parsed["_returncode"] = result.returncode
    return parsed


def make_board_repo(root: Path, *, prefix: str = "test", commit: bool = True) -> Path:
    """A git repo carrying a .bon board with a prefix marker."""
    (root / ".bon").mkdir(parents=True, exist_ok=True)
    (root / ".bon" / "prefix").write_text(f"{prefix}\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    if commit:
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "--allow-empty", "-m", "seed"],
            cwd=root, check=True,
        )
    return root


# --- bon-casovo: session identity ------------------------------------------

def test_session_id_comes_from_the_harness(tmp_path):
    """The id is the caller's own, taken from CLAUDE_CODE_SESSION_ID."""
    repo = make_board_repo(tmp_path / "repo")
    out = run_close(repo, tmp_path / "home", session_id="feedface-9999-8888-7777-666666666666")
    assert out["SESSION_ID"] == "feedface-9999-8888-7777-666666666666"
    assert out["SESSION_ID_SOURCE"] == "env:CLAUDE_CODE_SESSION_ID"
    assert out["HANDOFF_FILE"] == f"{TODAY}-feedface.md"


def test_concurrent_sessions_get_distinct_filenames(tmp_path):
    """The regression itself: two sessions, one repo, two filenames.

    Under `ls -t` both runs saw whichever transcript was written last and
    computed the SAME name, so the second /close overwrote the first.
    """
    repo = make_board_repo(tmp_path / "repo")
    home = tmp_path / "home"
    a = run_close(repo, home, session_id="aaaaaaaa-1111-1111-1111-111111111111")
    b = run_close(repo, home, session_id="bbbbbbbb-2222-2222-2222-222222222222")
    assert a["HANDOFF_FILE"] == f"{TODAY}-aaaaaaaa.md"
    assert b["HANDOFF_FILE"] == f"{TODAY}-bbbbbbbb.md"
    assert a["HANDOFF_FILE"] != b["HANDOFF_FILE"]


def test_missing_session_id_fails_loud_rather_than_guessing(tmp_path):
    """No id available: say so, and fall back to a timestamp filename."""
    repo = make_board_repo(tmp_path / "repo")
    out = run_close(repo, tmp_path / "home", session_id=None)
    assert out["SESSION_ID"] == ""
    assert out["SESSION_ID_SOURCE"] == "unavailable"
    assert "SESSION_ID_CUE" in out, "an absent id must announce itself, not pass silently"
    assert "do not invent" in out["SESSION_ID_CUE"].lower()
    # Timestamp form: YYYY-MM-DD-HHMM.md — four digits, never a hex-looking id
    assert out["HANDOFF_FILE"].startswith(f"{TODAY}-")
    suffix = out["HANDOFF_FILE"].removeprefix(f"{TODAY}-").removesuffix(".md")
    assert suffix.isdigit() and len(suffix) == 4


def test_missing_session_id_never_borrows_an_ambient_one(tmp_path):
    """A neighbouring transcript must not be adopted as this session's id.

    Plants a JSONL exactly where the old `ls -t` derivation looked.
    """
    repo = make_board_repo(tmp_path / "repo")
    home = tmp_path / "home"
    encoded = str(repo).replace("/", "-").replace("_", "-").replace(".", "-")
    projdir = home / ".claude" / "projects" / encoded
    projdir.mkdir(parents=True)
    (projdir / "deadbeef-0000-0000-0000-000000000000.jsonl").write_text("{}\n")

    out = run_close(repo, home, session_id=None)
    assert "deadbeef" not in out["HANDOFF_FILE"]
    assert out["SESSION_ID"] == ""


# --- bon-casovo: the clobber guard -----------------------------------------

def test_existing_handoff_is_never_overwritten(tmp_path):
    """A computed path that already exists gets suffixed, and says so."""
    repo = make_board_repo(tmp_path / "repo")
    handoffs = repo / ".bon" / "handoffs"
    handoffs.mkdir(parents=True)
    (handoffs / f"{TODAY}-abcd1234.md").write_text("an earlier handoff\n")

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_FILE_TAKEN"] == f"{TODAY}-abcd1234.md"
    assert out["HANDOFF_FILE"] == f"{TODAY}-abcd1234-2.md"
    assert (handoffs / f"{TODAY}-abcd1234.md").read_text() == "an earlier handoff\n"


def test_clobber_guard_finds_the_next_free_suffix(tmp_path):
    repo = make_board_repo(tmp_path / "repo")
    handoffs = repo / ".bon" / "handoffs"
    handoffs.mkdir(parents=True)
    for name in (f"{TODAY}-abcd1234.md", f"{TODAY}-abcd1234-2.md", f"{TODAY}-abcd1234-3.md"):
        (handoffs / name).write_text("x\n")

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_FILE"] == f"{TODAY}-abcd1234-4.md"


def test_no_collision_reported_when_the_path_is_free(tmp_path):
    repo = make_board_repo(tmp_path / "repo")
    (repo / ".bon" / "handoffs").mkdir(parents=True)
    out = run_close(repo, tmp_path / "home")
    assert "HANDOFF_FILE_TAKEN" not in out
    assert out["HANDOFF_FILE"] == f"{TODAY}-abcd1234.md"


# --- bon-suvise: never route a handoff into a plugin cache -----------------

def _vendored_plugin_board(container: Path, *, newer: bool = False) -> Path:
    """A vendored marketplace clone carrying its own .bon board."""
    vendored = container / "plugins" / "marketplaces" / "trousse-personal"
    (vendored / ".bon").mkdir(parents=True)
    (vendored / ".bon" / "prefix").write_text("trousse\n")
    subprocess.run(["git", "init", "-q"], cwd=vendored, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "--allow-empty", "-m", "newer" if newer else "seed"],
        cwd=vendored, check=True,
    )
    return vendored


def test_scan_down_skips_vendored_plugin_boards(tmp_path):
    """A boardless repo full of plugin clones must not adopt one of them."""
    container = tmp_path / "host"
    container.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=container, check=True)
    _vendored_plugin_board(container)

    out = run_close(container, tmp_path / "home")
    assert "plugins/marketplaces" not in out["HANDOFF_DIR"]
    assert out["HANDOFF_DIR_SOURCE"] == "global-fallback"


def test_scan_down_still_finds_a_real_child_repo(tmp_path):
    """Positive control: the legitimate container case keeps working."""
    container = tmp_path / "container"
    container.mkdir()
    real = make_board_repo(container / "realrepo")

    out = run_close(container, tmp_path / "home")
    assert out["HANDOFF_DIR"] == str(real / ".bon" / "handoffs")
    assert out["HANDOFF_DIR_SOURCE"] == f"scan-down:{real}"


def test_a_newer_plugin_board_still_loses_to_a_real_repo(tmp_path):
    """The prune excludes it, not commit-recency.

    Without this the previous test could pass by accident whenever the real
    repo happened to have the more recent commit.
    """
    container = tmp_path / "container"
    container.mkdir()
    real = make_board_repo(container / "realrepo")
    _vendored_plugin_board(container, newer=True)

    out = run_close(container, tmp_path / "home")
    assert out["HANDOFF_DIR"] == str(real / ".bon" / "handoffs")


# --- bon-kizeje: a gitignored .bon/ swallows the handoff -------------------

def test_gitignored_handoff_is_flagged_with_a_force_add(tmp_path):
    repo = make_board_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".bon/\n")

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_GITIGNORED"] == "true"
    assert out["HANDOFF_ADD_CMD"].startswith("git add -f -- ")
    assert out["HANDOFF_FILE"] in out["HANDOFF_ADD_CMD"]


def test_tracked_handoff_dir_is_not_flagged(tmp_path):
    """Negative control — the flag must not fire on an ordinary repo."""
    repo = make_board_repo(tmp_path / "repo")
    out = run_close(repo, tmp_path / "home")
    assert "HANDOFF_GITIGNORED" not in out
    assert "HANDOFF_ADD_CMD" not in out


def test_visible_handoffs_dir_outside_bon_is_not_flagged(tmp_path):
    """A repo ignoring .bon/ but writing to a VISIBLE handoffs/ is fine."""
    repo = make_board_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".bon/\n")
    (repo / "handoffs").mkdir()

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_DIR"] == str(repo / "handoffs")
    assert "HANDOFF_GITIGNORED" not in out
