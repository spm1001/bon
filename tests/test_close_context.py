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

bon-sedoze — `.bon/handoffs` retired as a resolution rung. close-context.sh
converges any pile still sitting there before it resolves, and the
HANDOFF_GITIGNORED / HANDOFF_ADD_CMD force-add probe that bon-kizeje added for
the wholesale-`.bon/`-ignore case is gone with it: handoffs no longer live
under `.bon/`, so that shape cannot arise. (bon doctor still advises on the
artefacts that DO remain there — understanding.md, the bottle, a JSONL board.)
"""

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
CLOSE_CONTEXT = REPO_ROOT / "scripts" / "close-context.sh"

TODAY = date.today().strftime("%Y-%m-%d")


def run_close(cwd: Path, home: Path, session_id: str | None = "abcd1234-1111-2222-3333-444444444444", now_hm: str = "1200") -> dict:
    """Run close-context.sh from `cwd` and parse its KEY=value output.

    HOME is isolated so the global ~/.bon/handoffs fallback can't reach the
    machine's real handoffs. `session_id=None` simulates a harness that does
    not export CLAUDE_CODE_SESSION_ID. `now_hm` pins the minute the filename
    carries (v4 scheme) so expectations aren't a race against the wall clock.
    """
    env = {
        "HOME": str(home),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "BON_TEST_NOW_HM": now_hm,
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
    assert out["HANDOFF_FILE"] == f"{TODAY}-1200-feedface.md"


def test_concurrent_sessions_get_distinct_filenames(tmp_path):
    """The regression itself: two sessions, one repo, two filenames.

    Under `ls -t` both runs saw whichever transcript was written last and
    computed the SAME name, so the second /close overwrote the first.
    """
    repo = make_board_repo(tmp_path / "repo")
    home = tmp_path / "home"
    a = run_close(repo, home, session_id="aaaaaaaa-1111-1111-1111-111111111111")
    b = run_close(repo, home, session_id="bbbbbbbb-2222-2222-2222-222222222222")
    assert a["HANDOFF_FILE"] == f"{TODAY}-1200-aaaaaaaa.md"
    assert b["HANDOFF_FILE"] == f"{TODAY}-1200-bbbbbbbb.md"
    assert a["HANDOFF_FILE"] != b["HANDOFF_FILE"]


def test_same_day_handoffs_sort_chronologically_under_ls(tmp_path):
    """notes-sovike: within a day the v3 sort key was the random id8, so the
    SUPERSEDED handoff could sort last and hand a routing session the stale
    frame (2026-07-31, sky-transaction). The v4 HHMM makes a plain sorted
    listing chronological — ids chosen here so v3 would have inverted it.
    """
    repo = make_board_repo(tmp_path / "repo")
    home = tmp_path / "home"
    first = run_close(repo, home, session_id="zzzzzzzz-1111-1111-1111-111111111111", now_hm="0901")
    second = run_close(repo, home, session_id="aaaaaaaa-2222-2222-2222-222222222222", now_hm="1813")
    listing = sorted([first["HANDOFF_FILE"], second["HANDOFF_FILE"]])
    assert listing == [f"{TODAY}-0901-zzzzzzzz.md", f"{TODAY}-1813-aaaaaaaa.md"], (
        "newest must sort last under a plain ls"
    )
    # The v3 names for the same pair would have sorted stale-last:
    assert sorted([f"{TODAY}-zzzzzzzz.md", f"{TODAY}-aaaaaaaa.md"])[-1] == f"{TODAY}-zzzzzzzz.md"


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
    handoffs = repo / "handoffs"
    handoffs.mkdir(parents=True)
    (handoffs / f"{TODAY}-1200-abcd1234.md").write_text("an earlier handoff\n")

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_FILE_TAKEN"] == f"{TODAY}-1200-abcd1234.md"
    assert out["HANDOFF_FILE"] == f"{TODAY}-1200-abcd1234-2.md"
    assert (handoffs / f"{TODAY}-1200-abcd1234.md").read_text() == "an earlier handoff\n"


def test_clobber_guard_counts_migrated_handoffs_too(tmp_path):
    """Seeded at the RETIRED location on purpose: the migration runs first, so
    by the time the clobber guard looks, all three are in the visible dir and
    it must count them. Seed and guard talk to different paths — this is the
    test that would catch a migration wired in AFTER resolution."""
    repo = make_board_repo(tmp_path / "repo")
    legacy = repo / ".bon" / "handoffs"
    legacy.mkdir(parents=True)
    for name in (f"{TODAY}-1200-abcd1234.md", f"{TODAY}-1200-abcd1234-2.md", f"{TODAY}-1200-abcd1234-3.md"):
        (legacy / name).write_text("x\n")

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_MIGRATED"] == "3"
    assert out["HANDOFF_FILE"] == f"{TODAY}-1200-abcd1234-4.md"


def test_no_collision_reported_when_the_path_is_free(tmp_path):
    repo = make_board_repo(tmp_path / "repo")
    (repo / "handoffs").mkdir(parents=True)
    out = run_close(repo, tmp_path / "home")
    assert "HANDOFF_FILE_TAKEN" not in out
    assert out["HANDOFF_FILE"] == f"{TODAY}-1200-abcd1234.md"


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
    assert out["HANDOFF_DIR"] == str(real / "handoffs")
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
    assert out["HANDOFF_DIR"] == str(real / "handoffs")


# --- bon-gojeni: never silently pick among legitimate siblings --------------

def test_two_sibling_repos_is_ambiguous(tmp_path):
    """An owner bucket with two board repos gets candidates, not a choice.

    The old rule was most-recent-commit-wins, which is estate noise: the live
    repro resolved to whichever sibling the last publish had touched.
    """
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    a = make_board_repo(bucket / "repo-a")
    b = make_board_repo(bucket / "repo-b")

    out = run_close(bucket, tmp_path / "home")
    assert out["HANDOFF_DIR_SOURCE"] == "ambiguous"
    assert "HANDOFF_DIR" not in out
    assert f"HANDOFF_CANDIDATE={a}" in out["_stdout"]
    assert f"HANDOFF_CANDIDATE={b}" in out["_stdout"]
    assert "work" in out.get("HANDOFF_HINT", "").lower()


def test_ambiguous_still_names_the_handoff_file(tmp_path):
    """The filename is dir-independent, so the Claude still gets it."""
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    make_board_repo(bucket / "repo-a")
    make_board_repo(bucket / "repo-b")

    out = run_close(bucket, tmp_path / "home")
    assert out["HANDOFF_FILE"] == f"{TODAY}-1200-abcd1234.md"


def test_ambiguous_does_not_fall_through_to_global(tmp_path):
    """The candidates ARE the answer — global-fallback would bury them."""
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    make_board_repo(bucket / "repo-a")
    make_board_repo(bucket / "repo-b")

    out = run_close(bucket, tmp_path / "home")
    assert out["HANDOFF_DIR_SOURCE"] == "ambiguous"
    assert "HANDOFF_DIR" not in out, "no dir is chosen — emitting one relocates the trap"


def test_vendored_board_does_not_create_ambiguity(tmp_path):
    """One real repo + one pruned plugin clone is still a SINGLE candidate."""
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    real = make_board_repo(bucket / "realrepo")
    _vendored_plugin_board(bucket, newer=True)

    out = run_close(bucket, tmp_path / "home")
    assert out["HANDOFF_DIR"] == str(real / "handoffs")
    assert out["HANDOFF_DIR_SOURCE"] == f"scan-down:{real}"


# --- bon-sedoze: the force-add probe is gone, the migration is not ----------

def test_force_add_probe_is_retired(tmp_path):
    """The kizeje shape — a repo gitignoring `.bon/` wholesale — no longer
    reaches the handoff, because the handoff no longer lands under `.bon/`.
    Both keys must be absent, including on the repo that used to trigger them."""
    repo = make_board_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text(".bon/\n")

    out = run_close(repo, tmp_path / "home")
    assert out["HANDOFF_DIR"] == str(repo / "handoffs")
    assert "HANDOFF_GITIGNORED" not in out
    assert "HANDOFF_ADD_CMD" not in out


def test_ordinary_repo_emits_no_force_add_keys(tmp_path):
    repo = make_board_repo(tmp_path / "repo")
    out = run_close(repo, tmp_path / "home")
    assert "HANDOFF_GITIGNORED" not in out
    assert "HANDOFF_ADD_CMD" not in out


def test_close_converges_a_legacy_pile_and_says_so(tmp_path):
    """A consumer whose next contact with bon is a CLOSE rather than an open
    still gets migrated — /open is not the only door."""
    repo = make_board_repo(tmp_path / "repo")
    legacy = repo / ".bon" / "handoffs"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "2026-08-20-0930-ccccdddd.md").write_text(
        "# Handoff — 2026-08-20\n\nsession_id: x\npurpose: residue\nformat: fond-v1\n"
    )

    out = run_close(repo, tmp_path / "home")

    assert out["HANDOFF_MIGRATED"] == "1"
    assert out["HANDOFF_MIGRATED_DEST"] == str(repo / "handoffs")
    assert "HANDOFF_MIGRATE_INCOMPLETE" not in out
    assert (repo / "handoffs" / "2026-08-20-0930-ccccdddd.md").exists()
    # And the handoff this close is about to write lands beside it.
    assert out["HANDOFF_DIR"] == str(repo / "handoffs")


def test_scan_down_migrates_the_child_it_resolves_into(tmp_path):
    """cwd is an owner bucket ABOVE the board, so the walk-UP migration never
    reaches it. Without a second call the close writes into the child's visible
    handoffs/ while the child's old pile stays stranded where nothing reads."""
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    real = make_board_repo(bucket / "realrepo")
    legacy = real / ".bon" / "handoffs"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "2026-08-20-0930-ccccdddd.md").write_text(
        "# Handoff — 2026-08-20\n\nsession_id: x\npurpose: residue\nformat: fond-v1\n"
    )

    out = run_close(bucket, tmp_path / "home")

    assert out["HANDOFF_DIR_SOURCE"] == f"scan-down:{real}"
    assert out["HANDOFF_MIGRATED"] == "1"
    assert (real / "handoffs" / "2026-08-20-0930-ccccdddd.md").exists()
    assert not (real / ".bon" / "handoffs").exists()


