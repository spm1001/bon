"""Invocation-log adoption tests (erg-fatogo).

bon vendors the estate invocation-log shim as src/bon/_invlog.py — canonical
copy and the cross-estate conformance test live in spm1001/harness-ergonomics
(shim/invocation_log.py, tests/test_conformance.py). These tests pin the
adoption facts locally: every invocation appends exactly one caller-stamped
JSONL line — success and failure alike — and a broken log path never breaks
the CLI.
"""
import json
import os

from conftest import run_bon


def _env(tmp_path, **overrides):
    """Env with a hermetic log dir and a deterministic model caller stamp."""
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env["XDG_DATA_HOME"] = str(tmp_path / "xdg")
    env.update(overrides)
    return env


def _log_lines(tmp_path):
    log = tmp_path / "xdg" / "bon" / "invocations.jsonl"
    assert log.exists(), f"no invocation log at {log}"
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


class TestInvocationLog:
    def test_ok_invocation_logs_one_line(self, bon_dir, tmp_path):
        env = _env(tmp_path, CLAUDECODE="1", CLAUDE_CODE_ENTRYPOINT="cli")
        result = run_bon("list", cwd=bon_dir, env=env, input="")
        assert result.returncode == 0
        (line,) = _log_lines(tmp_path)
        assert line["tool"] == "bon"
        assert line["subcommand"] == "list"
        assert line["argv"] == ["list"]
        assert line["parsed"]["command"] == "list"
        assert "func" not in line["parsed"]
        assert line["outcome"] == "ok" and line["exit_code"] == 0
        assert line["caller"] == "model" and line["caller_detail"] == "cli"
        assert line["duration_ms"] >= 0
        assert line["version"]  # whatever the CLI reports, non-empty

    def test_error_invocation_logged_with_parsed_args(self, bon_dir, tmp_path):
        env = _env(tmp_path, CLAUDECODE="1", CLAUDE_CODE_ENTRYPOINT="cli")
        result = run_bon("show", "BOGUS-NOPE", cwd=bon_dir, env=env, input="")
        assert result.returncode == 1
        (line,) = _log_lines(tmp_path)
        assert line["subcommand"] == "show"
        assert line["outcome"] == "error" and line["exit_code"] == 1
        assert line["parsed"]["id"] == "BOGUS-NOPE"

    def test_misinvocation_dies_in_argparse_still_logged(self, bon_dir, tmp_path):
        """An invented flag never reaches post-parse — raw argv is the evidence."""
        env = _env(tmp_path, CLAUDECODE="1")
        result = run_bon("list", "--definitely-not-a-flag", cwd=bon_dir, env=env, input="")
        assert result.returncode == 2
        (line,) = _log_lines(tmp_path)
        assert line["outcome"] == "error" and line["exit_code"] == 2
        assert line["argv"] == ["list", "--definitely-not-a-flag"]
        assert line["subcommand"] is None and line["parsed"] is None

    def test_robot_stamp_without_cc_env_or_tty(self, bon_dir, tmp_path):
        env = _env(tmp_path)  # no CC env; stdin/stdout/stderr are pipes
        result = run_bon("list", cwd=bon_dir, env=env, input="")
        assert result.returncode == 0
        (line,) = _log_lines(tmp_path)
        assert line["caller"] == "robot"
        assert line["caller_detail"]  # parent process name, non-empty

    def test_unwritable_log_path_never_breaks_cli(self, bon_dir, tmp_path):
        blocker = tmp_path / "xdg"
        blocker.write_text("occupied")  # a file where the data dir should be
        env = dict(os.environ, XDG_DATA_HOME=str(blocker), CLAUDECODE="1")
        result = run_bon("list", cwd=bon_dir, env=env, input="")
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
