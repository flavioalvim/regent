"""Durable abort-request signalling (PLAN-005 STEP-01).

A `regent loop abort` writes an abort-request into the DISPOSABLE XDG state
(outside the repo), bound to {activity_id, activity_epoch, turn_token} plus the
in-flight turn nonce. The in-flight turn's keep-alive reads it (~1s), validates
the binding, and — only if a matching turn is in flight — signals cancellation.
Honored exactly once (rename to `.claimed`); a request whose binding no longer
matches is discarded with an audit record. Creation is O_EXCL: one pending
abort at a time.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from ..protocol.audit import AuditLog, utcnow


class AbortPending(Exception):
    """An abort-request is already pending (O_EXCL)."""


def request_path(state_dir: Path) -> Path:
    return Path(state_dir) / "abort.request"


def write_abort_request(state_dir: Path, *, activity_id: str, activity_epoch: int,
                        turn_token: str | None, reason: str) -> dict:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {"id": uuid.uuid4().hex, "activity_id": activity_id,
               "activity_epoch": activity_epoch, "turn_token": turn_token,
               "turn_nonce": _turn_in_flight(state_dir),  # bind to the CURRENT turn
               "reason": reason, "requested_at": utcnow()}
    path = request_path(state_dir)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise AbortPending(str(path)) from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return payload


def write_turn_nonce(state_dir: Path, nonce: str) -> None:
    """Marks a turn in flight (atomic tmp+replace)."""
    target = Path(state_dir) / "turn.nonce"
    tmp = target.with_name(".turn.nonce.tmp")
    tmp.write_text(nonce, encoding="utf-8")
    os.replace(tmp, target)


def clear_turn_nonce(state_dir: Path) -> None:
    try:
        (Path(state_dir) / "turn.nonce").unlink()
    except OSError:
        pass


def _turn_in_flight(state_dir: Path) -> str | None:
    try:
        return (Path(state_dir) / "turn.nonce").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def claim_matching_abort(state_dir: Path, audit: AuditLog, *, activity_id: str,
                         activity_epoch: int, turn_token: str | None) -> dict | None:
    """Returns and CLAIMS (rename → .claimed) a valid abort-request bound to the
    current activity while a turn is in flight; discards a stale one (audited);
    returns None if there is none/not honorable."""
    path = request_path(state_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    in_flight = _turn_in_flight(state_dir)
    bound = (payload.get("activity_id") == activity_id
             and payload.get("activity_epoch") == activity_epoch
             and payload.get("turn_token") == turn_token
             and payload.get("turn_nonce") is not None
             and payload.get("turn_nonce") == in_flight)  # SAME turn, not just any
    if not bound:
        _discard(path, audit, payload, "binding mismatch or wrong/absent turn nonce")
        return None
    claimed = path.with_name(f"abort.claimed-{payload['id']}")  # unique, never clobbered
    try:
        os.replace(path, claimed)  # single claim
    except OSError:
        return None
    return payload


def pending_claimed(state_dir: Path) -> list[Path]:
    """Unfinished aborts (claimed but not yet reconciled) — for recovery."""
    return sorted(Path(state_dir).glob("abort.claimed-*"))


def clear_claimed(state_dir: Path) -> None:
    for p in pending_claimed(state_dir):
        try:
            p.unlink()
        except OSError:
            pass


def _discard(path: Path, audit: AuditLog, payload: dict, reason: str) -> None:
    audit.append({"event": "abort_request_discarded", "request_id": payload.get("id"),
                  "reason": reason})
    try:
        path.unlink()
    except OSError:
        pass
