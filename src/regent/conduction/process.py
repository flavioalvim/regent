"""Injectable process runner for the conduction commands (PLAN-003).

The real runner launches the child in a NEW SESSION (its own process group);
on timeout the WHOLE group is SIGKILLed before the TIMEOUT outcome is
reported — no child (not even ones spawned by bash) survives the result.
"""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass


@dataclass
class RunResult:
    exit_code: int | None
    output_bytes: bytes
    timed_out: bool
    aborted: bool = False

    @property
    def output(self) -> str:
        return self.output_bytes.decode("utf-8", errors="replace")


class SubprocessRunner:
    def run(self, argv: list[str], *, cwd: str, timeout: float,
            env: dict | None = None, cancel=None) -> RunResult:
        """Cancellable + deadlock-free: a reader THREAD drains stdout while the
        main loop polls `cancel` (checked BEFORE timeout — deterministic
        precedence) and the deadline. On either, the whole group is SIGKILLed
        and the group reaped. `aborted` (cancel) is distinct from `timed_out`."""
        import threading
        import time as _time
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, env=env,
                                start_new_session=True)
        chunks: list[bytes] = []
        reader = threading.Thread(target=lambda: chunks.append(proc.stdout.read()),
                                  daemon=True)
        reader.start()
        deadline = _time.monotonic() + timeout
        aborted = timed_out = False
        while True:
            if cancel is not None and cancel.is_set():  # cancel BEFORE timeout
                aborted = True
                break
            if _time.monotonic() >= deadline:
                timed_out = True
                break
            if proc.poll() is not None:
                break
            _time.sleep(0.1)
        if aborted or timed_out:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        proc.wait()  # reap the group leader
        reader.join(timeout=5)
        try:
            proc.stdout.close()
        except OSError:
            pass
        output = chunks[0] if chunks else b""
        exit_code = None if (aborted or timed_out) else proc.returncode
        return RunResult(exit_code, output or b"", timed_out, aborted)
