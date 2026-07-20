"""Executor turn lock: serialized lifecycle with token ownership.

Origin: reimplements the INVARIANT of the ArtNFT turn lock
(docs/brainstorm-mvp/scripts/turn_lock.py / control_adapters.py — the proven
directory-mutex primitive), not the algorithm verbatim: the actor model
changed (REQ-003 — the executor is the ONLY turn holder; no dual identity).

Structure (closes the race-window family found in the build reviews): ALL
lifecycle operations — acquire, heartbeat, release, takeover — run under a
dedicated LIFECYCLE MUTEX (the same hardened primitive as the control
mutation mutex: instance tokens, dead-pid-only eviction, audited recovery).
Serialization makes each operation's read-judge-act sequence atomic with
respect to the others: no verify-then-rename TOCTOU, no transiently-free
path for a third acquirer, no double fence rotation.

The lock instance itself is created by an atomic rename of a PRE-POPULATED
staging dir (owner.json written before the instance becomes visible), so an
ownerless lock can only be a legacy crash artifact.

Lock-ordering discipline (documented, deadlock-free): lifecycle mutex →
control mutation mutex (takeover rotates control while holding the lifecycle
mutex). Nothing acquires them in the opposite order.

Contracts:
- The lock lives in the DISPOSABLE local state dir (XDG side, REQ-001 §3);
  a successful acquire touches nothing else (P-01: `.regent/` and git stay
  byte-identical) — audits happen only on takeover/eviction anomalies.
- heartbeat/release require the current token (NotLockOwner otherwise);
  a vanished lock raises StaleLock.
- Takeover is only allowed on a SUSPECT lock (heartbeat older than
  stale_after, or ownerless). The INTENT is audited before acting. With a
  control_store, the control turn token is rotated BEFORE the new lock
  instance exists (fence-before-handover); a divergent rotation ABORTS the
  takeover (audited) — physical owner and fenced token can never separate.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .audit import AuditLog, utcnow
from .control import NotLockOwner, _MutationMutex

if TYPE_CHECKING:  # pragma: no cover
    from .control import ControlStore


class LockHeld(RuntimeError):
    """The lock is held (acquire), not suspect, or the takeover was lost."""


class StaleLock(RuntimeError):
    """The lock this token owned no longer exists (taken over or released)."""


class TurnLock:
    def __init__(self, state_dir: Path, audit: AuditLog, *,
                 stale_after: float = 1800.0, ownerless_grace: float = 30.0,
                 lifecycle_timeout: float = 30.0) -> None:
        self._dir = Path(state_dir) / "turn.lock.d"
        self._audit = audit
        self._stale_after = stale_after
        self._ownerless_grace = ownerless_grace
        self._lifecycle_timeout = lifecycle_timeout

    @property
    def path(self) -> Path:
        return self._dir

    def _lifecycle_mutex(self) -> _MutationMutex:
        mutex_dir = self._dir.with_name("turn.lifecycle.lock.d")
        return _MutationMutex(mutex_dir, self._audit, self._lifecycle_timeout)

    # -- lifecycle operations (each fully serialized) ----------------------

    def acquire(self) -> str:
        with self._lifecycle_mutex():
            return self._acquire_locked(uuid.uuid4().hex)

    def heartbeat(self, token: str) -> None:
        with self._lifecycle_mutex():
            owner = self._owner_or_raise_locked(token)
            owner["heartbeat_at"] = utcnow()
            self._write_owner_locked(owner)

    def release(self, token: str) -> None:
        with self._lifecycle_mutex():
            self._owner_or_raise_locked(token)
            _remove_tree(self._dir)

    def takeover(self, *, actor: str, reason: str,
                 control_store: "ControlStore | None" = None) -> str:
        with self._lifecycle_mutex():
            status = self._status_locked()
            if status["state"] == "held":
                raise LockHeld("takeover refused: lock is not suspect")
            judged_token = (status["owner"] or {}).get("token")
            new_token = uuid.uuid4().hex
            # Audit the INTENT first: any crash past this point leaves a record.
            self._audit.append({
                "event": "turn_lock_takeover", "actor": actor, "reason": reason,
                "state_judged": status["state"], "previous_owner": judged_token,
                "age_seconds": round(status["age_seconds"] or 0, 3),
                "new_token": new_token,
            })
            if status["state"] == "suspect":
                _remove_tree(self._dir)  # serialized: the judged instance, no other
            # FENCE BEFORE HANDOVER: rotate the control token while no lock
            # instance exists. A crash here leaves the control fenced to a token
            # whose lock does not exist — safe (no usurpation; a later takeover
            # sees free and re-fences). Divergence ABORTS: physical owner and
            # fenced token never separate.
            if control_store is not None:
                self._rotate_control_token_locked(control_store, judged_token,
                                                  new_token, actor=actor)
            return self._acquire_locked(new_token)

    def status(self) -> dict:
        with self._lifecycle_mutex():
            return self._status_locked()

    # -- serialized internals ---------------------------------------------

    def _acquire_locked(self, token: str) -> str:
        # Atomic publication of a PRE-POPULATED instance: staging dir with
        # owner.json, then one rename. No mkdir→owner window exists.
        staging = self._dir.with_name(f"turn.lock.staging-{token}")
        os.mkdir(staging)
        payload = {"owner": "executor", "token": token,
                   "acquired_at": utcnow(), "heartbeat_at": utcnow()}
        (staging / "owner.json").write_text(json.dumps(payload), encoding="utf-8")
        try:
            os.rename(staging, self._dir)
        except OSError:
            _remove_tree(staging)
            raise LockHeld(f"turn lock held: {self._dir}") from None
        return token

    def _status_locked(self) -> dict:
        if not self._dir.exists():
            return {"state": "free", "age_seconds": None, "owner": None}
        owner = self._read_owner_at(self._dir)
        now = datetime.now(timezone.utc)
        if owner is None:
            try:
                age = now.timestamp() - self._dir.stat().st_mtime
            except OSError:
                return {"state": "free", "age_seconds": None, "owner": None}
            state = "suspect" if age > self._ownerless_grace else "held"
            return {"state": state, "age_seconds": age, "owner": None}
        beat = datetime.fromisoformat(owner["heartbeat_at"])
        age = (now - beat).total_seconds()
        state = "suspect" if age > self._stale_after else "held"
        return {"state": state, "age_seconds": age, "owner": owner}

    def _owner_or_raise_locked(self, token: str) -> dict:
        if not self._dir.exists():
            raise StaleLock("turn lock no longer exists (released or taken over)")
        owner = self._read_owner_at(self._dir)
        if owner is None or owner.get("token") != token:
            raise NotLockOwner("token does not own the turn lock")
        return owner

    def _write_owner_locked(self, owner: dict) -> None:
        tmp = self._dir / "owner.json.tmp"
        tmp.write_text(json.dumps(owner), encoding="utf-8")
        os.replace(tmp, self._dir / "owner.json")

    def _rotate_control_token_locked(self, store: "ControlStore",
                                     previous: str | None, token: str, *,
                                     actor: str) -> None:
        skipped: dict = {}

        def fn(body: dict) -> dict:
            activity = body.get("activity")
            turn = (activity or {}).get("turn")
            if turn is None:
                return body
            if previous is not None and turn.get("token") != previous:
                skipped["found"] = turn.get("token")
                return body
            turn["token"] = token
            turn["acquired_at"] = utcnow()
            return body

        store.mutate(fn)
        if skipped:
            self._audit.append({"event": "turn_token_rotation_aborted_takeover",
                                "actor": actor, "expected_previous": previous,
                                "found": skipped["found"], "new_token": token})
            raise LockHeld("takeover aborted: control fencing diverged "
                           f"(expected {previous}, found {skipped['found']})")

    @staticmethod
    def _read_owner_at(lock_dir: Path) -> dict | None:
        try:
            return json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


def _remove_tree(path: Path) -> None:
    try:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()
    except OSError:
        pass
