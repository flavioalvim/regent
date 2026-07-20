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
    "NOT_SUSPENDED": 2, "ACTIVITY_OPEN": 2, "ACTIVITY": 2,
    "TOKEN_MISMATCH": 3, "LOCK_HELD": 3, "LOCK_SUSPECT": 3, "BUSY": 3,
    "CONFLICT": 3, "CORRUPT_CONTROL": 4, "IO": 5,
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
    stop_sub.add_parser("request")
    stop_sub.add_parser("check")


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
                result = service.stop_request()
                return _emit({"ok": True, **result}, 0, out)
            return _emit(service.stop_check(), 0, out)
        return _fail("USAGE", f"unknown command {args.command!r}", out)
    except ActivityError as exc:
        return _fail(exc.code, exc.detail, out)
    except ControlSchemaError as exc:
        if "does not exist" in str(exc):
            return _fail("UNINITIALIZED", {"root": str(root)}, out)
        return _fail("CORRUPT_CONTROL", {"reason": str(exc)}, out)
    except VersionConflict as exc:
        return _fail("CONFLICT", {"paths": [str(service.store.path)],
                                  "reason": str(exc)}, out)
    except NotLockOwner as exc:
        return _fail("TOKEN_MISMATCH", {"control_token": None,
                                        "held_token": None,
                                        "reason": str(exc)}, out)
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
        return _fail("IO", {"errno": exc.errno, "path": getattr(exc, "filename", None)},
                     out)


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


def _capabilities(status_report: dict) -> dict:
    import shutil
    return {"executor": shutil.which("claude") is not None,
            "advisor": shutil.which("codex") is not None,
            "control": isinstance(status_report.get("control"), dict)}
