#!/usr/bin/env python3
"""Standalone Claude Code hook for confined turns (PLAN-004 STEP-01).

Copied into a per-turn PRIVATE dir and referenced by the generated
settings.json. Reads REGENT_ENVELOPE (JSON list of allowed write roots),
REGENT_EVENT_LOG (private append log) and REGENT_TURN_SECRET (HMAC key for the
audit chain — NOT an anti-forgery proof against the agent; see PLAN-004 trust
model) from its own environment.

Semantics (official Claude Code hooks):
- PreToolUse decides allow/deny. Write/Edit/MultiEdit are allowed ONLY if the
  canonical real-path of the target is inside the envelope; every other
  write/exec tool (Bash included, defense in depth) is denied; read-only tools
  are allowed. A `pre` event is appended.
- PostToolUse (only fires after a successful tool) appends a `post` event with
  the resulting file's content sha256, correlated by tool_use_id.
Fails CLOSED: any internal error → deny + `hook_error` event.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "NotebookRead", "TodoWrite",
                   "WebFetch", "WebSearch", "Task"}


def _canonical(line: dict) -> str:
    return json.dumps(line, sort_keys=True, separators=(",", ":"))


def _append_event(event: dict) -> None:
    log_path = os.environ["REGENT_EVENT_LOG"]
    secret = os.environ["REGENT_TURN_SECRET"].encode()
    fd = os.open(log_path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)  # serialize concurrent hooks
        existing = _read_last_line(log_path)
        prev_hmac = existing.get("hmac", "") if existing else ""
        seq = (existing.get("seq", -1) + 1) if existing else 0
        event["seq"] = seq
        payload = _canonical(event)
        event["hmac"] = hmac.new(secret, (payload + prev_hmac).encode(),
                                 hashlib.sha256).hexdigest()
        os.write(fd, (json.dumps(event, sort_keys=True) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_last_line(path: str) -> dict | None:
    try:
        lines = [l for l in Path(path).read_text(encoding="utf-8").splitlines()
                 if l.strip()]
    except OSError:
        return None
    return json.loads(lines[-1]) if lines else None


def _target_paths(tool_name: str, tool_input: dict) -> list[str]:
    if tool_name in ("Write", "Edit", "NotebookEdit"):
        p = tool_input.get("file_path") or tool_input.get("notebook_path")
        return [p] if p else []
    if tool_name == "MultiEdit":
        p = tool_input.get("file_path")
        return [p] if p else []
    return []


def _inside_envelope(path: str, envelope: list[str]) -> bool:
    try:
        real = Path(path).resolve()
    except (OSError, RuntimeError):
        return False
    for root in envelope:
        try:
            root_real = Path(root).resolve()
        except (OSError, RuntimeError):
            continue
        if real == root_real or root_real in real.parents:
            return True
    return False


def _decide(payload: dict) -> dict:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    tool_use_id = payload.get("tool_use_id", "")
    envelope = json.loads(os.environ.get("REGENT_ENVELOPE", "[]"))

    # Malformed payload → deny (fail closed), even for an allowlisted tool.
    if not isinstance(tool_input, dict):
        _append_event({"kind": "pre", "tool": tool_name or "<unknown>",
                       "tool_use_id": tool_use_id, "paths": [],
                       "decision": "deny", "reason": "malformed tool_input"})
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": "deny",
                                       "permissionDecisionReason":
                                       "malformed tool_input (fail closed)"}}

    if tool_name in WRITE_TOOLS:
        targets = _target_paths(tool_name, tool_input)
        allow = bool(targets) and all(_inside_envelope(p, envelope)
                                      for p in targets)
        decision = "allow" if allow else "deny"
        _append_event({"kind": "pre", "tool": tool_name, "tool_use_id": tool_use_id,
                       "paths": targets, "decision": decision})
        if allow:
            return {}  # allow (no explicit permission decision needed)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": "deny",
                                       "permissionDecisionReason":
                                       "outside the turn envelope"}}
    # Default-deny: only an ALLOWLIST of known read-only tools passes silently.
    # Anything else — Bash/exec, an unknown/future tool, a malformed payload —
    # is denied (a write/exec we do not recognize must never slip through).
    if tool_name in READ_ONLY_TOOLS:
        return {}
    _append_event({"kind": "pre", "tool": tool_name or "<unknown>",
                   "tool_use_id": tool_use_id, "paths": [], "decision": "deny"})
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason":
                                   "tool not in the confined-turn allowlist"}}


def _post(payload: dict) -> dict:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}
    tool_use_id = payload.get("tool_use_id", "")
    for path in _target_paths(tool_name, tool_input):
        try:
            digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            mode = oct(os.stat(path).st_mode & 0o777)
        except OSError:
            digest, mode = None, None
        _append_event({"kind": "post", "tool": tool_name,
                       "tool_use_id": tool_use_id, "path": path,
                       "content_sha256": digest, "mode": mode})
    return {}


def main(argv: list[str], stdin_text: str) -> int:
    try:
        payload = json.loads(stdin_text or "{}")
        event_name = payload.get("hook_event_name") \
            or (argv[1] if len(argv) > 1 else "")
        if event_name == "PreToolUse":
            output = _decide(payload)
        elif event_name == "PostToolUse":
            output = _post(payload)
        else:
            output = {}
        if output:
            sys.stdout.write(json.dumps(output))
        return 0
    except Exception as exc:  # noqa: BLE001 — fail CLOSED
        try:
            _append_event({"kind": "hook_error", "error": repr(exc)})
        except Exception:  # noqa: BLE001
            pass
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "hook internal error (fail closed)"}}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv, sys.stdin.read()))
