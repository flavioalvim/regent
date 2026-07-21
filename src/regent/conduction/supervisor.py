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
    """Remove the token and fsync the directory so a crash after unlink cannot
    resurrect it. The dir-fsync is the DURABILITY BARRIER and runs even when the
    file is already gone (a prior unlink whose fsync had failed): removal is not
    'done' until that fsync SUCCEEDS. Any fsync/unlink error other than a missing
    file PROPAGATES, so a caller never reports a removal that isn't durable."""
    try:
        path.unlink()
    except FileNotFoundError:
        pass  # already unlinked from the namespace — still fsync below
    _fsync_dir(path)  # OSError here propagates: durability is not assured


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


_ARM_KEYS = {"arm_id", "plan_id", "activity_epoch", "turn_token", "config"}


def _raw_arm(state_dir: Path) -> dict | None:
    try:
        data = json.loads(_arm_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None  # non-dict JSON is not a token


def _well_formed(payload: dict) -> bool:
    """A token missing arm_id/config would later KeyError past the daemon's
    failure handler — so an ill-formed token is never returned as valid."""
    return _ARM_KEYS <= set(payload) and isinstance(payload.get("config"), dict)


def _validate_arm_config(root: Path, plan_id: str, config: dict) -> dict:
    """A daemon armed with a broken config would fail LATE (or, worse, drive an
    empty plan straight to STEPS_COMPLETE). Validate the whole loop config up
    front, at arm time, so a bad arm never succeeds — and return a CANONICAL
    copy with every path resolved to an ABSOLUTE one, so the daemon behaves
    identically no matter which directory it is launched from."""
    plan_dir = (root / ".regent" / "plans" / plan_id).resolve()
    template = Path(config.get("prompt_template", ""))
    if not template.is_file():
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
    canonical = dict(config)
    canonical["prompt_template"] = str(template.resolve())
    canonical["declared_in"] = str(resolved)
    canonical["artifact_dir"] = str(art_resolved)
    canonical["envelope"] = [str(Path(p).resolve()) for p in envelope]
    if config.get("gate_envelope"):
        canonical["gate_envelope"] = [str(Path(p).resolve())
                                      for p in config["gate_envelope"]]
    return canonical


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
            config = _validate_arm_config(root, plan_id, config)  # canonicalized
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
    bound = (_well_formed(payload)  # a malformed token is never treated as valid
             and payload.get("plan_id") == activity.get("id")
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
                try:
                    _unlink_durable(_arm_path(service.state_dir))
                except OSError:
                    pass  # leave it; re-evaluated next cycle (never claims removed)
                else:  # audit ONLY after the removal actually succeeded
                    service.audit.append({"event": "arm_token_discarded",
                                          "arm_id": payload.get("arm_id"),
                                          "reason": "binding no longer current"})
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
                # The file may be gone from the namespace but from an unlink whose
                # dir-fsync had failed — run the durability barrier before calling
                # it "already gone", so we never claim a non-durable removal.
                try:
                    _unlink_durable(_arm_path(service.state_dir))
                except OSError as exc:
                    return {"disarmed": False, "reason": f"fsync failed: {exc}"}
                return {"disarmed": False, "reason": "no arm token"}
            if arm_id is not None and payload.get("arm_id") != arm_id:
                return {"disarmed": False, "reason": "arm_id mismatch (rearmed)"}
            try:
                _unlink_durable(_arm_path(service.state_dir))
            except OSError as exc:  # never report a removal that did not happen
                return {"disarmed": False, "reason": f"unlink failed: {exc}"}
            return {"disarmed": True, "arm_id": payload.get("arm_id")}
    except MutationMutexBusy:
        return {"disarmed": False, "reason": "arm lock busy"}


# -- foreground daemon ----------------------------------------------------

# Disarm reasons that mean the token is already effectively gone (removed or
# superseded by a rearm) — NOT a failure to remove.
_BENIGN_DISARM = ("no arm token", "arm_id mismatch (rearmed)")


def _confirm_disarmed(service: ActivityService, *, arm_id: str | None) -> bool:
    """Disarm and CONFIRM the token is gone, retrying transient failures. Returns
    False only if, after retries, a real removal failure persists — the caller
    must then NOT report a clean terminal (the token is still armed)."""
    for _ in range(3):
        d = disarm(service, arm_id=arm_id)
        if d["disarmed"] or d.get("reason") in _BENIGN_DISARM:
            return True
    return False


def _confirm_absent_durable(service: ActivityService) -> str:
    """The IDLE path must not report a clean terminal over a prior unlink whose
    dir-fsync had failed. Under the lock: if a token is present (a rearm raced
    in) → "present" (re-evaluate, never delete it); if absent → run the dir-fsync
    barrier so the absence is DURABLE → "durable", or "failed" if the fsync
    fails. Retries transient fsync failures."""
    for _ in range(3):
        try:
            with _arm_lock(service.state_dir):
                if _raw_arm(service.state_dir) is not None:
                    return "present"
                try:
                    _fsync_dir(_arm_path(service.state_dir))
                except OSError:
                    continue  # transient; retry
                return "durable"
        except MutationMutexBusy:
            continue
    return "failed"


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
        if on_state is None:
            return
        try:
            on_state(state, extra or {})
        except Exception:  # noqa: BLE001 — a broken sink (e.g. BrokenPipeError)
            # must never escape un-disarmed; flag a stop so the guard halts the
            # loop and the terminal path disarms cleanly.
            stopping["flag"] = True

    def finish(state: str, *, arm_id: str | None = None,
               extra: dict | None = None) -> dict:
        # Every terminal path funnels here so it ACTS on the disarm result: if
        # the token could not be removed, report DISARM_FAILED (still armed)
        # instead of a clean terminal — a later run must not re-drive silently.
        if not _confirm_disarmed(service, arm_id=arm_id):
            state = "DISARM_FAILED"
        emit(state, extra)
        return _result(state, transitions, **(extra or {}))

    try:
        while True:
            if stopping["flag"]:
                return finish("SIGNALLED")
            armed = read_arm(service)
            if armed is None:
                # Confirm the absence is DURABLE (a prior unlink may not have
                # fsynced) before reporting a clean IDLE — without clobbering a
                # concurrent rearm.
                status = _confirm_absent_durable(service)
                if status == "present":
                    continue  # a rearm appeared; re-evaluate
                if status == "failed":
                    emit("DISARM_FAILED")
                    return _result("DISARM_FAILED", transitions)
                emit("IDLE")
                if once:
                    return _result("IDLE", transitions)
                time.sleep(poll)
                continue
            if service.stop_check()["stop_requested"]:
                return finish("STOPPED", arm_id=armed["arm_id"])

            emit("RUNNING", {"plan": armed["plan_id"], "arm_id": armed["arm_id"]})
            cfg = armed["config"]
            arm_id = armed["arm_id"]
            conclusion = _conclusion_path(root, armed["plan_id"])

            plan = armed["plan_id"]

            def guard(_arm_id=arm_id, _conc=conclusion, _plan=plan) -> bool:
                # Bar STARTING the next turn on: a signal, a mediated conclusion
                # appearing mid-run, APPROVAL revoked after the loop's own check,
                # or the arm being removed/rearmed.
                if stopping["flag"] or _conc.exists():
                    return False
                if _approval_status(root, _plan) != "APPROVED":
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
                return finish(exc.code, arm_id=arm_id)
            except Exception as exc:  # noqa: BLE001 — any failure must disarm
                return finish("FAILED", arm_id=arm_id,
                              extra={"error": f"{type(exc).__name__}: {exc}"})

            cond = result["stop_condition"]
            # A loop COMPLETE = steps done, NOT accepted: report STEPS_COMPLETE
            # and disarm; the mediated final review/CONCLUSION/conclude is the
            # owner's, never the daemon's.
            state = "STEPS_COMPLETE" if cond == "COMPLETE" else cond
            return finish(state, arm_id=arm_id, extra={"turns": result["count"]})
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
