"""Conduction phase 4 (PLAN-006): rehearsal, the durable arm/disarm safety
gate, and the foreground daemon supervisor.

Safety is the point: the daemon is autonomous PER TURN but never per the
decision to START. Without a valid arm-token issued by the owner it never
drives; any non-STEPS_COMPLETE terminal condition disarms; a loop COMPLETE
means "steps done", NOT "build accepted" — the final review, CONCLUSION.md and
`activity conclude` stay a MEDIATED decision (`/regent`), not the daemon's.

All arm-token mutations (write, discard, disarm) are serialized by a flock so
check-and-delete is an ATOMIC compare-and-swap: an old daemon (arm_id A) can
never race a rearm (arm_id B) and delete B. Every removal fsyncs the directory
so a token can't be resurrected by a crash after unlink.
"""

from __future__ import annotations

import json
import os
import signal
import time
import uuid
from pathlib import Path

from ..activity import ActivityService
from ..protocol.control import _FlockMutex, MutationMutexBusy
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


def _arm_lock(state_dir: Path) -> _FlockMutex:
    return _FlockMutex(Path(state_dir) / "arm.lock", timeout=5.0)


def _conclusion_path(root: Path, plan_id: str) -> Path:
    return root / ".regent" / "plans" / plan_id / "build" / "CONCLUSION.md"


def _fsync_dir(path: Path) -> None:
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _unlink_durable(path: Path) -> None:
    try:
        path.unlink()
        _fsync_dir(path)  # a crash after unlink must not resurrect the token
    except OSError:
        pass


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
    _fsync_dir(path)


