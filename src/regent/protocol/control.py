"""Transactional control store: control.json with real compare-and-swap.

Origin: reimplements the proven invariants of the ArtNFT protocol layer
(docs/brainstorm-mvp/scripts/control_adapters.py: atomic tempfile+replace
publication; control_domain.py: monotonic CAS versioning and strict schema
default-deny) under the regent v1 actor model (REQ-003: single executor).

Concurrency: read-check-replace alone is NOT a CAS (two writers could both
validate the same version — lost update). Every mutation therefore runs inside
a short exclusive critical section backed by a kernel **flock** on a dedicated
lock FILE (v0 is single-host by REQ-003, where flock is strictly stronger than
any directory-mutex scheme: acquisition is atomic in the kernel, a dead
holder's lock is released AUTOMATICALLY, and there is no stale-judgment,
eviction or recovery code to race on). The lock file is created once and never
unlinked (unlinking would allow two locks on different inodes). The flock is
never held while acquiring the turn lock — lock-ordering is lifecycle →
mutation, nowhere reversed.

Publication separates atomicity from durability: tempfile in the same
directory → flush+fsync(file) → os.replace → fsync(directory).
"""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .audit import AuditLog, utcnow

SCHEMA_VERSION = 1
ACTIVITY_TYPES = ("brainstorm", "plan", "build")
ACTIVITY_STATES = ("ACTIVE", "SUSPENDED")
_TMP_PREFIX = ".control-tmp-"

_TOP_KEYS = {"schema_version", "version", "updated_at", "activity", "stop_request",
             "last_concluded"}
_ACTIVITY_KEYS = {"type", "id", "epoch", "state", "turn", "suspension"}
_TURN_KEYS = {"owner", "token", "acquired_at"}
_SUSPENSION_KEYS = {"previous_state", "checkpoint", "owning_turn", "in_flight",
                    "reason", "evidence", "at"}
_REQUEST_KEYS = {"id", "activity_id", "activity_epoch", "turn_token",
                 "reason", "requested_at"}
_CONCLUDED_KEYS = {"type", "id", "status", "epoch", "at"}


class ControlSchemaError(ValueError):
    """Control file is corrupt, has an unknown schema or violates invariants."""


class VersionConflict(RuntimeError):
    """The control version diverged from the expected one (CAS failure)."""


class MutationMutexBusy(RuntimeError):
    """Could not enter (or keep) the mutation critical section."""


class NotLockOwner(RuntimeError):
    """A turn-token-guarded operation ran with a divergent token (ABA fencing)."""


def initial_control() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "version": 0,
        "updated_at": utcnow(),
        "activity": None,
        "stop_request": None,
        "last_concluded": None,
    }


def _require_keys(obj: Mapping[str, Any], keys: set, label: str) -> None:
    if not isinstance(obj, Mapping):
        raise ControlSchemaError(f"{label} must be an object")
    actual = set(obj.keys())
    if actual != keys:
        missing, extra = sorted(keys - actual), sorted(actual - keys)
        raise ControlSchemaError(f"{label}: missing keys {missing}, unknown keys {extra}")


