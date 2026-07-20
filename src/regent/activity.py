"""Application layer: composed activity operations over regent.protocol.

PLAN-002 STEP-01. Each public operation composes two transactional domains —
the turn lock (XDG local state) and the control.json (versioned CAS) — with a
canonical order and idempotent crash recovery. Recovery ALWAYS inspects
(control, lock, local token copy) and acts by the normative 12-row table in
PLAN-002; every entry point runs it first.

Token contract: the AUTHORITATIVE fencing token is control.activity.turn.token;
the XDG `turn.json` is a local convenience copy for the CLI (rows 2/10/11/12
repair it). P-01 is intact: TurnLock.acquire() touches only the XDG side —
`start` is the COMPOSED operation that also mutates control.json.

Canonical orders:
  start:    recover → acquire lock → CAS ACTIVE(epoch=floor+1, token) → write turn.json
  suspend:  recover → CAS SUSPENDED(payload+evidence) → release lock → clear turn.json
  resume:   recover → acquire lock → CAS ACTIVE(epoch+1, new token) → write turn.json
  conclude: recover → CAS(last_concluded, activity=null) → release lock → clear turn.json
A crash between any two steps lands on a table row; re-running recovers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .protocol import (AuditLog, ControlStore, NotLockOwner, TurnLock,
                       record_stop_request, read_valid_stop_request,
                       suspend_activity)
from .protocol.control import _FlockMutex
from .protocol.audit import utcnow
from .protocol.control import ACTIVITY_TYPES, ControlSchemaError

_CRASH_POINTS: set[str] = set()  # test hook: os._exit(43) at named boundaries


def _maybe_crash(point: str) -> None:
    if point in _CRASH_POINTS:
        os._exit(43)


class ActivityError(Exception):
    code = "USAGE"  # subclasses override; base = caller misuse

    def __init__(self, detail: Any = None, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.detail = detail


class NoActivity(ActivityError):
    code = "NO_ACTIVITY"


class NotActive(ActivityError):
    code = "NOT_ACTIVE"


class NotSuspended(ActivityError):
    code = "NOT_SUSPENDED"


class ActivityOpen(ActivityError):
    code = "ACTIVITY_OPEN"


class TokenMismatch(ActivityError):
    code = "TOKEN_MISMATCH"


class LockSuspectError(ActivityError):
    code = "LOCK_SUSPECT"


def default_state_dir(repo_root: Path) -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME",
                               str(Path.home() / ".local" / "state")))
    digest = hashlib.sha256(str(Path(repo_root).resolve()).encode()).hexdigest()[:16]
    return base / "regent" / digest


class ActivityService:
    def __init__(self, repo_root: Path, state_dir: Path | None = None) -> None:
        self.root = Path(repo_root).resolve()
        self.state_dir = Path(state_dir) if state_dir else default_state_dir(self.root)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        regent_dir = self.root / ".regent"
        self.audit = AuditLog(regent_dir / "protocol" / "audit.jsonl")
        self.store = ControlStore(regent_dir / "control.json", self.audit,
                                  lock_file=self.state_dir / "control.lock")
        self.lock = TurnLock(self.state_dir, self.audit)
        self.token_file = self.state_dir / "turn.json"
        # PLAN-002 STEP-06 (advisor blocker 1): composed operations are
        # serialized per host under a dedicated ops flock — recover→acquire→
        # CAS→turn.json is one unit; another process can never misread an
        # in-flight start as a crashed row-8 state and release its lock.
        self._ops_lock = self.state_dir / "ops.lock"

    def _ops_mutex(self) -> _FlockMutex:
        return _FlockMutex(self._ops_lock, 60.0)

    # -- public operations: each composed op is ONE serialized unit ---------

    def start(self, activity_type: str, activity_id: str) -> dict:
        with self._ops_mutex():
            return self._start_locked(activity_type, activity_id)

    def resume(self, activity_id: str | None = None) -> dict:
        with self._ops_mutex():
            return self._resume_locked(activity_id)

    def suspend(self, **kwargs) -> dict:
        with self._ops_mutex():
            return self._suspend_locked(**kwargs)

    def conclude(self, status: str) -> dict:
        with self._ops_mutex():
            return self._conclude_locked(status)

    def heartbeat(self) -> dict:
        with self._ops_mutex():
            return self._heartbeat_locked()

    def takeover(self, **kwargs) -> dict:
        with self._ops_mutex():
            return self._takeover_locked(**kwargs)

    def stop_request(self, reason: str | None = None) -> dict:
        with self._ops_mutex():
            return self._stop_request_locked(reason)

    def stop_check(self) -> dict:
        with self._ops_mutex():
            return self._stop_check_locked()

    def status(self) -> dict:
        return self._status_locked()  # read-only; no mutation to serialize

    # -- public operations -------------------------------------------------

    def _start_locked(self, activity_type: str, activity_id: str) -> dict:
        if activity_type not in ACTIVITY_TYPES:
            raise ActivityError(f"unknown activity type: {activity_type!r}",
                                "unknown activity type")  # USAGE: detail is str
        control = self._recover()
        if control["activity"] is not None:
            raise ActivityOpen({"activity": _activity_obj(control["activity"])})
        token = self.lock.acquire()
        _maybe_crash("start:after_lock")
        epoch = self._floor(control) + 1
        control = self.store.mutate(lambda body: _set_active(
            body, activity_type, activity_id, epoch, token))
        if (control["activity"] or {}).get("turn", {}).get("token") != token:
            # Raced: another start won between our recover and CAS. Undo ours.
            self._release_quietly(token)
            raise ActivityOpen({"activity": _activity_obj(control["activity"])})
        _maybe_crash("start:after_cas")
        self._write_local_token(token)
        return {"activity": _activity_obj(control["activity"]), "token": token,
                "checkpoint": None}

    def _resume_locked(self, activity_id: str | None = None) -> dict:
        control = self._recover()
        activity = control["activity"]
        if activity is None:
            raise NoActivity({"state": "idle"})
        if activity["state"] != "SUSPENDED":
            raise NotSuspended({"state": activity["state"]})
        if activity_id is not None and activity["id"] != activity_id:
            raise ActivityOpen({"activity": _activity_obj(activity)})
        suspension = activity["suspension"]
        token = self.lock.acquire()
        _maybe_crash("resume:after_lock")
        epoch = self._floor(control) + 1  # every (re)start increments (PLAN-001)

        def fn(body: dict) -> dict:
            current = body.get("activity")
            if current is None or current["state"] != "SUSPENDED" \
                    or current["id"] != activity["id"]:
                return body  # raced: do NOT overwrite; caller re-inspects
            body["activity"] = {"type": activity["type"], "id": activity["id"],
                                "epoch": epoch, "state": "ACTIVE",
                                "suspension": None,
                                "turn": {"owner": "executor", "token": token,
                                         "acquired_at": utcnow()}}
            return body

        control = self.store.mutate(fn)
        if (control["activity"] or {}).get("turn", {}).get("token") != token:
            self._release_quietly(token)
            raise NotSuspended({"state": (control["activity"] or {}).get("state",
                                                                          "idle")})
        _maybe_crash("resume:after_cas")
        self._write_local_token(token)
        missing = [p for p in suspension.get("evidence", [])
                   if not (self.root / p).exists()]
        return {"activity": _activity_obj(control["activity"]), "token": token,
                "checkpoint": suspension["checkpoint"],
                "missing_evidence": missing}

    def _suspend_locked(self, *, checkpoint: str, reason: str,
                in_flight: str | None = None,
                evidence: list[str] | None = None) -> dict:
        control = self._recover()
        activity = control["activity"]
        if activity is None:
            raise NoActivity({"state": "idle"})
        if activity["state"] != "ACTIVE":
            raise NotActive({"state": activity["state"]})
        token = activity["turn"]["token"]
        suspend_activity(self.store, turn_token=token, checkpoint=checkpoint,
                         reason=reason, in_flight=in_flight, evidence=evidence)
        _maybe_crash("suspend:after_cas")
        self.lock.release(token)  # strict: a failed release surfaces (STEP-06)
        _maybe_crash("suspend:before_token_cleanup")
        self._clear_local_token()
        control = self.store.load()
        return {"activity": _activity_obj(control["activity"]),
                "checkpoint": checkpoint}

    def _conclude_locked(self, status: str) -> dict:
        control = self._recover()
        activity = control["activity"]
        if activity is None:
            raise NoActivity({"state": "idle"})
        if activity["state"] != "ACTIVE":
            raise NotActive({"state": activity["state"]})
        token = activity["turn"]["token"]

        def fn(body: dict) -> dict:
            act = body["activity"]
            body["last_concluded"] = {"type": act["type"], "id": act["id"],
                                      "status": status, "epoch": act["epoch"],
                                      "at": utcnow()}
            body["activity"] = None
            return body

        control = self.store.mutate(fn, turn_token=token)
        _maybe_crash("conclude:after_cas")
        self.lock.release(token)  # strict: a failed release surfaces (STEP-06)
        _maybe_crash("conclude:before_token_cleanup")
        self._clear_local_token()
        return {"last_concluded": control["last_concluded"]}

    def _heartbeat_locked(self) -> dict:
        self._recover()
        token = self._read_local_token()
        if token is None:
            raise NoActivity({"state": "no local turn token"})
        self.lock.heartbeat(token)
        return {"heartbeat_at": utcnow()}

    def _takeover_locked(self, *, reason: str, actor: str = "mediator") -> dict:
        control = self.store.load()
        activity = control.get("activity")
        if activity is None:
            raise NoActivity({"state": "idle"})
        if activity["state"] != "ACTIVE":
            raise NotActive({"state": activity["state"]})
        previous = (activity.get("turn") or {}).get("token")
        token = self.lock.takeover(actor=actor, reason=reason,
                                   control_store=self.store)
        self._write_local_token(token)
        return {"token": token, "previous_owner": previous}

    def _stop_request_locked(self, reason: str | None = None) -> dict:
        control = self._recover()
        activity = control["activity"]
        if activity is None:
            raise NoActivity({"state": "idle"})
        if activity["state"] == "SUSPENDED":  # normalized no-op (PLAN-002)
            return {"request": None, "noop": True}
        return {"request": record_stop_request(self.store, turn_token=None,
                                               reason=reason),
                "noop": False}

    def _stop_check_locked(self) -> dict:
        request = read_valid_stop_request(self.store)
        return {"stop_requested": request is not None, "request": request}

    def _status_locked(self) -> dict:
        activity = None
        try:
            control = self.store.load()
            activity = control["activity"]
            control_view: Any = {"version": control["version"],
                                 "activity": _activity_obj(activity),
                                 "stop_request": control["stop_request"],
                                 "last_concluded": control["last_concluded"]}
        except ControlSchemaError as exc:
            control_view = ("uninitialized"
                            if "does not exist" in str(exc) else "corrupt")
        lock_status = self.lock.status()
        workspace = ({"open_artifacts": [], "verdict": "CORRUPT_CONTROL"}
                     if control_view == "corrupt"
                     else self.workspace_report(activity))
        return {"control": control_view,
                "lock": {"state": lock_status["state"],
                         "age_seconds": lock_status["age_seconds"]},
                "local_token_present": self._read_local_token() is not None,
                "workspace": workspace}

    # -- control×files matrix (normative, PLAN-002 — executable) ------------

    def workspace_report(self, activity: dict | None) -> dict:
        open_artifacts = self._scan_open_artifacts()
        return {"open_artifacts": open_artifacts,
                "verdict": classify_workspace(activity, open_artifacts,
                                              self.root)}

    def _scan_open_artifacts(self) -> list[str]:
        """Open content dirs by the v0 rules: EN scheme + legacy PT scheme."""
        found = []
        rounds = self.root / ".regent" / "brainstorm" / "rounds"
        for entry in sorted(rounds.glob("ROUND-*")):
            if entry.is_dir() and not (entry / "DECISION.md").exists():
                found.append(entry.name)
        legacy = self.root / ".regent" / "brainstorm" / "rodadas"
        for entry in sorted(legacy.glob("RODADA-*")):
            if entry.is_dir() and not (entry / "DECISAO.md").exists():
                found.append(entry.name)
        plans = self.root / ".regent" / "plans"
        for entry in sorted(plans.glob("PLAN-*")):
            if not entry.is_dir():
                continue
            if not (entry / "APPROVAL.md").exists():
                found.append(entry.name)
            elif (entry / "build").is_dir() \
                    and not (entry / "build" / "CONCLUSION.md").exists():
                found.append(entry.name)
        return found

    # -- recovery (normative 12-row table) ---------------------------------

    def _recover(self) -> dict:
        """Repairs repairable rows, raises on mediator-decision rows, and
        returns the (possibly repaired) current control."""
        control = self.store.load()
        activity = control["activity"]
        lock_status = self.lock.status()
        lock_state = lock_status["state"]
        lock_token = (lock_status["owner"] or {}).get("token")
        local = self._read_local_token()

        if activity is not None and activity["state"] == "ACTIVE":
            control_token = activity["turn"]["token"]
            if lock_state == "held" and lock_token == control_token:
                if local != control_token:  # rows 2 and 12
                    self._write_local_token(control_token)
            elif lock_state == "free":  # row 3
                raise LockSuspectError(
                    {"lock": {"state": "free", "age_seconds": None}},
                    "control is ACTIVE but no lock exists — run "
                    "`regent activity takeover --reason ...` (mediated)")
            elif lock_state == "suspect":  # row 4
                raise LockSuspectError(
                    {"lock": {"state": "suspect",
                              "age_seconds": lock_status["age_seconds"]}},
                    "turn lock is suspect — run takeover (mediated)")
            else:  # row 5: held by a DIFFERENT token
                raise TokenMismatch({"control_token": control_token,
                                     "held_token": lock_token})
        else:  # SUSPENDED or idle
            if lock_state in ("held", "suspect") and lock_token:  # rows 6 and 8
                self._release_quietly(lock_token)
            if self._read_local_token() is not None:  # rows 10 and 11
                self._clear_local_token()
        return self.store.load()

    # -- internals ---------------------------------------------------------

    def _floor(self, control: dict) -> int:
        values = [-1]
        if control.get("activity") is not None:
            values.append(control["activity"]["epoch"])
        if control.get("last_concluded") is not None:
            values.append(control["last_concluded"]["epoch"])
        return max(values)

    def _release_quietly(self, token: str) -> None:
        """Recovery-path release: a vanished/foreign lock (NotLockOwner,
        StaleLock) is already the desired outcome and is audited; a REAL
        removal failure (OSError) PROPAGATES — it is never success."""
        from .protocol import StaleLock
        try:
            self.lock.release(token)
        except (NotLockOwner, StaleLock) as exc:
            self.audit.append({"event": "release_during_recovery_skipped",
                               "token": token, "reason": repr(exc)})

    def _read_local_token(self) -> str | None:
        try:
            return json.loads(self.token_file.read_text(encoding="utf-8"))["token"]
        except (OSError, ValueError, KeyError):
            return None

    def _write_local_token(self, token: str) -> None:
        tmp = self.token_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"token": token, "at": utcnow()}),
                       encoding="utf-8")
        os.replace(tmp, self.token_file)

    def _clear_local_token(self) -> None:
        try:
            self.token_file.unlink()
        except FileNotFoundError:
            pass  # already clean; any OTHER failure propagates


WORKSPACE_VERDICTS = (
    "OK", "SUSPENDED_OK", "IDLE_CLEAN",  # proceedable
    "ORPHAN_NO_DIR", "ORPHAN_WITH_OTHER_OPEN", "SUSPENDED_ORPHAN",
    "TYPE_MISMATCH", "SECOND_ARTIFACT", "TERMINAL_EXISTS", "MULTIPLE_OPEN",
    "LEGACY_OPEN_ARTIFACT", "MULTIPLE_SCHEMES", "CORRUPT_CONTROL",
)


ALLOWED_STEP_AUDIT_EVENTS = frozenset({"stop_request_discarded"})


def explain_control_diff(before: dict, after: dict,
                         audit_delta: list[dict] | None = None,
                         since_version: int | None = None) -> dict:
    """Attributability check for the exempted operational files (PLAN-002
    commit choreography), DEFAULT-DENY with VERSION ACCOUNTING: nothing is
    explained by default. The only legitimate in-step mutations are the
    ARRIVAL of a well-formed stop_request bound to the CURRENT activity and
    an audited stale-request discard; the version delta must equal the count
    of those explained mutations (a bare version jump is unexplained).
    `since_version` is the skill's step-start snapshot: the HEAD version must
    not exceed it, and it must not exceed the worktree version."""
    explained, unexplained = [], []
    if before.get("schema_version") != after.get("schema_version"):
        unexplained.append("schema_version")
    for key in ("activity", "last_concluded"):
        if before.get(key) != after.get(key):
            unexplained.append(key)

    accountable = 0
    b_req, a_req = before.get("stop_request"), after.get("stop_request")
    if b_req != a_req:
        activity = after.get("activity") or before.get("activity")
        arrival_ok = (b_req is None and isinstance(a_req, dict)
                      and activity is not None
                      and a_req.get("activity_id") == activity.get("id")
                      and a_req.get("activity_epoch") == activity.get("epoch")
                      and set(a_req) == {"id", "activity_id", "activity_epoch",
                                         "turn_token", "reason", "requested_at"})
        if arrival_ok:
            explained.append("stop_request")
            accountable += 1
        else:
            unexplained.append("stop_request")
    for event in (audit_delta or []):
        name = event.get("event")
        if name in ALLOWED_STEP_AUDIT_EVENTS and event.get("request_id"):
            accountable += 1  # an audited discard also bumps the version
        else:
            unexplained.append(f"audit:{name}")

    b_ver, a_ver = before.get("version"), after.get("version")
    if b_ver != a_ver:
        delta = (a_ver - b_ver) if isinstance(a_ver, int)             and isinstance(b_ver, int) else None
        if delta is not None and 0 < delta <= accountable:
            explained.append("version")
            if before.get("updated_at") != after.get("updated_at"):
                explained.append("updated_at")
        else:
            unexplained.append("version")  # bare/unaccounted version churn
    elif before.get("updated_at") != after.get("updated_at"):
        unexplained.append("updated_at")

    if since_version is not None:
        if not (isinstance(b_ver, int) and isinstance(a_ver, int)
                and b_ver <= since_version <= a_ver):
            unexplained.append("since_version")
    return {"explained": explained, "unexplained": unexplained}


def classify_workspace(activity: dict | None, open_artifacts: list[str],
                       root: Path) -> str:
    """The PLAN-002 control×files matrix, row by row (default-deny)."""
    en_scheme = root / ".regent" / "brainstorm" / "rounds"
    pt_scheme = root / ".regent" / "brainstorm" / "rodadas"
    if any(en_scheme.glob("ROUND-*")) and any(pt_scheme.glob("RODADA-*")):
        return "MULTIPLE_SCHEMES"  # REQ-005 §8: coexistence is corruption
    if activity is None:
        if not open_artifacts:
            return "IDLE_CLEAN"
        if len(open_artifacts) > 1:
            return "MULTIPLE_OPEN"
        return "LEGACY_OPEN_ARTIFACT"  # ask the mediator; never adopt silently

    aid, atype, state = activity["id"], activity["type"], activity["state"]
    others = [a for a in open_artifacts if a != aid]
    own_dir = _artifact_dir(root, aid)
    type_ok = (atype == "brainstorm") == aid.startswith("ROUND-") \
        if aid.startswith(("ROUND-", "PLAN-")) else False

    if own_dir is None or not own_dir.exists():
        if others:
            return "ORPHAN_WITH_OTHER_OPEN"
        return "SUSPENDED_ORPHAN" if state == "SUSPENDED" else "ORPHAN_NO_DIR"
    if not type_ok:
        return "TYPE_MISMATCH"
    if others:
        return "SECOND_ARTIFACT" if len(others) == 1 else "MULTIPLE_OPEN"
    if state == "SUSPENDED":
        return "SUSPENDED_OK"
    if _terminal_exists(own_dir, atype):
        return "TERMINAL_EXISTS"
    return "OK"


def _artifact_dir(root: Path, activity_id: str) -> Path | None:
    if activity_id.startswith("ROUND-"):
        return root / ".regent" / "brainstorm" / "rounds" / activity_id
    if activity_id.startswith("PLAN-"):
        return root / ".regent" / "plans" / activity_id
    return None


def _terminal_exists(artifact_dir: Path, activity_type: str) -> bool:
    if activity_type == "brainstorm":
        return (artifact_dir / "DECISION.md").exists()
    if activity_type == "plan":
        return (artifact_dir / "APPROVAL.md").exists()
    return (artifact_dir / "build" / "CONCLUSION.md").exists()


def _activity_obj(activity: dict | None) -> dict | None:
    if activity is None:
        return None
    obj = {"type": activity["type"], "id": activity["id"],
           "epoch": activity["epoch"], "state": activity["state"]}
    suspension = activity.get("suspension")
    if suspension is not None:  # declared ActivityObj extension (STEP-06)
        obj["checkpoint"] = suspension["checkpoint"]
        obj["reason"] = suspension["reason"]
    return obj


def _set_active(body: dict, activity_type: str, activity_id: str,
                epoch: int, token: str) -> dict:
    if body.get("activity") is not None:
        return body  # raced: caller re-inspects
    body["activity"] = {"type": activity_type, "id": activity_id, "epoch": epoch,
                        "state": "ACTIVE", "suspension": None,
                        "turn": {"owner": "executor", "token": token,
                                 "acquired_at": utcnow()}}
    return body
