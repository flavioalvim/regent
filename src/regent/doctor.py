"""regent doctor — capability diagnostics via safe non-interactive probes.

Contract (PRD REQ-003 §6): exit 0 iff every capability is usable; structured
per-capability report. Probes never open interactive sessions.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_UNAVAILABLE = 1

CAPABILITIES = (
    ("executor", "claude", ["claude", "--version"]),
    ("advisor", "codex", ["codex", "--version"]),
)


def _default_probe(argv: list[str]) -> tuple[str, str]:
    """Returns (status, detail): OK, MISSING or BROKEN."""
    if shutil.which(argv[0]) is None:
        return "MISSING", f"'{argv[0]}' not found on PATH"
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return "BROKEN", f"probe failed: {exc}"
    if proc.returncode != 0:
        return "BROKEN", f"exit {proc.returncode}: {proc.stderr.strip()[:200]}"
    return "OK", proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else "ok"


def run_doctor(project_root: Path, out=sys.stdout, probe=_default_probe) -> int:
    all_ok = True
    for role, _cli, argv in CAPABILITIES:
        status, detail = probe(argv)
        all_ok = all_ok and status == "OK"
        print(f"{role:<9} {status:<8} {detail}", file=out)

    initialized = (project_root / ".regent").is_dir()
    print(f"project   {'INITIALIZED' if initialized else 'NOT-INITIALIZED':<8} "
          f"{project_root}", file=out)

    control_state = _control_state(project_root)
    print(f"control   {control_state.upper():<8}", file=out)
    if control_state == "corrupt":  # PLAN-002: corrupt control fails the doctor
        all_ok = False

    return EXIT_OK if all_ok else EXIT_UNAVAILABLE


def _control_state(project_root: Path) -> str:
    path = project_root / ".regent" / "control.json"
    if not path.exists():
        return "uninitialized"
    from .protocol.audit import AuditLog
    from .protocol.control import ControlSchemaError, ControlStore
    try:
        ControlStore(path, AuditLog(path.parent / "protocol" / "audit.jsonl")).load()
        return "initialized"
    except ControlSchemaError:
        return "corrupt"