def test_ambiguous_migrates_nothing(tmp_path):
    """Refusing to pick a repo means refusing to move one's files around."""
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    for name in ("repo-a", "repo-b"):
        repo = make_board_repo(bucket / name)
        legacy = repo / ".bon" / "handoffs"
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "h.md").write_text("# Handoff — 2026-08-20\n\npurpose: residue\n")

    out = run_close(bucket, tmp_path / "home")

    assert out["HANDOFF_DIR_SOURCE"] == "ambiguous"
    assert "HANDOFF_MIGRATED" not in out
    for name in ("repo-a", "repo-b"):
        assert (bucket / name / ".bon" / "handoffs" / "h.md").exists()


def test_clean_repo_emits_no_migration_keys(tmp_path):
    """Negative control — the keys must not fire on a repo with no residue."""
    repo = make_board_repo(tmp_path / "repo")
    out = run_close(repo, tmp_path / "home")
    assert "HANDOFF_MIGRATED" not in out
    assert "HANDOFF_MIGRATE_INCOMPLETE" not in out


# ---------- board motion (bon-racafo) ----------
#
# Closed-versus-minted since the previous close, DERIVED by the script rather
# than narrated by the closing Claude — the card's falsifier is evasive
# behaviour when nobody is watching, and an agent cannot inflate a count it
# did not compute. These tests pin the window arithmetic, the carried
# residual, and the two guards on the re-runnable path.

