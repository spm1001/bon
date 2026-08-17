"""invocation_log — the estate's invocation-logging shim (canonical copy).

CANONICAL: spm1001/harness-ergonomics/shim/invocation_log.py
Vendored per adopting repo, no runtime coupling: copy this file into the
tool's package (e.g. src/bon/_invlog.py, src/passe/_invlog.py). The schema
is held identical across repos by the conformance test in this repo
(tests/test_conformance.py), which parses a real log line from each
adopter — bind by test, not import. Stdlib only, PEP 723-friendly.

One JSON object per line, appended to
    $XDG_DATA_HOME/<tool>/invocations.jsonl   (default ~/.local/share/<tool>/)

Schema (exactly these keys, no extras — the conformance test enforces both):
    ts            str        ISO 8601 UTC, e.g. "2026-08-17T12:34:56.789Z"
    tool          str        CLI name, e.g. "bon"
    version       str        the version the CLI itself reports
    subcommand    str|null   post-parse subcommand; null if parsing never got there
    argv          [str]      raw argv as received (sys.argv[1:]), BEFORE validation
    parsed        obj|null   post-parse arguments, JSON-safe; null if parse failed
    outcome       "ok"|"error"   ok iff exit_code == 0
    exit_code     int
    duration_ms   number     >= 0
    caller        "model"|"human"|"robot"
    caller_detail str        model: CLAUDE_CODE_ENTRYPOINT ("cli"/"sdk-cli", "unknown"
                             if only CLAUDECODE is set); human: "tty";
                             robot: parent process name (catches cron, systemd, aboyeur)

Design decisions carried from the erg-vikoke brief (2026-08-16):
- Successes AND failures are logged — error-only logging is the failure mode
  that killed the human baseline (numerators without denominators).
- argv is raw-as-received so a misinvocation that dies in the parser (an
  invented flag, exit 2) still leaves its evidence; parsed is null there.
- Rotation is generous: 50 MB per file, 9 rotated siblings kept. mise's
  5 MB x 3 would eat longitudinal history at bon's volume (~17.9k calls /
  7 months); at that volume 50 MB x 10 holds decades.
- Logging must never break the host CLI: every write path is best-effort
  and swallows its own exceptions. The capture context manager re-raises
  the host's exception/exit untouched.

Adoption pattern (argparse host):

    from mytool import _invlog

    def main():
        with _invlog.capture("mytool", __version__) as inv:
            args = parser.parse_args()
            inv.note(subcommand=args.command, parsed=args)
            ... dispatch ...
"""

from __future__ import annotations

import json
import os
import sys
import time

_MAX_BYTES = 50 * 1024 * 1024
_KEEP = 9  # invocations.jsonl.1 .. .9


def _log_path(tool: str) -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, tool, "invocations.jsonl")


def _parent_comm() -> str:
    ppid = os.getppid()
    try:  # Linux
        with open(f"/proc/{ppid}/comm", encoding="utf-8", errors="replace") as f:
            name = f.read().strip()
        if name:
            return name
    except OSError:
        pass
    try:  # macOS and other no-/proc hosts
        import subprocess
        out = subprocess.run(["ps", "-o", "comm=", "-p", str(ppid)],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        if out:
            return os.path.basename(out)
    except Exception:
        pass
    return "unknown"


def caller_stamp() -> tuple[str, str]:
    """(caller, caller_detail): model per CC env; human per tty; else robot+parent."""
    entrypoint = os.environ.get("CLAUDE_CODE_ENTRYPOINT")
    if os.environ.get("CLAUDECODE") or entrypoint:
        return "model", (entrypoint or "unknown")
    try:
        if sys.stdin.isatty() or sys.stderr.isatty():
            return "human", "tty"
    except Exception:
        pass
    return "robot", _parent_comm()


def _json_safe(value, depth=0):
    if depth > 6:
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in value.items()}
    return repr(value)


def scrub_args(parsed, drop=("func",)):
    """argparse Namespace or mapping -> JSON-safe dict for the `parsed` field."""
    if parsed is None:
        return None
    mapping = parsed if isinstance(parsed, dict) else vars(parsed)
    return {str(k): _json_safe(v) for k, v in mapping.items() if k not in drop}


def _rotate(path: str) -> None:
    try:
        if os.path.getsize(path) < _MAX_BYTES:
            return
    except OSError:
        return
    for i in range(_KEEP - 1, 0, -1):
        src, dst = f"{path}.{i}", f"{path}.{i + 1}"
        if os.path.exists(src):
            os.replace(src, dst)
    os.replace(path, f"{path}.1")


class Invocation:
    """One invocation record; finish() writes the line (best-effort, never raises)."""

    def __init__(self, tool: str, version: str):
        self.tool = tool
        self.version = version
        self.subcommand = None
        self.parsed = None
        try:
            self.argv = [str(a) for a in sys.argv[1:]]
        except Exception:
            self.argv = []
        self._t0 = time.monotonic()

    def note(self, subcommand=None, parsed=None):
        """Record post-parse facts. Call after argument parsing succeeds."""
        try:
            if subcommand is not None:
                self.subcommand = str(subcommand)
            if parsed is not None:
                self.parsed = scrub_args(parsed)
        except Exception:
            pass

    def finish(self, exit_code: int) -> None:
        try:
            caller, caller_detail = caller_stamp()
            now = time.time()
            record = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))
                      + f".{int(now * 1000) % 1000:03d}Z",
                "tool": self.tool,
                "version": self.version,
                "subcommand": self.subcommand,
                "argv": self.argv,
                "parsed": self.parsed,
                "outcome": "ok" if exit_code == 0 else "error",
                "exit_code": int(exit_code),
                "duration_ms": round((time.monotonic() - self._t0) * 1000, 3),
                "caller": caller,
                "caller_detail": caller_detail,
            }
            path = _log_path(self.tool)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _rotate(path)
            data = (json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                    + "\n").encode("utf-8")
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, data)  # single write: atomic append for a small line
            finally:
                os.close(fd)
        except Exception:
            pass  # logging must never break the host CLI


class capture:
    """Context manager wrapping a CLI main(). Logs on every exit path, re-raises."""

    def __init__(self, tool: str, version: str):
        self.invocation = Invocation(tool, version)

    def __enter__(self) -> Invocation:
        return self.invocation

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            code = 0
        elif isinstance(exc, SystemExit):
            if exc.code is None:
                code = 0
            elif isinstance(exc.code, int):
                code = exc.code
            else:
                code = 1  # sys.exit("message") convention
        elif isinstance(exc, KeyboardInterrupt):
            code = 130
        else:
            code = 1
        self.invocation.finish(code)
        return False  # never swallow the host's exception
