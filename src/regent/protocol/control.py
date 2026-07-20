"""Transactional control store: control.json with real compare-and-swap.

Origin: reimplements the proven invariants of the ArtNFT protocol layer
(docs/brainstorm-mvp/scripts/control_adapters.py: atomic tempfile+replace
publication; control_domain.py: monotonic CAS versioning and strict schema
default-deny) under the regent v1 actor model (REQ-003: single executor).

Concurrency: read-check-replace alone is NOT a CAS (two writers could both
validate the same version — lost update). Every mutation therefore runs inside
a short exclusive mutation mutex (mkdir-style, distinct from the turn lock;
never held while acquiring the turn lock — acquire the turn lock first, then
mutate). Mutex instances carry an identity token; recovery ONLY evicts a
holder whose pid is dead (or an ownerless dir past the timeout) — an alive
holder is never evicted, however slow, so two CAS winners are impossible.
Recovery is audited BEFORE acting and claims the judged instance by atomic
rename (two concurrent recoverers cannot both evict). The holder re-verifies
its mutex identity immediately before publishing.

Publication separates atomicity from durability: tempfile in the same
directory → flush+fsync(file) → os.replace → fsync(directory).
"""

from __future__ import annotations

import errno
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
                    "reason", "at"}
_REQUEST_KEYS = {"id", "activity_id", "activity_epoch", "turn_token", "requested_at"}
_CONCLUDED_KEYS = {"type", "id", "status", "at"}


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


def _require_timestamp(value: Any, label: str) -> None:
    _require_str(value, label)
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ControlSchemaError(f"{label} is not an ISO-8601 timestamp: {value!r}") from None


def validate_control(control: Mapping[str, Any]) -> None:
    """Strict default-deny validation: exact key sets, types, timestamps and the
    ACTIVE/SUSPENDED invariants. Unknown or missing fields are rejected."""
    _require_keys(control, _TOP_KEYS, "control")
    if control["schema_version"] != SCHEMA_VERSION:
        raise ControlSchemaError(f"unknown schema_version: {control['schema_version']!r}")
    if not isinstance(control["version"], int) or control["version"] < 0:
        raise ControlSchemaError("version must be a non-negative int")
    _require_timestamp(control["updated_at"], "updated_at")

    activity = control["activity"]
    if activity is not None:
        _require_keys(activity, _ACTIVITY_KEYS, "activity")
        if activity["type"] not in ACTIVITY_TYPES:
            raise ControlSchemaError(f"unknown activity type: {activity['type']!r}")
        _require_str(activity["id"], "activity.id")
        if not isinstance(activity["epoch"], int) or activity["epoch"] < 0:
            raise ControlSchemaError("activity.epoch must be a non-negative int")
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
            _require_str(turn["token"], "turn.token")
            _require_timestamp(turn["acquired_at"], "turn.acquired_at")
        if suspension is not None:
            _require_keys(suspension, _SUSPENSION_KEYS, "activity.suspension")
            for key in ("previous_state", "checkpoint", "owning_turn", "reason"):
                _require_str(suspension[key], f"suspension.{key}")
            if suspension["in_flight"] is not None:
                _require_str(suspension["in_flight"], "suspension.in_flight")
            _require_timestamp(suspension["at"], "suspension.at")

    request = control["stop_request"]
    if request is not None:
        _require_keys(request, _REQUEST_KEYS, "stop_request")
        _require_str(request["id"], "stop_request.id")
        _require_str(request["activity_id"], "stop_request.activity_id")
        if not isinstance(request["activity_epoch"], int):
            raise ControlSchemaError("stop_request.activity_epoch must be an int")
        if request["turn_token"] is not None:
            _require_str(request["turn_token"], "stop_request.turn_token")
        _require_timestamp(request["requested_at"], "stop_request.requested_at")

    concluded = control["last_concluded"]
    if concluded is not None:
        _require_keys(concluded, _CONCLUDED_KEYS, "last_concluded")
        for key in ("type", "id", "status"):
            _require_str(concluded[key], f"last_concluded.{key}")
        _require_timestamp(concluded["at"], "last_concluded.at")


def assert_turn_token(control: Mapping[str, Any], turn_token: str) -> None:
    activity = control.get("activity")
    current = (activity or {}).get("turn") or {}
    if current.get("token") != turn_token:
        raise NotLockOwner("turn token diverged (lock was taken over?)")


