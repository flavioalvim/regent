"""CLI subcommands over the activity application layer (PLAN-002 STEP-02).

Contract (normative, PLAN-002): stdout is ALWAYS pure JSON — success or the
error envelope {"error": CODE, "detail": ...} — including argparse usage
errors; stderr carries optional human hints only. Exit codes: 0 success,
2 precondition, 3 lock/fencing/busy, 4 corrupt control, 5 IO, 64 usage.
Root discovery: --project, else cwd upward until a `.regent/` dir is found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .activity import ActivityError, ActivityService
from .protocol import (LockHeld, MutationMutexBusy, NotLockOwner, StaleLock,
                       VersionConflict)
from .protocol.control import ControlSchemaError

_EXIT_BY_CODE = {
    "USAGE": 64, "UNINITIALIZED": 2, "NO_ACTIVITY": 2, "NOT_ACTIVE": 2,
    "NOT_SUSPENDED": 2, "ACTIVITY_OPEN": 2,
    "TOKEN_MISMATCH": 3, "LOCK_HELD": 3, "LOCK_SUSPECT": 3, "BUSY": 3,
    "CONFLICT": 3, "UNATTRIBUTABLE": 3, "CORRUPT_CONTROL": 4, "IO": 5,
    "ADVISOR_FAILED": 3, "ADVISOR_UNAVAILABLE": 2, "GATE_RED": 3, "PROVENANCE": 3,
    "TURN_VIOLATION": 3, "TURN_TAMPERED": 3, "TURN_FAILED": 3, "NOT_ACTIVE": 2,
    "STEP_MISMATCH": 2, "ARTIFACT_OUTSIDE_REGENT": 2, "STEP_ALREADY_DONE": 2,
    "WORKTREE_DIRTY": 3,
}


class _UsageError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class _JsonArgumentParser(argparse.ArgumentParser):
    """argparse that raises instead of printing/exiting, so even usage errors
    come out as pure JSON on stdout."""

    def error(self, message):  # noqa: A003 — argparse API
        raise _UsageError(message)


def _emit(payload: dict, exit_code: int, out=None) -> int:
    print(json.dumps(payload, sort_keys=True), file=out or sys.stdout)
    return exit_code


def _fail(code: str, detail, out=None) -> int:
    return _emit({"error": code, "detail": detail}, _EXIT_BY_CODE.get(code, 1), out)


def find_root(start: Path, explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).resolve()
        return candidate if (candidate / ".regent").is_dir() else None
    current = Path(start).resolve()
    for path in (current, *current.parents):
        if (path / ".regent").is_dir():
            return path
    return None


def build_parser(sub) -> None:
    p_status = sub.add_parser("status", help="control + lock + capabilities (JSON)")
    p_status.add_argument("--project", default=None)

    p_act = sub.add_parser("activity", help="activity lifecycle operations")
    p_act.add_argument("--project", default=None)
    act_sub = p_act.add_subparsers(dest="activity_command", required=True)
    p = act_sub.add_parser("start")
    p.add_argument("--type", required=True, dest="activity_type")
    p.add_argument("--id", required=True, dest="activity_id")
    p = act_sub.add_parser("resume")
    p.add_argument("--id", default=None, dest="activity_id")
    p = act_sub.add_parser("suspend")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--in-flight", default=None, dest="in_flight")
    p.add_argument("--evidence", action="append", default=[])
    p = act_sub.add_parser("conclude")
    p.add_argument("--status", required=True)
    act_sub.add_parser("heartbeat")
    p = act_sub.add_parser("takeover")
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", default="mediator")

    p_stop = sub.add_parser("stop", help="stop-request channel")
    p_stop.add_argument("--project", default=None)
    stop_sub = p_stop.add_subparsers(dest="stop_command", required=True)
    p = stop_sub.add_parser("request")
    p.add_argument("--reason", default=None)
    stop_sub.add_parser("check")

    p_advisor = sub.add_parser("advisor", help="mechanized advisor consultation")
    p_advisor.add_argument("--project", default=None)
    advisor_sub = p_advisor.add_subparsers(dest="advisor_command", required=True)
    p = advisor_sub.add_parser("consult")
    p.add_argument("--prompt-file", required=True, dest="prompt_file")
    p.add_argument("--artifact", required=True)
    p.add_argument("--linkage", required=True)
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--expect-verdict", default=None, dest="expect_verdict")

    p_turn = sub.add_parser("turn", help="supervised confined production turn")
    p_turn.add_argument("--project", default=None)
    turn_sub = p_turn.add_subparsers(dest="turn_command", required=True)
    p = turn_sub.add_parser("run")
    p.add_argument("--prompt-file", required=True, dest="prompt_file")
    p.add_argument("--envelope", action="append", required=True)
    p.add_argument("--gate-envelope", action="append", default=[],
                   dest="gate_envelope")
    p.add_argument("--gate-command", required=True, dest="gate_command")
    p.add_argument("--declared-in", required=True, dest="declared_in")
    p.add_argument("--step", required=True)
    p.add_argument("--artifact-dir", required=True, dest="artifact_dir")
    p.add_argument("--linkage", required=True)
    p.add_argument("--timeout", type=float, default=900.0)
    p.add_argument("--claude-bin", default="claude", dest="claude_bin")

    p_gate = sub.add_parser("gate", help="mechanized gate execution")
    p_gate.add_argument("--project", default=None)
    gate_sub = p_gate.add_subparsers(dest="gate_command", required=True)
    p = gate_sub.add_parser("run")
    p.add_argument("--command", required=True, dest="gate_cmd")
    p.add_argument("--declared-in", required=True, dest="declared_in")
    p.add_argument("--artifact", required=True)
    p.add_argument("--linkage", required=True)
    p.add_argument("--timeout", type=float, default=1800.0)

    p_control = sub.add_parser("control",
                               help="control.json attributability helpers")
    p_control.add_argument("--project", default=None)
    control_sub = p_control.add_subparsers(dest="control_command", required=True)
    p = control_sub.add_parser("explain")
    p.add_argument("--since-version", type=int, default=None, dest="since_version")


def run(args, out=None) -> int:
    root = find_root(Path.cwd(), getattr(args, "project", None))
    if root is None:
        return _fail("UNINITIALIZED",
                     {"root": getattr(args, "project", None)}, out)
    service = ActivityService(root)
    try:
        if args.command == "status":
            report = service.status()
            report["capabilities"] = _capabilities(report)
            return _emit(report, 0, out)
        if args.command == "activity":
            return _emit(_dispatch_activity(service, args), 0, out)
        if args.command == "stop":
            if args.stop_command == "request":
                result = service.stop_request(reason=args.reason)
                return _emit({"ok": True, **result}, 0, out)
            return _emit(service.stop_check(), 0, out)
        if args.command == "control":
            return _run_control_explain(service, root, out,
                                        since_version=args.since_version)
        if args.command == "advisor":
            from .conduction.consult import AdvisorUnavailable, run_consult
            from .conduction.evidence import EvidenceConflict
            try:
                result = run_consult(root, prompt_file=Path(args.prompt_file),
                                     artifact=Path(args.artifact),
                                     linkage=args.linkage, timeout=args.timeout,
                                     expect_verdict=args.expect_verdict)
            except AdvisorUnavailable as exc:
                return _fail("ADVISOR_UNAVAILABLE", {"reason": str(exc)}, out)
            except EvidenceConflict as exc:
                return _fail("CONFLICT", {"paths": exc.paths}, out)
            if not result["ok"]:
                return _fail("ADVISOR_FAILED",
                             {"outcome": result["outcome"],
                              "exit_code": result["exit_code"],
                              "verdict": result["verdict"],
                              "artifact": result["artifact"]}, out)
            return _emit(result, 0, out)
        if args.command == "turn":
            from .conduction.turn import TurnError, run_turn
            from .conduction.gate import ProvenanceError
            from .conduction.evidence import EvidenceConflict
            try:
                result = run_turn(
                    root, prompt_file=Path(args.prompt_file),
                    envelope=args.envelope, gate_envelope=args.gate_envelope,
                    gate_command=args.gate_command,
                    declared_in=Path(args.declared_in), step=args.step,
                    artifact_dir=Path(args.artifact_dir), linkage=args.linkage,
                    timeout=args.timeout, claude_bin=args.claude_bin)
            except TurnError as exc:
                return _fail(exc.code, exc.detail, out)
            except ProvenanceError as exc:
                return _fail("PROVENANCE", {"reason": str(exc)}, out)
            except EvidenceConflict as exc:
                return _fail("CONFLICT", {"paths": exc.paths}, out)
            if not result["ok"]:
                code = ({"TURN_VIOLATION": "TURN_VIOLATION",
                         "TURN_TAMPERED": "TURN_TAMPERED",
                         "GATE_RED": "GATE_RED"}.get(result["outcome"], "TURN_FAILED"))
                return _fail(code, {"outcome": result["outcome"],
                                    "artifact": result["artifact"]}, out)
            return _emit(result, 0, out)
        if args.command == "gate":
            from .conduction.gate import ProvenanceError, run_gate
            from .conduction.evidence import EvidenceConflict
            try:
                result = run_gate(root, command=args.gate_cmd,
                                  declared_in=Path(args.declared_in),
                                  artifact=Path(args.artifact),
                                  linkage=args.linkage, timeout=args.timeout)
            except ProvenanceError as exc:
                return _fail("PROVENANCE", {"reason": str(exc)}, out)
            except EvidenceConflict as exc:
                return _fail("CONFLICT", {"paths": exc.paths}, out)
            if not result["ok"]:
                return _fail("GATE_RED", {"outcome": result["outcome"],
                                          "exit_code": result["exit_code"],
                                          "artifact": result["artifact"]}, out)
            return _emit(result, 0, out)
        return _fail("USAGE", f"unknown command {args.command!r}", out)
    except ActivityError as exc:
        return _fail(exc.code, exc.detail, out)
    except ControlSchemaError as exc:
        if "does not exist" in str(exc):
            return _fail("UNINITIALIZED", {"root": str(root)}, out)
        return _fail("CORRUPT_CONTROL", {"reason": str(exc)}, out)
    except VersionConflict:
        return _fail("CONFLICT", {"paths": [str(service.store.path)]}, out)
    except NotLockOwner:
        control_token = held_token = None
        try:
            control = service.store.load()
            control_token = ((control.get("activity") or {}).get("turn")
                             or {}).get("token")
        except Exception:  # noqa: BLE001 — best-effort detail only
            pass
        held = service.lock.status().get("owner") or {}
        held_token = held.get("token")
        return _fail("TOKEN_MISMATCH", {"control_token": control_token or "",
                                        "held_token": held_token or ""}, out)
    except (LockHeld, StaleLock) as exc:
        status = service.lock.status()
        return _fail("LOCK_HELD" if isinstance(exc, LockHeld) else "LOCK_SUSPECT",
                     {"lock": {"state": status["state"],
                               "age_seconds": status["age_seconds"]}}, out)
    except MutationMutexBusy:
        status = service.lock.status()
        return _fail("BUSY", {"lock": {"state": status["state"],
                                       "age_seconds": status["age_seconds"]}}, out)
    except OSError as exc:
        return _fail("IO", {"errno": exc.errno,
                            "path": getattr(exc, "filename", None) or ""}, out)


def _dispatch_activity(service: ActivityService, args) -> dict:
    command = args.activity_command
    if command == "start":
        result = service.start(args.activity_type, args.activity_id)
        return {"ok": True, **result}
    if command == "resume":
        result = service.resume(args.activity_id)
        return {"ok": True, **result}
    if command == "suspend":
        result = service.suspend(checkpoint=args.checkpoint, reason=args.reason,
                                 in_flight=args.in_flight,
                                 evidence=args.evidence or None)
        return {"ok": True, **result}
    if command == "conclude":
        return {"ok": True, **service.conclude(args.status)}
    if command == "heartbeat":
        return {"ok": True, **service.heartbeat()}
    if command == "takeover":
        return {"ok": True,
                **service.takeover(reason=args.reason, actor=args.actor)}
    raise _UsageError(f"unknown activity command {command!r}")


def _run_control_explain(service: ActivityService, root: Path, out,
                         since_version: int | None = None) -> int:
    """`regent control explain [--since-version N]` — attributability of the
    exempted operational files vs git HEAD (PLAN-002 choreography), with the
    skill's step-start version snapshot. Unexplained changes exit 3."""
    import json as _json
    import subprocess
    from .activity import explain_control_diff
    try:
        head_raw = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:.regent/control.json"],
            capture_output=True, text=True, check=True).stdout
        before = _json.loads(head_raw)
    except (subprocess.CalledProcessError, ValueError):
        before = None
    after = service.store.load()
    if before is None:
        return _emit({"explained": ["control.json is new in this commit"],
                      "unexplained": []}, 0, out)
    audit_delta = _audit_delta(service, root)
    if audit_delta is None:  # history rewritten or corrupt: default-deny
        diff = {"explained": [], "unexplained": ["audit:history-not-append-only"]}
    else:
        diff = explain_control_diff(before, after, audit_delta,
                                    since_version=since_version)
    if diff["unexplained"]:
        return _fail("UNATTRIBUTABLE", diff, out)
    return _emit(diff, 0, out)


def _audit_delta(service: ActivityService, root: Path) -> list[dict] | None:
    """REAL diff of the append-only audit: HEAD lines must be a PREFIX of the
    worktree lines (rewritten/removed history returns None = default-deny)."""
    import json as _json
    import subprocess
    try:
        head_raw = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:.regent/protocol/audit.jsonl"],
            capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        head_raw = ""
    head_lines = [l for l in head_raw.splitlines() if l.strip()]
    try:
        work_raw = service.audit.path.read_text(encoding="utf-8")
    except OSError:
        work_raw = ""
    work_lines = [l for l in work_raw.splitlines() if l.strip()]
    if work_lines[:len(head_lines)] != head_lines:
        return None  # not append-only relative to HEAD
    delta = []
    for line in work_lines[len(head_lines):]:
        try:
            delta.append(_json.loads(line))
        except ValueError:
            return None  # corrupt new line: default-deny
    return delta


def _capabilities(status_report: dict) -> dict:
    import shutil
    return {"executor": shutil.which("claude") is not None,
            "advisor": shutil.which("codex") is not None,
            "control": isinstance(status_report.get("control"), dict)}
