"""session-dashboard.sh state keying (bon-numise).

The state file must key on the SESSION, not ambient process state. When
stdin's session_id arrived empty, the key fell to $$ — a fresh PID every
invocation — so state never persisted: the turn counter froze at
max-sibling+1 and the one-time "Session restarted" banner fired every turn.
The fix falls back to CLAUDE_CODE_SESSION_ID (exported by CC; verified live
in an interactive cli-entrypoint session, 2026-08-16) before $$.
"""
import json
import os
import subprocess
import uuid
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "session-dashboard.sh"


def run_hook(stdin_json, env_session=None, cwd=None):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    if env_session is not None:
        env["CLAUDE_CODE_SESSION_ID"] = env_session
    r = subprocess.run(
        ["bash", str(HOOK)], input=json.dumps(stdin_json),
        capture_output=True, text=True, env=env, cwd=cwd,
    )
    assert r.returncode == 0, r.stderr
    if not r.stdout.strip():
        return ""
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def state_path(session_id):
    return Path(f"/tmp/.claude-dashboard-{session_id}")


def turn_of(context):
    for part in context.splitlines()[-1].split(" · "):
        if part.startswith("turn "):
            return int(part.split()[1])
    raise AssertionError(f"no turn in: {context}")


class TestSessionKeying:
    def test_stdin_session_id_advances(self, tmp_path):
        sid = f"test-{uuid.uuid4().hex[:8]}"
        try:
            t1 = turn_of(run_hook({"session_id": sid}, cwd=tmp_path))
            t2 = turn_of(run_hook({"session_id": sid}, cwd=tmp_path))
            assert t2 == t1 + 1
        finally:
            state_path(sid).unlink(missing_ok=True)

    def test_env_var_fallback_advances(self, tmp_path):
        """Empty stdin session_id — the incident shape — heals via env var."""
        sid = f"test-{uuid.uuid4().hex[:8]}"
        try:
            t1 = turn_of(run_hook({}, env_session=sid, cwd=tmp_path))
            t2 = turn_of(run_hook({}, env_session=sid, cwd=tmp_path))
            t3 = turn_of(run_hook({}, env_session=sid, cwd=tmp_path))
            assert (t2, t3) == (t1 + 1, t1 + 2)
            assert state_path(sid).exists()  # session-keyed, not $$-keyed
        finally:
            state_path(sid).unlink(missing_ok=True)

    def test_concurrent_sessions_independent(self, tmp_path):
        """The --done criterion: two sessions in one cwd, counters independent."""
        a, b = (f"test-{uuid.uuid4().hex[:8]}" for _ in range(2))
        try:
            a1 = turn_of(run_hook({"session_id": a}, cwd=tmp_path))
            b1 = turn_of(run_hook({"session_id": b}, cwd=tmp_path))
            a2 = turn_of(run_hook({"session_id": a}, cwd=tmp_path))
            a3 = turn_of(run_hook({"session_id": a}, cwd=tmp_path))
            b2 = turn_of(run_hook({"session_id": b}, cwd=tmp_path))
            assert (a2, a3) == (a1 + 1, a1 + 2)
            assert b2 == b1 + 1  # b unmoved by a's three turns
        finally:
            state_path(a).unlink(missing_ok=True)
            state_path(b).unlink(missing_ok=True)

    def test_restart_banner_fires_at_most_once(self, tmp_path):
        sid = f"test-{uuid.uuid4().hex[:8]}"
        try:
            run_hook({"session_id": sid}, cwd=tmp_path)
            for _ in range(3):
                out = run_hook({"session_id": sid}, cwd=tmp_path)
                assert "Session restarted" not in out
        finally:
            state_path(sid).unlink(missing_ok=True)


class TestContextWindowInference:
    """Window size inference when no statusline sidecar exists (bon-zugone).

    `message.model` in the transcript records the BASE model id — a 1M Opus
    session writes `claude-opus-5`, identical to a 200k one. settings.json
    keeps the `[1m]` marker and is the only local source that can tell them
    apart, but it used to be read only when the transcript model was empty.
    From turn 2 onward a 1M session was therefore inferred as 200k: observed
    live on 2026-08-22 as "1% free" at 197k of a 1M window.
    """

    def _session(self, tmp_path, model, total_in, configured):
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        if configured is not None:
            (home / ".claude" / "settings.json").write_text(
                json.dumps({"model": configured})
            )
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(json.dumps({
            "type": "assistant",
            "message": {
                "model": model,
                "usage": {
                    "input_tokens": total_in,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        }) + "\n")
        return home, transcript

    def _window_k(self, tmp_path, model, total_in, configured):
        home, transcript = self._session(tmp_path, model, total_in, configured)
        env = dict(os.environ)
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        env.pop("CLAUDE_CONTEXT_WINDOW", None)
        env["HOME"] = str(home)
        r = subprocess.run(
            ["bash", str(HOOK)],
            input=json.dumps({
                "session_id": str(uuid.uuid4()),
                "transcript_path": str(transcript),
            }),
            capture_output=True, text=True, env=env, cwd=str(tmp_path),
        )
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_stripped_variant_still_infers_1m_from_settings(self, tmp_path):
        # The reported bug: transcript says claude-opus-5, settings say opus[1m].
        ctx = self._window_k(tmp_path, "claude-opus-5", 197_000, "opus[1m]")
        assert "1000k window" in ctx
        assert "80% free" in ctx

    def test_genuine_200k_model_stays_200k(self, tmp_path):
        ctx = self._window_k(tmp_path, "claude-sonnet-5", 50_000, "sonnet")
        assert "200k window" in ctx

    def test_input_beyond_200k_proves_1m_regardless(self, tmp_path):
        ctx = self._window_k(tmp_path, "claude-sonnet-5", 400_000, "sonnet")
        assert "1000k window" in ctx

    def test_no_configured_model_falls_back_to_200k(self, tmp_path):
        ctx = self._window_k(tmp_path, "claude-opus-5", 1_000, None)
        assert "200k window" in ctx