def _stub_bon(home: Path, events: list[dict]) -> None:
    """Put a fake `bon` on PATH that answers `log --json` with `events`.

    A stub rather than a real board because the window arithmetic is what is
    under test, and real timestamps would make the expectations a race.
    """
    bindir = home / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(events)
    stub = bindir / "bon"
    stub.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = "log" ]; then\n'
        f"  cat <<'JSONEOF'\n{payload}\nJSONEOF\n"
        "  exit 0\n"
        "fi\n"
        'echo "○ stub board"\n'
    )
    stub.chmod(0o755)


def _ev(verb: str, ident: str, time: str) -> dict:
    return {"time": time, "verb": verb, "id": ident, "title": ident, "type": "action"}


def _run_close_with_bon(cwd: Path, home: Path, **kw) -> dict:
    """run_close, but with the stub bin dir ahead of the isolated PATH.

    TZ is pinned to UTC by default so the window's local-to-UTC conversion is
    a no-op and these expectations mean what they say on any machine. The
    conversion itself is exercised under a real zone in TestBoardMotionTimezone
    — keeping the two concerns apart is what stopped this suite noticing that
    the boundary was an hour out for half the year.
    """
    env = {
        "HOME": str(home),
        "PATH": f"{home}/bin:/usr/local/bin:/usr/bin:/bin",
        "TZ": kw.get("tz", "UTC"),
        "BON_TEST_NOW_HM": kw.get("now_hm", "1200"),
        "CLAUDE_CODE_SESSION_ID": "abcd1234-1111-2222-3333-444444444444",
    }
    result = subprocess.run(
        ["bash", str(CLOSE_CONTEXT)],
        capture_output=True, text=True, cwd=cwd, env=env,
    )
    parsed = {}
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, _, value = line.partition("=")
            parsed[key] = value
    parsed["_stdout"] = result.stdout
    return parsed


