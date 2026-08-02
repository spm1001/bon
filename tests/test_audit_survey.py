"""Unit tests for the review skill's audit_survey.py helpers.

The survey script lives outside src/ (it ships with the review skill), so it
is loaded by path. Only the pure/local helpers are tested here — the Dolt
paths are covered by the opt-in integration suite and live runs.
"""

import importlib.util
import subprocess
from pathlib import Path

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
