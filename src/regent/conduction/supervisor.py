"""Conduction phase 4 (PLAN-006): rehearsal, the durable arm/disarm safety
gate, and the foreground daemon supervisor.

Safety is the point: the daemon is autonomous PER TURN but never per the
decision to START. Without a valid arm-token issued by the owner it never
drives; any non-STEPS_COMPLETE terminal condition disarms; a loop COMPLETE
means "steps done", NOT "build accepted" — the final review, CONCLUSION.md and
`activity conclude` stay a MEDIATED decision (`/regent`), not the daemon's.
"""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from pathlib import Path

from ..activity import ActivityService
from .loop import (LoopError, _approval_status, _attempt_number, _committed_steps,
                   _declared_steps, _step_gate, run_loop)


class SupervisorError(Exception):
    def __init__(self, code: str, detail: dict) -> None:
        super().__init__(code)
        self.code, self.detail = code, detail


# -- rehearsal (read-only) ------------------------------------------------

def rehearse(root: Path, *, plan_id: str, declared_in: Path) -> dict:
    root = Path(root).resolve()
    artifact_dir = (root / ".regent" / "plans" / plan_id / "build").resolve()
    plan_text = Path(declared_in).read_text(encoding="utf-8", errors="replace")
    declared = _declared_steps(plan_text)
    done = _committed_steps(root, plan_id)
    pending = []
    for step in declared:
        if step in done:
            continue
        pending.append({"step": step, "gate": _step_gate(plan_text, step),
                        "next_attempt": _attempt_number(artifact_dir, step)})
    return {"plan": plan_id, "done": sorted(done), "pending": pending,
            "complete": not pending}


# -- arm / disarm (durable safety gate) -----------------------------------

