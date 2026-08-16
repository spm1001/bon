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
