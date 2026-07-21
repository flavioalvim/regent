"""Conduction phase 4 (PLAN-006), STEP-01: rehearsal + the durable arm/disarm
safety gate. The foreground daemon supervisor arrives in STEP-02.

Safety is the point: the daemon (STEP-02) is autonomous PER TURN but never per
the decision to START. Without a valid arm-token issued by the owner it never
drives; the arm-token is the owner's durable, activity-bound authorization.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from ..activity import ActivityService
from .loop import (_approval_status, _attempt_number, _committed_steps,
                   _declared_steps, _step_gate)


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


def _now() -> str:
    from ..protocol.audit import utcnow
    return utcnow()
