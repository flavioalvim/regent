"""regent.protocol — transactional foundation (PLAN-001).

Reimplements the invariants proven in the ArtNFT protocol layer
(docs/brainstorm-mvp/scripts/: turn_lock.py, control_domain.py,
control_adapters.py) under the regent v1 actor model (REQ-003: the executor is
the only turn holder; the advisor never holds a turn).

Public API (nominal, PLAN-001 STEP-04; STEP-05 unified NotLockOwner into a
single class raised by both control fencing and lock ownership checks):
- control: ControlStore, ControlSchemaError, VersionConflict, NotLockOwner,
  MutationMutexBusy (declared deviation: added to the approved nominal list —
  callers need to catch a busy/lost mutation mutex)
- lock:    TurnLock, LockHeld, StaleLock
- stop:    record_stop_request, read_valid_stop_request, suspend_activity
- audit:   AuditLog
"""

from .audit import AuditLog
from .control import (ControlSchemaError, ControlStore, MutationMutexBusy,
                      NotLockOwner, VersionConflict)
from .lock import LockHeld, StaleLock, TurnLock
from .stop import read_valid_stop_request, record_stop_request, suspend_activity

__all__ = [
    "AuditLog",
    "ControlSchemaError",
    "ControlStore",
    "LockHeld",
    "MutationMutexBusy",
    "NotLockOwner",
    "StaleLock",
    "TurnLock",
    "VersionConflict",
    "read_valid_stop_request",
    "record_stop_request",
    "suspend_activity",
]
