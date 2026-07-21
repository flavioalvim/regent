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
    output: str
    timed_out: bool


class SubprocessRunner:
    def run(self, argv: list[str], *, cwd: str, timeout: float) -> RunResult:
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                start_new_session=True)  # headless: NEVER
        # inherit the parent's stdin — a child waiting for EOF on an
        # inherited pipe hangs forever (caught live by the dogfooded review)
        try:
            output, _ = proc.communicate(timeout=timeout)
            return RunResult(proc.returncode, output or "", False)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            output, _ = proc.communicate()
            return RunResult(None, output or "", True)