def _board(tmp_path: Path) -> tuple[Path, Path]:
    """A repo with a board and a handoffs dir, plus an isolated HOME."""
    home = tmp_path / "home"
    home.mkdir()
    repo = tmp_path / "repo"
    (repo / ".bon").mkdir(parents=True)
    (repo / ".bon" / "prefix").write_text("bon\n")
    (repo / "handoffs").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo, home


class TestBoardMotionWindow:
    def test_window_comes_from_the_newest_handoff_filename_with_hhmm(self, tmp_path):
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-30-2318-fb49cab3.md").write_text("# Handoff\n")
        (repo / "handoffs" / "2026-08-12-0900-aaaaaaaa.md").write_text("# Handoff\n")
        _stub_bon(home, [])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_SINCE"].startswith("2026-08-30T23:18:00")
        assert "2026-08-30-2318-fb49cab3.md" in out["MOTION_SINCE"]

    def test_old_format_filename_falls_back_to_that_day_start(self, tmp_path):
        # Pre-supuko handoffs carry no HHMM, so the honest window is the day.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-08-599066b2.md").write_text("# Handoff\n")
        _stub_bon(home, [])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_SINCE"].startswith("2026-08-08T00:00:00")

    def test_no_dated_handoff_falls_back_to_24h_and_says_so(self, tmp_path):
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "fond-seed.md").write_text("# Handoff\n")
        _stub_bon(home, [])
        out = _run_close_with_bon(repo, home)
        assert "last 24h" in out["MOTION_SINCE"]
        assert "not this session" in out["MOTION_SINCE"]

    def test_undated_files_never_outrank_a_dated_one(self, tmp_path):
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-30-2318-fb49cab3.md").write_text("# Handoff\n")
        (repo / "handoffs" / "zzz-undated.md").write_text("# Handoff\n")
        (repo / "handoffs" / "LEDGER.md").write_text("# ledger\n")
        _stub_bon(home, [])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_SINCE"].startswith("2026-08-30T23:18:00")