def _require_str(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise ControlSchemaError(f"{label} must be a non-empty string")


def _require_int(value: Any, label: str, *, minimum: int = 0) -> None:
    # bool is an int subclass in Python; the schema means actual integers.
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ControlSchemaError(f"{label} must be an int >= {minimum}")


def _require_token(value: Any, label: str) -> None:
    _require_str(value, label)
    if len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
        raise ControlSchemaError(f"{label} must be a uuid4 hex token (32 hex chars)")


def _require_timestamp(value: Any, label: str) -> None:
    _require_str(value, label)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ControlSchemaError(f"{label} is not an ISO-8601 timestamp: {value!r}") from None
    if parsed.tzinfo is None:
        raise ControlSchemaError(f"{label} must be timezone-aware (UTC): {value!r}")


def validate_control(control: Mapping[str, Any]) -> None:
    """Strict default-deny validation: exact key sets, types, timestamps and the
    ACTIVE/SUSPENDED invariants. Unknown or missing fields are rejected."""
    _require_keys(control, _TOP_KEYS, "control")
    _require_int(control["schema_version"], "schema_version")  # rejects bool too
    if control["schema_version"] != SCHEMA_VERSION:
        raise ControlSchemaError(f"unknown schema_version: {control['schema_version']!r}")
    _require_int(control["version"], "version")
    _require_timestamp(control["updated_at"], "updated_at")

    activity = control["activity"]
    if activity is not None:
        _require_keys(activity, _ACTIVITY_KEYS, "activity")
        if activity["type"] not in ACTIVITY_TYPES:
            raise ControlSchemaError(f"unknown activity type: {activity['type']!r}")
        _require_str(activity["id"], "activity.id")
        _require_int(activity["epoch"], "activity.epoch")
        state = activity["state"]
        if state not in ACTIVITY_STATES:
            raise ControlSchemaError(f"unknown activity state: {state!r}")
        turn, suspension = activity["turn"], activity["suspension"]
        if state == "ACTIVE" and (turn is None or suspension is not None):
            raise ControlSchemaError("ACTIVE requires turn and forbids suspension")
        if state == "SUSPENDED" and (turn is not None or suspension is None):
            raise ControlSchemaError("SUSPENDED requires suspension and forbids turn")
        if turn is not None:
            _require_keys(turn, _TURN_KEYS, "activity.turn")
            if turn["owner"] != "executor":
                raise ControlSchemaError("turn.owner must be 'executor' (REQ-003)")
            _require_token(turn["token"], "turn.token")
            _require_timestamp(turn["acquired_at"], "turn.acquired_at")
        if suspension is not None:
            _require_keys(suspension, _SUSPENSION_KEYS, "activity.suspension")
            for key in ("previous_state", "checkpoint", "reason"):
                _require_str(suspension[key], f"suspension.{key}")
            _require_token(suspension["owning_turn"], "suspension.owning_turn")
            if suspension["in_flight"] is not None:
                _require_str(suspension["in_flight"], "suspension.in_flight")
            evidence = suspension["evidence"]
            if not isinstance(evidence, list) \
                    or any(not isinstance(p, str) or not p for p in evidence):
                raise ControlSchemaError("suspension.evidence must be a list of paths")
            _require_timestamp(suspension["at"], "suspension.at")

    request = control["stop_request"]
    if request is not None:
        _require_keys(request, _REQUEST_KEYS, "stop_request")
        _require_token(request["id"], "stop_request.id")
        _require_str(request["activity_id"], "stop_request.activity_id")
        _require_int(request["activity_epoch"], "stop_request.activity_epoch")
        if request["turn_token"] is not None:
            _require_token(request["turn_token"], "stop_request.turn_token")
        if request["reason"] is not None:
            _require_str(request["reason"], "stop_request.reason")
        _require_timestamp(request["requested_at"], "stop_request.requested_at")

    concluded = control["last_concluded"]
    if concluded is not None:
        _require_keys(concluded, _CONCLUDED_KEYS, "last_concluded")
        for key in ("type", "id", "status"):
            _require_str(concluded[key], f"last_concluded.{key}")
        _require_int(concluded["epoch"], "last_concluded.epoch")
        _require_timestamp(concluded["at"], "last_concluded.at")


def assert_turn_token(control: Mapping[str, Any], turn_token: str) -> None:
    activity = control.get("activity")
    current = (activity or {}).get("turn") or {}
    if current.get("token") != turn_token:
        raise NotLockOwner("turn token diverged (lock was taken over?)")


class ControlStore:
    def __init__(self, path: Path, audit: AuditLog, *,
                 mutation_timeout: float = 60.0,
                 lock_file: Path | None = None) -> None:
        self._path = Path(path)
        self._audit = audit
        # PLAN-001 errata (PLAN-002 STEP-01): the mutation lock is disposable
        # process state, so the PRODUCT places it in the XDG state dir
        # (REQ-001 §3). The adjacent default remains for bare-library use only.
        self._mutex_file = (Path(lock_file) if lock_file is not None
                            else self._path.with_name(self._path.name + ".lock"))
        self._mutation_timeout = mutation_timeout

    @property
    def path(self) -> Path:
        return self._path

    @property
    def audit(self) -> AuditLog:
        return self._audit

    def seed(self) -> dict[str, Any]:
        """Creates the initial control file (refuses to overwrite)."""
        if self._path.exists():
            raise ControlSchemaError(f"{self._path} already exists")
        control = initial_control()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._publish(control)
        return control

    def load(self) -> dict[str, Any]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ControlSchemaError(f"{self._path} does not exist (run seed)") from None
        try:
            control = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ControlSchemaError(f"corrupt control file: {exc}") from exc
        validate_control(control)
        return control

    def cas_write(self, expected_version: int, new_control: Mapping[str, Any],
                  *, turn_token: str | None = None) -> dict[str, Any]:
        """Publishes new_control iff the stored version equals expected_version.

        With turn_token set, additionally enforces ABA fencing: the CURRENT
        stored control must carry that token as the active turn."""
        with self._mutation_mutex():
            self._clean_orphan_tempfiles()
            current = self.load()
            if turn_token is not None:
                assert_turn_token(current, turn_token)
            if current["version"] != expected_version:
                raise VersionConflict(
                    f"expected version {expected_version}, found {current['version']}")
            control = dict(new_control)
            control["schema_version"] = SCHEMA_VERSION
            control["version"] = expected_version + 1
            control["updated_at"] = utcnow()
            validate_control(control)
            self._check_epoch_monotonic(current, control)
            self._publish(control)
            return control

    def mutate(self, fn: Callable[[dict[str, Any]], dict[str, Any]], *,
               turn_token: str | None = None, retries: int = 10) -> dict[str, Any]:
        """Retry-on-conflict convenience: fn(current) -> new control body.

        True no-op guarantee: if fn returns the body semantically unchanged
        (e.g. an equivalent transition raced in), nothing is published — the
        version and updated_at stay put."""
        for _ in range(retries):
            current = self.load()
            new_body = fn(json.loads(json.dumps(current)))  # deep copy for fn
            unchanged = {k: v for k, v in new_body.items()} == current
            if unchanged:
                return current
            try:
                return self.cas_write(current["version"], new_body,
                                      turn_token=turn_token)
            except VersionConflict:
                time.sleep(0.02)
        raise VersionConflict(f"could not apply mutation after {retries} retries")

    # -- critical section -------------------------------------------------

    def _mutation_mutex(self) -> "_FlockMutex":
        return _FlockMutex(self._mutex_file, self._mutation_timeout)

    @staticmethod
    def _check_epoch_monotonic(current: Mapping[str, Any],
                               new: Mapping[str, Any]) -> None:
        """Epoch never regresses — INCLUDING through the idle cycle: the floor
        survives activity=null via last_concluded.epoch, and (re)starting from
        idle demands a STRICTLY greater epoch (ABA guard)."""
        def floor_of(control: Mapping[str, Any]) -> int:
            values = [-1]
            if control.get("activity") is not None:
                values.append(control["activity"]["epoch"])
            if control.get("last_concluded") is not None:
                values.append(control["last_concluded"]["epoch"])
            return max(values)

        current_floor = floor_of(current)
        # The floor itself may NEVER regress — concluding an activity cannot
        # erase it (e.g. epoch 10 concluded as last_concluded.epoch=1 or null).
        if floor_of(new) < current_floor:
            raise ControlSchemaError(
                f"epoch floor must not regress ({current_floor} -> {floor_of(new)})")
        new_activity = new.get("activity")
        if new_activity is None:
            return
        if current.get("activity") is None:
            if current_floor >= 0 and new_activity["epoch"] <= current_floor:
                raise ControlSchemaError(
                    f"starting from idle requires epoch > {current_floor} "
                    f"(got {new_activity['epoch']})")
        elif new_activity["epoch"] < current_floor:
            raise ControlSchemaError(
                f"activity.epoch must not decrease ({current_floor} -> "
                f"{new_activity['epoch']})")

    def _clean_orphan_tempfiles(self) -> None:
        for orphan in self._path.parent.glob(_TMP_PREFIX + "*"):
            try:
                orphan.unlink()
            except OSError:
                pass

    def _publish(self, control: Mapping[str, Any]) -> None:
        tmp = self._path.with_name(f"{_TMP_PREFIX}{uuid.uuid4().hex}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(control, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            if _CRASH_BEFORE_REPLACE:  # test hook: simulated crash
                os._exit(42)
            os.replace(tmp, self._path)
            dir_fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass


_CRASH_BEFORE_REPLACE = False  # flipped only by crash-consistency tests


class _FlockMutex:
    """Exclusive critical section backed by a kernel flock on a lock FILE.

    Single-host guarantees (REQ-003 v0): acquisition is atomic in the kernel;
    a dead holder's flock is released AUTOMATICALLY — there is no staleness
    judgment, eviction or recovery code, hence nothing to race on. The lock
    file is created once and NEVER unlinked (unlinking would allow two locks
    on different inodes)."""

    _POLL = 0.01

    def __init__(self, lock_file: Path, timeout: float) -> None:
        self._file = lock_file
        self._timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "_FlockMutex":
        self._file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._file, os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise MutationMutexBusy(
                        f"critical section busy: {self._file}") from None
                time.sleep(self._POLL)
        self._fd = fd
        return self

    def __exit__(self, *exc_info):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
            self._fd = None
        return False