class ControlStore:
    def __init__(self, path: Path, audit: AuditLog, *,
                 mutation_timeout: float = 60.0) -> None:
        self._path = Path(path)
        self._audit = audit
        self._mutex_dir = self._path.with_name(self._path.name + ".lock.d")
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
        with self._mutation_mutex() as mutex:
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
            mutex.verify_still_held()  # belt-and-suspenders before publishing
            self._publish(control)
            return control

    def mutate(self, fn: Callable[[dict[str, Any]], dict[str, Any]], *,
               turn_token: str | None = None, retries: int = 10) -> dict[str, Any]:
        """Retry-on-conflict convenience: fn(current) -> new control body."""
        for _ in range(retries):
            current = self.load()
            try:
                return self.cas_write(current["version"], fn(dict(current)),
                                      turn_token=turn_token)
            except VersionConflict:
                time.sleep(0.02)
        raise VersionConflict(f"could not apply mutation after {retries} retries")

    # -- critical section -------------------------------------------------

    def _mutation_mutex(self) -> "_MutationMutex":
        return _MutationMutex(self._mutex_dir, self._audit, self._mutation_timeout)

    @staticmethod
    def _check_epoch_monotonic(current: Mapping[str, Any],
                               new: Mapping[str, Any]) -> None:
        current_activity, new_activity = current.get("activity"), new.get("activity")
        if current_activity is not None and new_activity is not None:
            if new_activity["epoch"] < current_activity["epoch"]:
                raise ControlSchemaError(
                    f"activity.epoch must not decrease "
                    f"({current_activity['epoch']} -> {new_activity['epoch']})")

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


class _MutationMutex:
    """Short exclusive mkdir-style mutex around control mutations.

    Instance identity: meta.json carries {pid, at, token}. Recovery ONLY
    evicts a dead holder (or an ownerless dir past the timeout) — an alive
    holder is never evicted. Eviction is audited BEFORE acting and claims the
    judged instance by atomic rename, so concurrent recoverers cannot both
    evict, and can never evict a fresh instance (token compare)."""

    _POLL = 0.01

    def __init__(self, mutex_dir: Path, audit: AuditLog, timeout: float) -> None:
        self._dir = mutex_dir
        self._audit = audit
        self._timeout = timeout
        self._token: str | None = None

    def __enter__(self) -> "_MutationMutex":
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                os.mkdir(self._dir)
                break
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
                self._recover_if_stale()
                if time.monotonic() >= deadline:
                    raise MutationMutexBusy(f"mutation mutex busy: {self._dir}") from None
                time.sleep(self._POLL)
        self._token = uuid.uuid4().hex
        meta = {"pid": os.getpid(), "at": utcnow(), "token": self._token}
        (self._dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return self

    def __exit__(self, *exc_info):
        self._remove(self._dir)
        return False

    def verify_still_held(self) -> None:
        meta = self._read_meta(self._dir)
        if meta is None or meta.get("token") != self._token:
            raise MutationMutexBusy("mutation mutex lost during critical section")

    def _recover_if_stale(self) -> None:
        meta = self._read_meta(self._dir)
        stale_reason = None
        if meta is not None:
            holder_pid = int(meta.get("pid", -1))
            if not _pid_alive(holder_pid):
                stale_reason = f"holder pid {holder_pid} is dead"
            # An ALIVE holder is never evicted, however old: evicting it could
            # let two CAS writers win. Callers time out with MutationMutexBusy.
        else:
            try:
                age = time.time() - self._dir.stat().st_mtime
            except OSError:
                return  # already gone
            if age > self._timeout:
                stale_reason = f"ownerless mutex dir for {int(age)}s > timeout"
        if not stale_reason:
            return
        judged_token = (meta or {}).get("token")
        # Audit the INTENT first: a crash after this point leaves a record.
        self._audit.append({"event": "mutation_mutex_recovered",
                            "mutex": str(self._dir), "reason": stale_reason,
                            "evicted_token": judged_token})
        aside = self._dir.with_name(self._dir.name + f".evict-{uuid.uuid4().hex}")
        try:
            os.rename(self._dir, aside)  # atomic claim: one recoverer wins
        except FileNotFoundError:
            return  # someone else recovered it first
        aside_meta = self._read_meta(aside)
        if (aside_meta or {}).get("token") != judged_token:
            # Fresh instance appeared in between: restore it, never evict.
            try:
                os.rename(aside, self._dir)
            except OSError:
                self._audit.append({"event": "mutation_mutex_restore_failed",
                                    "aside": str(aside)})
            return
        self._remove(aside)

    @staticmethod
    def _read_meta(mutex_dir: Path) -> dict | None:
        try:
            return json.loads((mutex_dir / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _remove(mutex_dir: Path) -> None:
        try:
            (mutex_dir / "meta.json").unlink()
        except OSError:
            pass
        try:
            os.rmdir(mutex_dir)
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