class TestBoardMotionCounts:
    def _repo_with_events(self, tmp_path, events):
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-30-2318-fb49cab3.md").write_text("# Handoff\n")
        _stub_bon(home, events)
        return repo, home

    def test_counts_and_ids_inside_the_window(self, tmp_path):
        repo, home = self._repo_with_events(tmp_path, [
            _ev("completed", "bon-aaa", "2026-08-31T09:00:00Z"),
            _ev("created", "bon-bbb", "2026-08-31T09:30:00Z"),
            _ev("completed", "bon-ccc", "2026-08-31T10:00:00Z"),
        ])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_CLOSED"] == "2 bon-aaa, bon-ccc"
        assert out["MOTION_MINTED"] == "1 bon-bbb"
        assert out["MOTION_CARRIED"] == "1 bon-bbb"

    def test_events_before_the_window_are_excluded(self, tmp_path):
        # The known-bad arm: an event just before the boundary must not count.
        repo, home = self._repo_with_events(tmp_path, [
            _ev("completed", "bon-old", "2026-08-30T23:17:59Z"),
            _ev("completed", "bon-new", "2026-08-30T23:18:01Z"),
        ])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_CLOSED"] == "1 bon-new"

    def test_minted_and_closed_in_window_is_not_carried(self, tmp_path):
        # The residual that stops a mint-and-close reading as board growth.
        repo, home = self._repo_with_events(tmp_path, [
            _ev("created", "bon-same", "2026-08-31T09:00:00Z"),
            _ev("completed", "bon-same", "2026-08-31T09:05:00Z"),
            _ev("created", "bon-kept", "2026-08-31T09:10:00Z"),
        ])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_MINTED"] == "2 bon-kept, bon-same"
        assert out["MOTION_CARRIED"] == "1 bon-kept"

    def test_other_verbs_are_ignored(self, tmp_path):
        repo, home = self._repo_with_events(tmp_path, [
            _ev("stepped", "bon-aaa", "2026-08-31T09:00:00Z"),
            _ev("edited", "bon-bbb", "2026-08-31T09:00:00Z"),
            _ev("waited", "bon-ccc", "2026-08-31T09:00:00Z"),
        ])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_CLOSED"] == "0"
        assert out["MOTION_MINTED"] == "0"

    def test_empty_window_reports_zeroes_not_silence(self, tmp_path):
        repo, home = self._repo_with_events(tmp_path, [])
        out = _run_close_with_bon(repo, home)
        assert out["MOTION_CLOSED"] == "0"
        assert out["MOTION_CARRIED"] == "0"

    def test_truncation_flag_stays_quiet_when_the_log_reaches_past_the_window(
        self, tmp_path
    ):
        # 500 events, but the oldest predates the window — nothing can be
        # hidden, so a cap warning here would be crying wolf.
        events = [_ev("completed", f"bon-{i}", "2026-08-31T09:00:00Z")
                  for i in range(499)]
        events.append(_ev("completed", "bon-old", "2026-01-01T00:00:00Z"))
        repo, home = self._repo_with_events(tmp_path, events)
        out = _run_close_with_bon(repo, home)
        assert "MOTION_TRUNCATED" not in out

    def test_truncation_flag_fires_when_the_oldest_event_is_still_in_window(
        self, tmp_path
    ):
        events = [_ev("completed", f"bon-{i}", "2026-08-31T09:00:00Z")
                  for i in range(500)]
        repo, home = self._repo_with_events(tmp_path, events)
        out = _run_close_with_bon(repo, home)
        assert out.get("MOTION_TRUNCATED", "").startswith("true")


class TestMotionOnly:
    def test_re_derives_for_a_supplied_window(self, tmp_path):
        repo, home = _board(tmp_path)
        _stub_bon(home, [_ev("created", "bon-late", "2026-08-31T11:00:00Z")])
        r = subprocess.run(
            ["bash", str(CLOSE_CONTEXT), "--motion-only", "2026-08-30T23:18:00"],
            capture_output=True, text=True, cwd=repo,
            env={"HOME": str(home), "PATH": f"{home}/bin:/usr/bin:/bin"},
        )
        assert r.returncode == 0
        assert "MOTION_MINTED=1 bon-late" in r.stdout
        assert "re-derived at summary time" in r.stdout

    def test_missing_window_argument_refuses(self, tmp_path):
        repo, home = _board(tmp_path)
        _stub_bon(home, [])
        r = subprocess.run(
            ["bash", str(CLOSE_CONTEXT), "--motion-only"],
            capture_output=True, text=True, cwd=repo,
            env={"HOME": str(home), "PATH": f"{home}/bin:/usr/bin:/bin"},
        )
        assert r.returncode == 2
        assert "MOTION_ERROR" in r.stdout

    def test_no_board_says_so_rather_than_reporting_zeroes(self, tmp_path):
        # Zeroes would read as "a quiet session"; this is "no board here".
        bare = tmp_path / "bare"
        bare.mkdir()
        home = tmp_path / "home"
        (home / "bin").mkdir(parents=True)
        r = subprocess.run(
            ["bash", str(CLOSE_CONTEXT), "--motion-only", "2026-08-30T23:18:00"],
            capture_output=True, text=True, cwd=bare,
            env={"HOME": str(home), "PATH": f"{home}/bin:/usr/bin:/bin"},
        )
        assert "MOTION_ERROR=no board found" in r.stdout
        assert "MOTION_CLOSED" not in r.stdout


