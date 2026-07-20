"""Executor turn lock: mkdir-primitive mutex with token ownership.

Origin: reimplements the INVARIANT of the ArtNFT turn lock
(docs/brainstorm-mvp/scripts/turn_lock.py / control_adapters.py — the proven
mkdir() mutex primitive), not the algorithm verbatim: the actor model changed
(REQ-003 — the executor is the ONLY turn holder; no dual agent identity).

Contracts:
- The lock lives in the DISPOSABLE local state dir (XDG side, REQ-001 §3);
  a successful acquire touches nothing else (P-01: `.regent/` and git stay
  byte-identical).
- Ownership is a uuid4 token in owner.json inside the lock dir.
- heartbeat is INSTANCE-BOUND: it opens the lock directory once and performs
  read-verify-write through that directory fd — if a takeover renames the
  instance concurrently, the write lands in the renamed (discarded) dir and
  can never usurp the new holder's lock.
- release claims the instance by atomic rename, verifies the token INSIDE the
  claimed instance, and only then deletes it; a mismatch restores the instance
  (audited if restoration fails). The old holder can never destroy a lock it
  no longer owns.
- Takeover is only allowed on a SUSPECT lock (heartbeat older than
  stale_after, or ownerless beyond a grace covering the mkdir→owner.json
  window). The takeover INTENT is audited before acting; the judged instance
  is claimed by atomic rename and verified by token (ABA guard) — exactly one
  candidate wins, and a fresh lock can never be evicted.
- ABA fencing end-to-end: `takeover(..., control_store=...)` rotates the token
  recorded in control.activity.turn.token in the same operation, so control
  operations guarded by the previous token fail immediately after takeover.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .audit import AuditLog, utcnow
from .control import NotLockOwner

if TYPE_CHECKING:  # pragma: no cover
    from .control import ControlStore


class LockHeld(RuntimeError):
    """The lock is held (acquire) or not suspect / lost race (takeover)."""


class StaleLock(RuntimeError):
    """The lock this token owned no longer exists (taken over or released)."""


class TurnLock:
    def __init__(self, state_dir: Path, audit: AuditLog, *,
                 stale_after: float = 1800.0, ownerless_grace: float = 30.0) -> None:
        self._dir = Path(state_dir) / "turn.lock.d"
        self._audit = audit
        self._stale_after = stale_after
        self._ownerless_grace = ownerless_grace

    @property
    def path(self) -> Path:
        return self._dir

    # -- acquisition ------------------------------------------------------

    def acquire(self) -> str:
        return self._acquire_with_token(uuid.uuid4().hex)

    def _acquire_with_token(self, token: str) -> str:
        try:
            os.mkdir(self._dir)  # parent (state dir) must exist; XDG-only footprint
        except FileExistsError:
            raise LockHeld(f"turn lock held: {self._dir}") from None
        payload = {"owner": "executor", "token": token,
                   "acquired_at": utcnow(), "heartbeat_at": utcnow()}
        (self._dir / "owner.json").write_text(json.dumps(payload), encoding="utf-8")
        return token

    def heartbeat(self, token: str) -> None:
        """Instance-bound: read-verify-write through the directory fd, immune to
        a concurrent takeover renaming the canonical path."""
        try:
            dir_fd = os.open(self._dir, os.O_RDONLY)
        except FileNotFoundError:
            raise StaleLock("turn lock no longer exists (released or taken over)") from None
        try:
            owner = self._read_owner_fd(dir_fd)
            if owner is None or owner.get("token") != token:
                raise NotLockOwner("token does not own the turn lock")
            owner["heartbeat_at"] = utcnow()
            tmp_fd = os.open("owner.json.tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                             0o644, dir_fd=dir_fd)
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                json.dump(owner, handle)
            os.replace("owner.json.tmp", "owner.json",
                       src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        finally:
            os.close(dir_fd)

    def release(self, token: str) -> None:
        """Verify-then-claim: ownership is checked BEFORE any rename (a stale
        holder never displaces the current lock, not even transiently), then
        the instance is claimed by atomic rename and re-verified inside the
        claimed dir before being destroyed."""
        current = self._read_owner_at(self._dir)
        if current is None:
            if not self._dir.exists():
                raise StaleLock("turn lock no longer exists (released or taken over)")
            raise NotLockOwner("token does not own the turn lock")
        if current.get("token") != token:
            raise NotLockOwner("token does not own the turn lock")
        aside = self._dir.with_name(f"turn.lock.releasing-{uuid.uuid4().hex}")
        try:
            os.rename(self._dir, aside)
        except FileNotFoundError:
            raise StaleLock("turn lock no longer exists (released or taken over)") from None
        owner = self._read_owner_at(aside)
        if owner is None or owner.get("token") != token:
            try:
                os.rename(aside, self._dir)
            except OSError:
                self._audit.append({"event": "turn_lock_release_restore_failed",
                                    "aside": str(aside)})
            raise NotLockOwner("token does not own the turn lock")
        _remove_tree(aside)

    # -- inspection -------------------------------------------------------

    def status(self) -> dict:
        """{'state': 'free'|'held'|'suspect', 'age_seconds': float|None, ...}"""
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

    # -- takeover ---------------------------------------------------------

    def takeover(self, *, actor: str, reason: str,
                 control_store: "ControlStore | None" = None) -> str:
        status = self.status()
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
            aside = self._dir.with_name(f"turn.lock.stale-{uuid.uuid4().hex}")
            try:
                os.rename(self._dir, aside)  # atomic: one candidate renames it
            except FileNotFoundError:
                raise LockHeld("takeover lost: another candidate acted first") from None
            # ABA guard: only the exact instance judged suspect may be evicted.
            # A DIFFERENT (fresh) lock is restored, and the race is lost.
            aside_owner = self._read_owner_at(aside)
            if (aside_owner or {}).get("token") != judged_token:
                try:
                    os.rename(aside, self._dir)
                except OSError:
                    self._audit.append({"event": "turn_lock_takeover_restore_failed",
                                        "actor": actor, "aside": str(aside)})
                raise LockHeld("takeover lost: lock changed hands while judging it")
            _remove_tree(aside)
        # FENCE BEFORE HANDOVER: rotate the control token while the canonical
        # path is empty. A crash here leaves the control fenced to a token whose
        # lock does not exist yet — safe (no usurpation; the next takeover sees
        # state=free and re-fences). Only then is the new lock instance created.
        if control_store is not None:
            self._rotate_control_token(control_store, judged_token, new_token,
                                       actor=actor)
        try:
            return self._acquire_with_token(new_token)
        except LockHeld:
            # Another candidate acquired the transiently-free path first. The
            # control (if given) is fenced to OUR token, so the winner cannot
            # proceed silently: surface the loss.
            raise LockHeld("takeover lost: path acquired by another candidate") from None

    def _rotate_control_token(self, store: "ControlStore", previous: str | None,
                              token: str, *, actor: str) -> None:
        """End-to-end fencing: replace the turn token recorded in an ACTIVE
        control activity so the previous holder is rejected immediately. A
        mismatch (token in control is neither `previous` nor absent) is audited,
        never silently skipped."""
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
            self._audit.append({"event": "turn_token_rotation_skipped",
                                "actor": actor, "expected_previous": previous,
                                "found": skipped["found"], "new_token": token})

    # -- internals --------------------------------------------------------

    @staticmethod
    def _read_owner_fd(dir_fd: int) -> dict | None:
        try:
            fd = os.open("owner.json", os.O_RDONLY, dir_fd=dir_fd)
        except OSError:
            return None
        try:
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

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
