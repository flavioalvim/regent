"""Confined-turn composition (PLAN-004 STEP-02).

Builds an immutable per-turn PRIVATE dir (outside the repo) with a generated
settings.json that wires the Pre/PostToolUse hooks to a private copy of
hookscript.py, and returns the `claude -p` argv + minimal environment. The
launch inherits NO config (`--setting-sources ""`), restricts tools, and forces
acceptEdits (the confinement IS the hook's deny; dontAsk would deny even
in-envelope writes — empirical IMP-003 lesson).
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TOOLS = "Read,Write,Edit,MultiEdit"
ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL")


@dataclass
class ConfinedTurn:
    private_dir: Path
    settings_path: Path
    event_log: Path
    secret: str
    envelope: list[str]

    def cleanup(self) -> None:
        shutil.rmtree(self.private_dir, ignore_errors=True)


def compose(*, envelope: list[str], claude_bin: str = "claude") -> ConfinedTurn:
    private_dir = Path(tempfile.mkdtemp(prefix="regent-turn-"))
    hook_copy = private_dir / "hookscript.py"
    shutil.copy(Path(__file__).with_name("hookscript.py"), hook_copy)
    event_log = private_dir / "events.log"
    secret = secrets.token_hex(32)
    envelope = [str(Path(p).resolve()) for p in envelope]

    hook_cmd = f"{_python()} {hook_copy}"
    settings = {
        "hooks": {
            "PreToolUse": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
            "PostToolUse": [{"hooks": [{"type": "command", "command": hook_cmd}]}],
        }
    }
    settings_path = private_dir / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    # Freeze the composition (read-only) so nothing mutates it mid-turn.
    for path in (hook_copy, settings_path):
        path.chmod(0o400)
    return ConfinedTurn(private_dir, settings_path, event_log, secret, envelope)


def launch_argv(turn: ConfinedTurn, *, prompt: str,
                claude_bin: str = "claude") -> list[str]:
    return [claude_bin, "-p", prompt,
            "--setting-sources", "",              # inherit NOTHING
            "--settings", str(turn.settings_path),
            "--tools", ALLOWED_TOOLS,
            "--permission-mode", "acceptEdits"]


def launch_env(turn: ConfinedTurn) -> dict[str, str]:
    env = {k: os.environ[k] for k in ENV_ALLOWLIST if k in os.environ}
    env["REGENT_TURN_SECRET"] = turn.secret
    env["REGENT_ENVELOPE"] = json.dumps(turn.envelope)
    env["REGENT_EVENT_LOG"] = str(turn.event_log)
    return env


def _python() -> str:
    import sys
    return sys.executable or "python3"