def test_board_motion_absent_when_the_cli_is_missing(tmp_path):
    # The pre-existing harness has no bon on PATH; the block must stay silent
    # rather than emitting a zero tally the closing Claude would then report.
    repo, home = _board(tmp_path)
    (repo / "handoffs" / "2026-08-30-2318-fb49cab3.md").write_text("# Handoff\n")
    out = run_close(repo, home)
    assert "MOTION_CLOSED" not in out


class TestBoardMotionTimezone:
    """The window boundary comes from a handoff filename (LOCAL time) and the
    events from `bon log` (UTC). Compared as one clock they differ by the UTC
    offset: under BST the first hour of every window was dropped, and an item
    minted 30 minutes after the previous close reported MOTION_MINTED=0 live.

    The earlier tests could not catch this — they fabricate both the filename
    and the event stamps with no real clock relating them, so the boundary
    looked exact while live it was 3,600 seconds out. These pin a REAL
    conversion by running under a named zone.
    """

    def _run_tz(self, cwd: Path, home: Path, tz: str) -> dict:
        result = subprocess.run(
            ["bash", str(CLOSE_CONTEXT)],
            capture_output=True, text=True, cwd=cwd,
            env={
                "HOME": str(home),
                "PATH": f"{home}/bin:/usr/local/bin:/usr/bin:/bin",
                "TZ": tz,
                "BON_TEST_NOW_HM": "1200",
                "CLAUDE_CODE_SESSION_ID": "abcd1234-1111-2222-3333-444444444444",
            },
        )
        parsed = {}
        for line in result.stdout.splitlines():
            if "=" in line and not line.startswith("="):
                key, _, value = line.partition("=")
                parsed[key] = value
        return parsed

    def test_bst_boundary_converts_to_utc(self, tmp_path):
        # Handoff at 12:48 LOCAL on a BST date == 11:48 UTC.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-31-1248-deadbeef.md").write_text("# H\n")
        _stub_bon(home, [])
        out = self._run_tz(repo, home, "Europe/London")
        assert out["MOTION_SINCE"].startswith("2026-08-31T11:48:00")

    def test_the_live_repro_now_counts(self, tmp_path):
        # An item created at 12:18Z is 13:18 BST — half an hour AFTER a close
        # at 12:48 BST. It reported MOTION_MINTED=0 before the conversion.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-31-1248-deadbeef.md").write_text("# H\n")
        _stub_bon(home, [_ev("created", "bon-after", "2026-08-31T12:18:34Z")])
        out = self._run_tz(repo, home, "Europe/London")
        assert out["MOTION_MINTED"] == "1 bon-after"

    def test_an_event_genuinely_before_the_close_still_excluded(self, tmp_path):
        # The control the conversion must not break: 11:00Z is 12:00 BST,
        # genuinely before the 12:48 BST close, so it stays out.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-31-1248-deadbeef.md").write_text("# H\n")
        _stub_bon(home, [_ev("created", "bon-before", "2026-08-31T11:00:00Z")])
        out = self._run_tz(repo, home, "Europe/London")
        assert out["MOTION_MINTED"] == "0"

    def test_utc_zone_is_a_no_op(self, tmp_path):
        # Under UTC the conversion must change nothing — otherwise the fix
        # would be trading a BST bug for a GMT one.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-31-1248-deadbeef.md").write_text("# H\n")
        _stub_bon(home, [])
        out = self._run_tz(repo, home, "UTC")
        assert out["MOTION_SINCE"].startswith("2026-08-31T12:48:00")

    def test_undated_day_boundary_also_converts(self, tmp_path):
        # A pre-supuko filename means midnight LOCAL, which is 23:00Z the
        # previous day under BST — not 00:00Z.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-08-599066b2.md").write_text("# H\n")
        _stub_bon(home, [])
        out = self._run_tz(repo, home, "Europe/London")
        assert out["MOTION_SINCE"].startswith("2026-08-07T23:00:00")

    def test_unconvertible_timestamp_names_the_file_not_absence(self, tmp_path):
        # A DST-skipped local time (or a malformed name) fails conversion and
        # falls through to the 24h window. Saying "no dated handoff found"
        # there points a debugger away from the cause — the handoff WAS found.
        repo, home = _board(tmp_path)
        (repo / "handoffs" / "2026-08-31-2599-deadbeef.md").write_text("# H\n")
        _stub_bon(home, [])
        out = self._run_tz(repo, home, "Europe/London")
        assert "last 24h" in out["MOTION_SINCE"]
        assert "2026-08-31-2599-deadbeef.md" in out["MOTION_SINCE"]
        assert "no dated handoff found" not in out["MOTION_SINCE"]

    def test_genuinely_absent_handoff_still_says_absent(self, tmp_path):
        # The control: the other branch must keep its own honest message.
        repo, home = _board(tmp_path)
        _stub_bon(home, [])
        out = self._run_tz(repo, home, "Europe/London")
        assert "no dated handoff found" in out["MOTION_SINCE"]


