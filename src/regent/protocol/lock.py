"""Executor turn lock: mkdir-primitive mutex with token ownership.

Origin: reimplements the INVARIANT of the ArtNFT turn lock
(docs/brainstorm-mvp/scripts/turn_lock.py / control_adapters.py — the proven
mkdir() mutex primitive), not the algorithm verbatim: the actor model changed
(REQ-003 — the executor is the ONLY turn holder; no dual agent identity).

Contracts:
- The lock lives in the DISPOSABLE local state dir (XDG side, REQ-001 §3);
  a successful acquire touches nothing else (P-01: `.regent/` and git stay
  byte-identical).
- Ownership is a uuid4 token written to owner.json inside the lock dir;
  release/heartbeat require the current token (else NotLockOwner).
- Takeover is only allowed on a SUSPECT lock (heartbeat older than
  stale_after, or ownerless beyond a grace covering the mkdir→owner.json
  window). It is always explicit and audited (actor, reason, previous owner,
  age, timestamps) to the SHAREABLE audit log under .regent/ (REQ-001 §3).
- Takeover race: the stale dir is atomically renamed aside first — exactly
  one candidate wins the rename; the loser gets LockHeld.
- ABA fencing end-to-end: the winning token is what callers must mirror into
  control.activity.turn.token; control operations guarded by turn_token then
  reject the previous holder (control.assert_turn_token).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .audit import AuditLog, utcnow


class LockHeld(RuntimeError):
    """The lock is held (acquire) or not suspect / lost race (takeover)."""


class NotLockOwner(RuntimeError):
    """Operation attempted with a token that does not own the lock."""


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
        try:
            os.mkdir(self._dir)  # parent (state dir) must exist; XDG-only footprint
        except FileExistsError:
            raise LockHeld(f"turn lock held: {self._dir}") from None
        token = uuid.uuid4().hex
        self._write_owner(token, acquired_at=utcnow())
        return token

    def heartbeat(self, token: str) -> None:
        owner = self._owner_or_raise(token)
        self._write_owner(token, acquired_at=owner["acquired_at"])

    def release(self, token: str) -> None:
        self._owner_or_raise(token)
        try:
            (self._dir / "owner.json").unlink()
        except OSError:
            pass
        os.rmdir(self._dir)

    # -- inspection -------------------------------------------------------

    def status(self) -> dict:
        """{'state': 'free'|'held'|'suspect', 'age_seconds': float|None, ...}"""
        if not self._dir.exists():
            return {"state": "free", "age_seconds": None, "owner": None}
        owner = self._read_owner()
        now = datetime.now(timezone.utc)
        if owner is None:
            age = now.timestamp() - self._dir.stat().st_mtime
            state = "suspect" if age > self._ownerless_grace else "held"
            return {"state": state, "age_seconds": age, "owner": None}
        beat = datetime.fromisoformat(owner["heartbeat_at"])
        age = (now - beat).total_seconds()
        state = "suspect" if age > self._stale_after else "held"
        return {"state": state, "age_seconds": age, "owner": owner}

    # -- takeover ---------------------------------------------------------

    def takeover(self, *, actor: str, reason: str) -> str:
        status = self.status()
        if status["state"] == "free":
            return self.acquire()
        if status["state"] != "suspect":
            raise LockHeld("takeover refused: lock is not suspect")
        judged_token = (status["owner"] or {}).get("token")
        aside = self._dir.with_name(f"turn.lock.stale-{uuid.uuid4().hex}")
        try:
            os.rename(self._dir, aside)  # atomic: exactly one candidate renames it
        except FileNotFoundError:
            raise LockHeld("takeover lost: another candidate acted first") from None
        # ABA guard: only the exact instance judged suspect may be evicted. If the
        # renamed dir is a DIFFERENT (fresh) lock, restore it and lose the race.
        aside_owner = self._read_owner_at(aside)
        if (aside_owner or {}).get("token") != judged_token:
            try:
                os.rename(aside, self._dir)
            except OSError:
                self._audit.append({"event": "turn_lock_takeover_restore_failed",
                                    "actor": actor, "aside": str(aside)})
            raise LockHeld("takeover lost: lock changed hands while judging it")
        token = self.acquire()
        self._audit.append({
            "event": "turn_lock_takeover", "actor": actor, "reason": reason,
            "previous_owner": (status["owner"] or {}).get("token"),
            "age_seconds": round(status["age_seconds"] or 0, 3),
            "new_token": token,
        })
        _remove_tree(aside)
        return token

    # -- internals --------------------------------------------------------

    def _write_owner(self, token: str, *, acquired_at: str) -> None:
        payload = {"owner": "executor", "token": token,
                   "acquired_at": acquired_at, "heartbeat_at": utcnow()}
        (self._dir / "owner.json").write_text(json.dumps(payload), encoding="utf-8")

    def _read_owner(self) -> dict | None:
        return self._read_owner_at(self._dir)

    @staticmethod
    def _read_owner_at(lock_dir: Path) -> dict | None:
        try:
            return json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _owner_or_raise(self, token: str) -> dict:
        if not self._dir.exists():
            raise StaleLock("turn lock no longer exists (released or taken over)")
        owner = self._read_owner()
        if owner is None or owner.get("token") != token:
            raise NotLockOwner("token does not own the turn lock")
        return owner


def _remove_tree(path: Path) -> None:
    try:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()
    except OSError:
        pass