def _raw_arm(state_dir: Path) -> dict | None:
    try:
        return json.loads(_arm_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _validate_arm_config(root: Path, plan_id: str, config: dict) -> None:
    """A daemon armed with a broken config would fail LATE (or, worse, drive an
    empty plan straight to STEPS_COMPLETE). Validate the whole loop config up
    front, at arm time, so a bad arm never succeeds."""
    plan_dir = (root / ".regent" / "plans" / plan_id).resolve()
    if not Path(config.get("prompt_template", "")).is_file():
        raise SupervisorError("NOT_EXECUTABLE",
                              {"reason": "prompt_template not a file"})
    declared_in = Path(config.get("declared_in", ""))
    try:
        resolved = declared_in.resolve()
    except OSError:
        resolved = declared_in
    if not declared_in.is_file() or plan_dir not in resolved.parents:
        raise SupervisorError("NOT_EXECUTABLE",
                              {"reason": "declared_in must be the plan's own file"})
    plan_text = declared_in.read_text(encoding="utf-8", errors="replace")
    steps = _declared_steps(plan_text)
    if not steps:
        raise SupervisorError("NOT_EXECUTABLE", {"reason": "plan declares no steps"})
    if any(_step_gate(plan_text, s) is None for s in steps):
        raise SupervisorError("NOT_EXECUTABLE", {"reason": "a step declares no gate"})
    artifact_dir = Path(config.get("artifact_dir", ""))
    regent_dir = (root / ".regent").resolve()
    try:
        art_resolved = artifact_dir.resolve()
    except OSError:
        art_resolved = artifact_dir
    if regent_dir not in art_resolved.parents and art_resolved != regent_dir:
        raise SupervisorError("NOT_EXECUTABLE",
                              {"reason": "artifact_dir must live under .regent"})
    envelope = config.get("envelope") or []
    if not isinstance(envelope, list) or not envelope:
        raise SupervisorError("NOT_EXECUTABLE", {"reason": "envelope required"})


def arm(service: ActivityService, *, plan_id: str, config: dict) -> dict:
    """Hard preconditions: an ACTIVE build activity matching the plan, APPROVED,
    no CONCLUSION.md, executable workspace, current token, and a VALID loop
    config. Never authorizes a future activity."""
    root = service.root
    try:
        with _arm_lock(service.state_dir):
            # An arm-token for a DIFFERENT plan on disk must be disarmed
            # explicitly first — checked (RAW, before anything else) inside the
            # lock so a leftover is never overwritten blind or raced.
            existing = _raw_arm(service.state_dir)
            if existing is not None and existing.get("plan_id") != plan_id:
                raise SupervisorError("ALREADY_ARMED",
                                      {"armed_plan": existing.get("plan_id")})
            _validate_arm_config(root, plan_id, config)
            control = service.store.load()
            activity = control.get("activity")
            if activity is None or activity["state"] != "ACTIVE" \
                    or activity["type"] != "build" or activity["id"] != plan_id:
                raise SupervisorError(
                    "NOT_EXECUTABLE",
                    {"reason": "no matching ACTIVE build activity"})
            if _approval_status(root, plan_id) != "APPROVED":
                raise SupervisorError("NOT_EXECUTABLE",
                                      {"reason": "plan not APPROVED"})
            if _conclusion_path(root, plan_id).exists():
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
    except MutationMutexBusy:
        raise SupervisorError("NOT_EXECUTABLE", {"reason": "arm lock busy"})


def read_arm(service: ActivityService) -> dict | None:
    """Returns the arm-token iff it is still bound to the CURRENT activity
    (plan/epoch/token). A takeover (token rotated) or epoch change invalidates
    it — discarded (under the lock) with an audit record, never survives a
    cycle."""
    payload = _raw_arm(service.state_dir)
    if payload is None:
        return None
    activity = service.store.load().get("activity") or {}
    cur_token = (activity.get("turn") or {}).get("token") if activity.get("state") == \
        "ACTIVE" else (activity.get("suspension") or {}).get("owning_turn")
    bound = (payload.get("plan_id") == activity.get("id")
             and payload.get("activity_epoch") == activity.get("epoch")
             and payload.get("turn_token") == cur_token)
    if bound:
        return payload
    # Discard the stale token atomically: re-read under the lock and only remove
    # it if it is STILL the same stale arm_id (a rearm in the window is kept).
    try:
        with _arm_lock(service.state_dir):
            current = _raw_arm(service.state_dir)
            if current is not None and current.get("arm_id") == payload.get("arm_id"):
                service.audit.append({"event": "arm_token_discarded",
                                      "arm_id": payload.get("arm_id"),
                                      "reason": "binding no longer current"})
                _unlink_durable(_arm_path(service.state_dir))
    except MutationMutexBusy:
        pass
    return None


def disarm(service: ActivityService, *, arm_id: str | None = None) -> dict:
    """Atomic CAS by arm_id under the lock: an old daemon (arm_id A) never
    removes a rearm (arm_id B)."""
    try:
        with _arm_lock(service.state_dir):
            payload = _raw_arm(service.state_dir)
            if payload is None:
                return {"disarmed": False, "reason": "no arm token"}
            if arm_id is not None and payload.get("arm_id") != arm_id:
                return {"disarmed": False, "reason": "arm_id mismatch (rearmed)"}
            _unlink_durable(_arm_path(service.state_dir))
            return {"disarmed": True, "arm_id": payload.get("arm_id")}
    except MutationMutexBusy:
        return {"disarmed": False, "reason": "arm lock busy"}


# -- foreground daemon ----------------------------------------------------

def run_daemon(service: ActivityService, *, poll: float = 5.0,
               claude_bin: str = "claude", once: bool = False,
               runner=None, on_state=None) -> dict:
    """Foreground supervisor. Drives an ARMED build via run_loop, re-checking the
    arm AND the absence of CONCLUSION.md before every turn (guard). It never
    STARTS work without a valid arm-token and DISARMS on every terminal
    condition — including COMPLETE, which it reports as STEPS_COMPLETE (the
    mediated final review/CONCLUSION/conclude is the owner's). Any unexpected
    failure disarms too. SIGINT/SIGTERM disarm and exit."""
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
            conclusion = _conclusion_path(root, armed["plan_id"])

            def guard(_arm_id=arm_id, _conc=conclusion) -> bool:
                # Bar STARTING the next turn on: a signal, a mediated conclusion
                # appearing mid-run, or the arm being removed/rearmed.
                if stopping["flag"] or _conc.exists():
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
            except Exception as exc:  # noqa: BLE001 — any failure must disarm
                disarm(service, arm_id=arm_id)
                emit("FAILED", {"error": f"{type(exc).__name__}: {exc}"})
                return _result("FAILED", transitions)

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


_TERMINAL_OK = {"STEPS_COMPLETE", "IDLE"}


def _result(state: str, transitions: list[str], **extra) -> dict:
    return {"final_state": state, "ok": state in _TERMINAL_OK,
            "transitions": transitions, **extra}


def _now() -> str:
    from ..protocol.audit import utcnow
    return utcnow()