class TestMigrationBridgeSurfacing:
    """close-context.sh greps `bon doctor` for the bridge advisory, which
    retypes the wording cli.py emits. Nothing bound the two, so rewording the
    advisory would have killed the /close surfacing silently with nothing
    going red (bon-kefoba's post-repair essayeur). These pin the coupling.
    """

    def _dev_bon(self, home: Path) -> None:
        """A `bon` on PATH that runs THIS repo's source, not the stale install."""
        bindir = home / "bin"
        bindir.mkdir(parents=True, exist_ok=True)
        stub = bindir / "bon"
        stub.write_text(
            "#!/bin/sh\n"
            f'exec env PYTHONPATH={REPO_ROOT / "src"} python3 -m bon.cli "$@"\n'
        )
        stub.chmod(0o755)

    def _run(self, cwd: Path, home: Path):
        return subprocess.run(
            ["bash", str(CLOSE_CONTEXT)],
            capture_output=True, text=True, cwd=cwd,
            env={
                "HOME": str(home),
                "PATH": f"{home}/bin:/usr/local/bin:/usr/bin:/bin",
                "TZ": "UTC",
                "BON_TEST_NOW_HM": "1200",
                "CLAUDE_CODE_SESSION_ID": "abcd1234-1111-2222-3333-444444444444",
            },
        )

    def test_an_unclosed_bridge_doc_reaches_the_close_rite(self, tmp_path):
        repo, home = _board(tmp_path)
        (repo / ".bon" / "id-migration-2026-08-30.md").write_text(
            "# id migration\n\nthese pointers want updating\n"
        )
        self._dev_bon(home)
        r = self._run(repo, home)
        assert "=== MIGRATION BRIDGE ===" in r.stdout
        assert "BRIDGE_UNCLOSED=id-migration-2026-08-30.md" in r.stdout
        assert "BRIDGE_CUE=" in r.stdout

    def test_a_stamped_doc_stays_silent(self, tmp_path):
        repo, home = _board(tmp_path)
        (repo / ".bon" / "id-migration-2026-08-30.md").write_text(
            "# id migration\n\n## Closed out 2026-08-31\n\nall pointers corrected\n"
        )
        self._dev_bon(home)
        r = self._run(repo, home)
        assert "MIGRATION BRIDGE" not in r.stdout

    def test_no_bridge_doc_stays_silent(self, tmp_path):
        repo, home = _board(tmp_path)
        self._dev_bon(home)
        r = self._run(repo, home)
        assert "MIGRATION BRIDGE" not in r.stdout

    def test_the_script_survives_a_bon_that_fails(self, tmp_path):
        # The whole script must not die when the CLI errors — a Dolt board
        # with the server down exits non-zero, and pipefail plus set -e once
        # killed close-context mid-output, losing every later section.
        repo, home = _board(tmp_path)
        bindir = home / "bin"
        bindir.mkdir(parents=True, exist_ok=True)
        stub = bindir / "bon"
        stub.write_text('#!/bin/sh\necho "boom" >&2\nexit 1\n')
        stub.chmod(0o755)
        r = self._run(repo, home)
        assert r.returncode == 0, r.stderr
        # Sections AFTER the board-motion block must still be emitted.
        assert "TODAY=" in r.stdout, "the script died before reaching META"
