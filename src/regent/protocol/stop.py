"""Durable stop-request: representation and transitions (REQ-004 §3–4, reduced).

DELIBERATELY REDUCED SCOPE (PLAN-001 STEP-03): this module implements the
durable representation and the control-side transitions only. The full
canonical stop sequence, `--abort` and the `CANCELLED` consultation outcome
require the conduction layer (daemon) and are implemented in that phase.

Staleness rule (normative, PLAN-001 schema v1): a stop_request is STALE iff
its activity_id/activity_epoch diverge from the current activity, OR its
turn_token is non-null and diverges from the current turn token (takeover
rotates the token, so requests aimed at the previous holder expire — ABA
fencing). turn_token=null is the mediator channel: valid for the activity
regardless of which turn serves it.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from .audit import utcnow
from .control import ControlSchemaError, ControlStore


def record_stop_request(store: ControlStore, *, turn_token: str | None = None) -> dict:
    """Records a stop request bound to the current activity. Idempotent: an
    equivalent pending request (same activity/epoch/token) is returned as-is."""
    result: dict[str, Any] = {}

    def fn(body: dict) -> dict:
        activity = body.get("activity")
        if activity is None:
            raise ControlSchemaError("no activity to stop")
        existing = body.get("stop_request")
        if existing is not None and _matches_current(existing, body) \
                and existing.get("turn_token") == turn_token:
            result.update(existing)  # idempotent re-request
            return body
        request = {"id": uuid.uuid4().hex,
                   "activity_id": activity["id"],
                   "activity_epoch": activity["epoch"],
                   "turn_token": turn_token,
                   "requested_at": utcnow()}
        body["stop_request"] = request
        result.update(request)
        return body

    store.mutate(fn)
    return result


def read_valid_stop_request(store: ControlStore) -> dict | None:
    """Returns the pending stop request, or None. A stale request is discarded
    (with an audit record) and None is returned."""
    control = store.load()
    request = control.get("stop_request")
    if request is None:
        return None
    if _matches_current(request, control):
        return dict(request)

    def discard(body: dict) -> dict:
        pending = body.get("stop_request")
        if pending is not None and pending.get("id") == request["id"]:
            body["stop_request"] = None
        return body

    store.mutate(discard)
    store.audit.append({"event": "stop_request_discarded", "request_id": request["id"],
                        "reason": "stale (activity or turn diverged)",
                        "activity_id": request.get("activity_id"),
                        "activity_epoch": request.get("activity_epoch"),
                        "turn_token": request.get("turn_token")})
    return None


def suspend_activity(store: ControlStore, *, turn_token: str, checkpoint: str,
                     reason: str, in_flight: str | None = None) -> bool:
    """ACTIVE → SUSPENDED with the full REQ-004 §5 payload; consumes any pending
    stop request. Idempotent: returns False if already suspended at the same
    checkpoint (no-op), True if the transition was applied."""
    applied = False

    def fn(body: dict) -> dict:
        nonlocal applied
        activity = body.get("activity")
        if activity is None:
            raise ControlSchemaError("no activity to suspend")
        if activity["state"] == "SUSPENDED":
            if (activity.get("suspension") or {}).get("checkpoint") == checkpoint:
                return body  # idempotent re-apply
            raise ControlSchemaError("already suspended at a different checkpoint")
        current_token = (activity.get("turn") or {}).get("token")
        if current_token != turn_token:
            from .control import NotLockOwner
            raise NotLockOwner("suspend requires the current turn token")
        activity["suspension"] = {"previous_state": activity["state"],
                                  "checkpoint": checkpoint,
                                  "owning_turn": current_token,
                                  "in_flight": in_flight,
                                  "reason": reason,
                                  "at": utcnow()}
        activity["state"] = "SUSPENDED"
        activity["turn"] = None
        body["stop_request"] = None  # consumed by the suspension
        applied = True
        return body

    store.mutate(fn)
    return applied


def _matches_current(request: Mapping[str, Any], control: Mapping[str, Any]) -> bool:
    activity = control.get("activity")
    if activity is None:
        return False
    if request.get("activity_id") != activity.get("id") \
            or request.get("activity_epoch") != activity.get("epoch"):
        return False
    token = request.get("turn_token")
    if token is None:
        return True  # mediator channel
    current = (activity.get("turn") or {}).get("token")
    return token == current