def _arm_path(state_dir: Path) -> Path:
    return Path(state_dir) / "arm.token"


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            h.write(text)
            h.flush()
            os.fsync(h.fileno())
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, path)
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _raw_arm(state_dir: Path) -> dict | None:
    try:
        return json.loads(_arm_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def arm(service: ActivityService, *, plan_id: str, config: dict) -> dict:
    """Hard preconditions: an ACTIVE build activity matching the plan, APPROVED,
    no CONCLUSION.md, executable workspace, current token. Never authorizes a
    future activity."""
    root = service.root
    # An arm-token for a DIFFERENT plan on disk must be disarmed explicitly
    # first — checked on the RAW file (before binding validation) so a leftover
    # never forces the owner to overwrite it blind.
    existing = _raw_arm(service.state_dir)
    if existing is not None and existing.get("plan_id") != plan_id:
        raise SupervisorError("ALREADY_ARMED", {"armed_plan": existing.get("plan_id")})
    control = service.store.load()
    activity = control.get("activity")
    if activity is None or activity["state"] != "ACTIVE" \
            or activity["type"] != "build" or activity["id"] != plan_id:
        raise SupervisorError("NOT_EXECUTABLE",
                              {"reason": "no matching ACTIVE build activity"})
    if _approval_status(root, plan_id) != "APPROVED":
        raise SupervisorError("NOT_EXECUTABLE", {"reason": "plan not APPROVED"})
    if (root / ".regent" / "plans" / plan_id / "build" / "CONCLUSION.md").exists():
        raise SupervisorError("ALREADY_CONCLUDED", {"plan": plan_id})
    verdict = service.status()["workspace"]["verdict"]
    if verdict not in ("OK", "SUSPENDED_OK", "IDLE_CLEAN"):
        raise SupervisorError("NOT_EXECUTABLE", {"workspace": verdict})
    token = activity["turn"]["token"]
    payload = {"arm_id": uuid.uuid4().hex, "plan_id": plan_id,
               "activity_epoch": activity["epoch"], "turn_token": token,
               "armed_at": _now(), "config": config}
    _atomic_write(_arm_path(service.state_dir), json.dumps(payload))
    return payload


def read_arm(service: ActivityService) -> dict | None:
    """Returns the arm-token iff it is still bound to the CURRENT activity
    (plan/epoch/token). A takeover (token rotated) or epoch change invalidates
    it — discarded with an audit record, never survives a cycle."""
    path = _arm_path(service.state_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    activity = service.store.load().get("activity") or {}
    cur_token = (activity.get("turn") or {}).get("token") if activity.get("state") == \
        "ACTIVE" else (activity.get("suspension") or {}).get("owning_turn")
    bound = (payload.get("plan_id") == activity.get("id")
             and payload.get("activity_epoch") == activity.get("epoch")
             and payload.get("turn_token") == cur_token)
    if not bound:
        service.audit.append({"event": "arm_token_discarded",
                              "arm_id": payload.get("arm_id"),
                              "reason": "binding no longer current"})
        try:
            path.unlink()
        except OSError:
            pass
        return None
    return payload


def disarm(service: ActivityService, *, arm_id: str | None = None) -> dict:
    """CAS by arm_id: an old daemon (arm_id A) never removes a rearm (arm_id B)."""
    path = _arm_path(service.state_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"disarmed": False, "reason": "no arm token"}
    if arm_id is not None and payload.get("arm_id") != arm_id:
        return {"disarmed": False, "reason": "arm_id mismatch (rearmed)"}
    try:
        path.unlink()
    except OSError:
        pass
    return {"disarmed": True, "arm_id": payload.get("arm_id")}


# -- foreground daemon ----------------------------------------------------

def run_daemon(service: ActivityService, *, poll: float = 5.0,
               claude_bin: str = "claude", once: bool = False,
               runner=None, on_state=None) -> dict:
    """Foreground supervisor. Drives an ARMED build via run_loop, re-checking the
    arm before every turn (guard). It never STARTS work without a valid arm-token
    and DISARMS on every terminal condition — including COMPLETE, which it reports
    as STEPS_COMPLETE (the mediated final review/CONCLUSION/conclude is the
    owner's). SIGINT/SIGTERM disarm and exit."""
    root = service.root
    stopping = {"flag": False}

    def _sig(_signum, _frame):
        stopping["flag"] = True
    old_int = signal.signal(signal.SIGINT, _sig)
    old_term = signal.signal(signal.SIGTERM, _sig)
    transitions: list[str] = []

    def emit(state: str, extra: dict | None = None) -> None:
        transitions.append(state)
        if on_state is not None:
            on_state(state, extra or {})

    try:
        while True:
            if stopping["flag"]:
                disarm(service)
                emit("SIGNALLED")
                return _result("SIGNALLED", transitions)
            armed = read_arm(service)
            if armed is None:
                emit("IDLE")
                if once:
                    return _result("IDLE", transitions)
                time.sleep(poll)
                continue
            if service.stop_check()["stop_requested"]:
                disarm(service, arm_id=armed["arm_id"])
                emit("STOPPED")
                return _result("STOPPED", transitions)

            emit("RUNNING", {"plan": armed["plan_id"], "arm_id": armed["arm_id"]})
            cfg = armed["config"]
            arm_id = armed["arm_id"]

            def guard(_arm_id=arm_id) -> bool:
                if stopping["flag"]:
                    return False
                cur = read_arm(service)
                return cur is not None and cur["arm_id"] == _arm_id

            try:
                result = run_loop(
                    root, plan_id=armed["plan_id"],
                    prompt_template=Path(cfg["prompt_template"]),
                    envelope=cfg["envelope"], gate_envelope=cfg.get("gate_envelope"),
                    declared_in=Path(cfg["declared_in"]),
                    artifact_dir=Path(cfg["artifact_dir"]),
                    max_turns=cfg.get("max_turns", 20),
                    timeout=cfg.get("timeout", 900.0), claude_bin=claude_bin,
                    runner=runner, service=service, guard=guard)
            except LoopError as exc:
                disarm(service, arm_id=arm_id)
                emit(exc.code)
                return _result(exc.code, transitions)

            cond = result["stop_condition"]
            # A loop COMPLETE = steps done, NOT accepted: report STEPS_COMPLETE
            # and disarm; the mediated final review/CONCLUSION/conclude is the
            # owner's, never the daemon's.
            state = "STEPS_COMPLETE" if cond == "COMPLETE" else cond
            disarm(service, arm_id=arm_id)  # every terminal condition disarms
            emit(state, {"turns": result["count"]})
            return _result(state, transitions, turns=result["count"])
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)


_TERMINAL_OK = {"STEPS_COMPLETE", "IDLE", "SIGNALLED"}


def _result(state: str, transitions: list[str], **extra) -> dict:
    return {"final_state": state, "ok": state in _TERMINAL_OK,
            "transitions": transitions, **extra}


def _now() -> str:
    from ..protocol.audit import utcnow
    return utcnow()
