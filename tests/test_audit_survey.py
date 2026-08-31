"""Unit tests for the review skill's audit_survey.py helpers.

The survey script lives outside src/ (it ships with the review skill), so it
is loaded by path. Only the pure/local helpers are tested here — the Dolt
paths are covered by the opt-in integration suite and live runs.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent.parent / "skills" / "review" / "scripts" / "audit_survey.py"
)
_spec = importlib.util.spec_from_file_location("audit_survey", SCRIPT)
audit_survey = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_survey)


class TestDoneRecords:
    def _done(self, n, done_at):
        return {
            "id": f"x-{n}",
            "title": f"item {n}",
            "type": "action",
            "done_at": done_at,
            "done_note": f"note {n}",
        }

    def test_newest_first(self):
        items = [
            self._done("a", "2026-07-01T00:00:00Z"),
            self._done("b", "2026-08-01T00:00:00Z"),
            self._done("c", "2026-07-15T00:00:00Z"),
        ]
        recs, total = audit_survey.done_records(items)
        assert [r["id"] for r in recs] == ["x-b", "x-c", "x-a"]
        assert total == 3
        assert recs[0]["done_note"] == "note b"

    def test_cap_states_true_total(self):
        # 13 in, cap out — but the count must be the TRUE total, so a
        # truncated list can't read as complete (no silent caps).
        items = [self._done(i, f"2026-07-{i:02d}T00:00:00Z") for i in range(1, 14)]
        recs, total = audit_survey.done_records(items)
        assert len(recs) == audit_survey.RECENT_DONES_CAP
        assert total == 13

    def test_missing_done_at_sorts_last_not_crashes(self):
        items = [
            {"id": "x-n", "title": "no stamp", "type": "action"},
            self._done("b", "2026-08-01T00:00:00Z"),
        ]
        recs, total = audit_survey.done_records(items)
        assert [r["id"] for r in recs] == ["x-b", "x-n"]
        assert "done_at" not in recs[1]


class TestGetJob:
    def test_absent_is_none(self, tmp_path):
        assert audit_survey.get_job(tmp_path) is None

    def test_present_is_stripped_value(self, tmp_path):
        (tmp_path / "job").write_text("knowledge-work\n")
        assert audit_survey.get_job(tmp_path) == "knowledge-work"

    def test_empty_file_is_none(self, tmp_path):
        (tmp_path / "job").write_text("\n")
        assert audit_survey.get_job(tmp_path) is None


class TestDetectDuplicatePrefixes:
    def _board(self, path, prefix, backend="jsonl"):
        return {
            "bon_dir": Path(path) / ".bon",
            "repo_path": Path(path),
            "root": Path("/r"),
            "backend": backend,
            "prefix": prefix,
        }

    def _resolver(self, origins):
        return lambda p: origins.get(str(p))

    def test_same_prefix_different_origins_flagged(self):
        # The live bon-kafono shape: the owner's Dolt board plus a JSONL
        # squatter, both cloned locally.
        boards = [
            self._board("/r/spm1001/bon", "bon", backend="dolt"),
            self._board("/r/itv/mit-agentic-sales", "bon"),
        ]
        origins = {
            "/r/spm1001/bon": "github.com/spm1001/bon",
            "/r/itv/mit-agentic-sales": "github.com/itv/mit-agentic-sales",
        }
        out = audit_survey.detect_duplicate_prefixes(
            boards, {}, origin_resolver=self._resolver(origins)
        )
        assert len(out) == 1
        assert out[0]["prefix"] == "bon"
        assert len(out[0]["boards"]) == 2

    def test_same_origin_clones_exempt(self):
        # A repo checked out twice (e.g. a marketplace cache clone) is the
        # estate's normal shape, not a squat.
        boards = [self._board("/r/a", "tp"), self._board("/r/b", "tp")]
        origins = {
            "/r/a": "github.com/spm1001/trousse-personal",
            "/r/b": "github.com/spm1001/trousse-personal",
        }
        out = audit_survey.detect_duplicate_prefixes(
            boards, {}, origin_resolver=self._resolver(origins)
        )
        assert out == []

    def test_jsonl_squat_caught_without_owner_clone(self):
        # The repos-table layer: the rightful owner isn't cloned under the
        # scan roots, but the shared DB knows who the prefix belongs to.
        boards = [self._board("/r/itv/mit-agentic-sales", "bon")]
        repos_map = {
            "bon": {
                "repo_name": "spm1001/bon",
                "origin_url": "https://github.com/spm1001/bon.git",
            }
        }
        origins = {"/r/itv/mit-agentic-sales": "github.com/itv/mit-agentic-sales"}
        out = audit_survey.detect_duplicate_prefixes(
            boards, repos_map, origin_resolver=self._resolver(origins)
        )
        assert len(out) == 1
        assert out[0]["repos_table"]["repo_name"] == "spm1001/bon"

    def test_singleton_dolt_with_matching_registration_clean(self):
        boards = [self._board("/r/spm1001/bon", "bon", backend="dolt")]
        repos_map = {
            "bon": {
                "repo_name": "spm1001/bon",
                "origin_url": "git@github.com:spm1001/bon.git",
            }
        }
        out = audit_survey.detect_duplicate_prefixes(
            boards,
            repos_map,
            origin_resolver=lambda p: "github.com/spm1001/bon",
        )
        assert out == []

    def test_no_origin_boards_count_as_distinct_identities(self):
        # Fail-visible: two originless boards sharing a prefix flag rather
        # than silently merging on "origin unknown".
        boards = [self._board("/r/a", "x"), self._board("/r/b", "x")]
        out = audit_survey.detect_duplicate_prefixes(
            boards, {}, origin_resolver=lambda p: None
        )
        assert len(out) == 1

    def test_norm_origin_url_forms_agree(self):
        n = audit_survey._norm_origin
        assert (
            n("https://github.com/A/B.git")
            == n("git@github.com:A/B.git")
            == "github.com/a/b"
        )
        assert n(None) is None


class TestGitActivity:
    def test_non_repo_soft_fails_to_none(self, tmp_path):
        assert audit_survey.git_activity(tmp_path, 30) is None

    def test_real_repo_reports_count_and_last_commit(self, tmp_path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / "f.txt").write_text("hello\n")
        subprocess.run(["git", "add", "f.txt"], cwd=tmp_path, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-q", "-m", "test commit subject"],
            cwd=tmp_path, check=True,
        )
        out = audit_survey.git_activity(tmp_path, 30)
        assert out is not None
        assert out["commits_window"] == 1
        assert "test commit subject" in out["last_commit"]


# ---------- scope-flag hardening (bon-libito) ----------
#
# The three faults these pin, all measured on the real 52-label estate:
# an empty --repos silently widened to everything; the substring match
# over-included (`passe` swept in `spm1001/passe-partout`); and jobs had
# no flag at all. The old substring expression is asserted alongside the
# new one so the change in what a filter matches is documented, not silent
# — the card's own falsifier.

# A slice of the real 2026-08-31 label population: bare labels, owner-bucketed
# labels, and the three genuine substring collisions among them.
_LABELS = [
    "bon", "trousse", "passe", "notes", "mise-en-space",
    "spm1001/passe-partout", "spm1001/trousse-personal", "spm1001/sonner",
    "itv/mit-kg", "itv/mit-commons",
]


def _results(labels=None, jobs=None):
    jobs = jobs or {}
    out = []
    for label in (labels if labels is not None else _LABELS):
        entry = {"repo": label, "open_count": 1}
        if label in jobs:
            entry["job"] = jobs[label]
        out.append(entry)
    return out


def _old_substring_filter(results, repo_filter):
    """The pre-libito expression, kept as the comparison arm."""
    return [r for r in results if any(f in r["repo"] for f in repo_filter)]


class TestFlagValues:
    def test_absent_flag_is_none(self):
        assert audit_survey.flag_values(["--roots", "/x"], "--repos") is None

    def test_values_stop_at_next_option(self):
        argv = ["--repos", "bon", "trousse", "--window-days", "14"]
        assert audit_survey.flag_values(argv, "--repos") == ["bon", "trousse"]

    def test_empty_is_a_real_answer_not_none(self):
        # The whole bug: [] and None must stay distinguishable here so the
        # guard above can tell "asked for nothing" from "did not ask".
        argv = ["--repos", "--roots", "/x"]
        assert audit_survey.flag_values(argv, "--repos") == []

    def test_trailing_flag_with_no_values_is_empty(self):
        assert audit_survey.flag_values(["--repos"], "--repos") == []


class TestRequireValues:
    def test_none_passes_through(self):
        assert audit_survey.require_values(None, "--repos") is None

    def test_values_pass_through(self):
        assert audit_survey.require_values(["bon"], "--repos") == ["bon"]

    def test_empty_exits_two(self, capsys):
        with pytest.raises(SystemExit) as e:
            audit_survey.require_values([], "--repos")
        assert e.value.code == 2
        assert "--repos" in capsys.readouterr().err


class TestMatchRepo:
    def test_whole_label(self):
        assert audit_survey.match_repo("bon", "bon")

    def test_final_path_segment(self):
        # Bare-name filtering has to keep working on bucketed labels.
        assert audit_survey.match_repo("spm1001/sonner", "sonner")
        assert audit_survey.match_repo("itv/mit-kg", "mit-kg")

    def test_full_bucketed_label(self):
        assert audit_survey.match_repo("itv/mit-kg", "itv/mit-kg")

    def test_substring_does_not_match(self):
        assert not audit_survey.match_repo("spm1001/passe-partout", "passe")
        assert not audit_survey.match_repo("spm1001/trousse-personal", "trousse")
        assert not audit_survey.match_repo("mise-en-space", "mise")

    def test_bucket_owner_is_not_a_match(self):
        assert not audit_survey.match_repo("spm1001/sonner", "spm1001")


class TestApplyRepoFilter:
    def test_exact_hit(self):
        out = audit_survey.apply_repo_filter(_results(), ["bon"])
        assert [r["repo"] for r in out] == ["bon"]

    def test_bucketed_basename_hit(self):
        out = audit_survey.apply_repo_filter(_results(), ["sonner"])
        assert [r["repo"] for r in out] == ["spm1001/sonner"]

    def test_narrowing_against_old_behaviour_is_reported(self, capsys):
        # THE change: 'passe' used to pull in passe-partout too.
        old = _old_substring_filter(_results(), ["passe"])
        assert sorted(r["repo"] for r in old) == ["passe", "spm1001/passe-partout"]

        new = audit_survey.apply_repo_filter(_results(), ["passe"])
        assert [r["repo"] for r in new] == ["passe"]

        # ...and the narrowing is announced, so it cannot pass unnoticed.
        err = capsys.readouterr().err
        assert "spm1001/passe-partout" in err
        assert "NOT matched" in err

    def test_clean_hit_reports_nothing(self, capsys):
        audit_survey.apply_repo_filter(_results(), ["bon"])
        assert capsys.readouterr().err == ""

    def test_miss_exits_two_naming_near_misses(self, capsys):
        # 'mise' matched mise-en-space under the old semantics; under the new
        # ones it matches nothing — so it must SAY so, not return empty.
        old = _old_substring_filter(_results(), ["mise"])
        assert [r["repo"] for r in old] == ["mise-en-space"]

        with pytest.raises(SystemExit) as e:
            audit_survey.apply_repo_filter(_results(), ["mise"])
        assert e.value.code == 2
        err = capsys.readouterr().err
        assert "mise-en-space" in err
        assert "matched no board" in err

    def test_miss_with_no_near_miss_still_exits(self, capsys):
        with pytest.raises(SystemExit) as e:
            audit_survey.apply_repo_filter(_results(), ["nosuchrepo"])
        assert e.value.code == 2
        assert "nosuchrepo" in capsys.readouterr().err

    def test_multiple_values_union(self):
        out = audit_survey.apply_repo_filter(_results(), ["bon", "itv/mit-kg"])
        assert sorted(r["repo"] for r in out) == ["bon", "itv/mit-kg"]

    def test_one_bad_value_among_good_ones_still_exits(self):
        with pytest.raises(SystemExit):
            audit_survey.apply_repo_filter(_results(), ["bon", "nosuchrepo"])


class TestApplyJobFilter:
    def _jobbed(self):
        return _results(jobs={"bon": "toolmaking", "notes": "knowledge-work"})

    def test_filters_to_one_job(self):
        out = audit_survey.apply_job_filter(self._jobbed(), ["toolmaking"])
        assert [r["repo"] for r in out] == ["bon"]

    def test_unknown_job_exits_naming_the_live_set(self, capsys):
        with pytest.raises(SystemExit) as e:
            audit_survey.apply_job_filter(self._jobbed(), ["nosuchjob"])
        assert e.value.code == 2
        err = capsys.readouterr().err
        assert "nosuchjob" in err
        assert "toolmaking" in err

    def test_no_jobs_at_all_says_so(self, capsys):
        with pytest.raises(SystemExit):
            audit_survey.apply_job_filter(_results(), ["toolmaking"])
        assert "jobs_unassigned" in capsys.readouterr().err


class TestFullDones:
    def test_cap_applies_by_default(self):
        items = [
            {"id": f"x-{n}", "title": f"t{n}", "done_at": f"2026-08-{n:02d}T00:00:00Z"}
            for n in range(1, 26)
        ]
        recs, total = audit_survey.done_records(items)
        assert len(recs) == audit_survey.RECENT_DONES_CAP
        assert total == 25

    def test_cap_none_returns_everything(self):
        items = [
            {"id": f"x-{n}", "title": f"t{n}", "done_at": f"2026-08-{n:02d}T00:00:00Z"}
            for n in range(1, 26)
        ]
        recs, total = audit_survey.done_records(items, cap=None)
        assert len(recs) == 25
        assert total == 25


class TestEmptyFlagEndToEnd:
    """The empty-flag guard runs before any Dolt work, so this is fast."""

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True,
        )

    def test_empty_repos_exits_two_without_surveying(self):
        r = self._run("--repos", "--window-days", "7")
        assert r.returncode == 2
        assert "--repos" in r.stderr
        assert r.stdout == ""

    def test_trailing_empty_repos_exits_two(self):
        r = self._run("--repos")
        assert r.returncode == 2
        assert r.stdout == ""

    def test_empty_roots_exits_two(self):
        r = self._run("--roots")
        assert r.returncode == 2
        assert r.stdout == ""
