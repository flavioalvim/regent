"""Transactional control store: control.json with real compare-and-swap.

Origin: reimplements the proven invariants of the ArtNFT protocol layer
(docs/brainstorm-mvp/scripts/control_adapters.py: atomic tempfile+replace
publication; control_domain.py: monotonic CAS versioning and strict schema
default-deny) under the regent v1 actor model (REQ-003: single executor).

Concurrency: read-check-replace alone is NOT a CAS (two writers could both
validate the same version — lost update). Every mutation therefore runs inside
a short exclusive mutation mutex (mkdir-style, distinct from the turn lock;
never held while acquiring the turn lock — acquire the turn lock first, then
mutate). A crashed holder leaves a recoverable mutex: stale (old or dead pid)
mutex dirs are force-removed with an audit record.

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


class ControlSchemaError(ValueError):
    """Control file is corrupt, has an unknown schema or violates invariants."""


class VersionConflict(RuntimeError):
    """The control version diverged from the expected one (CAS failure)."""


class MutationMutexBusy(RuntimeError):
    """Could not enter the mutation critical section within the timeout."""


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


def validate_control(control: Mapping[str, Any]) -> None:
    if not isinstance(control, Mapping):
        raise ControlSchemaError("control must be an object")
    if control.get("schema_version") != SCHEMA_VERSION:
        raise ControlSchemaError(f"unknown schema_version: {control.get('schema_version')!r}")
    if not isinstance(control.get("version"), int) or control["version"] < 0:
        raise ControlSchemaError("version must be a non-negative int")
    activity = control.get("activity")
    if activity is not None:
        if activity.get("type") not in ACTIVITY_TYPES:
            raise ControlSchemaError(f"unknown activity type: {activity.get('type')!r}")
        if not isinstance(activity.get("id"), str) or not activity["id"]:
            raise ControlSchemaError("activity.id must be a non-empty string")
        if not isinstance(activity.get("epoch"), int) or activity["epoch"] < 0:
            raise ControlSchemaError("activity.epoch must be a non-negative int")
        state = activity.get("state")
        if state not in ACTIVITY_STATES:
            raise ControlSchemaError(f"unknown activity state: {state!r}")
        turn, suspension = activity.get("turn"), activity.get("suspension")
        if state == "ACTIVE" and (turn is None or suspension is not None):
            raise ControlSchemaError("ACTIVE requires turn and forbids suspension")
        if state == "SUSPENDED" and (turn is not None or suspension is None):
            raise ControlSchemaError("SUSPENDED requires suspension and forbids turn")
        if turn is not None and not turn.get("token"):
            raise ControlSchemaError("turn.token is required")
        if suspension is not None:
            missing = [k for k in ("previous_state", "checkpoint", "owning_turn", "reason", "at")
                       if not suspension.get(k)]
            if missing:
                raise ControlSchemaError(f"suspension payload missing: {missing}")
    request = control.get("stop_request")
    if request is not None:
        for key in ("id", "activity_id", "requested_at"):
            if not request.get(key):
                raise ControlSchemaError(f"stop_request.{key} is required")
        if not isinstance(request.get("activity_epoch"), int):
            raise ControlSchemaError("stop_request.activity_epoch must be an int")


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

    def _mutation_mutex(self):
        return _MutationMutex(self._mutex_dir, self._audit, self._mutation_timeout)

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

    Stale recovery: a mutex whose meta.json is older than the timeout, or whose
    recorded pid is dead, is force-removed with an audit record so a crashed
    holder never blocks future mutations."""

    _POLL = 0.01

    def __init__(self, mutex_dir: Path, audit: AuditLog, timeout: float) -> None:
        self._dir = mutex_dir
        self._audit = audit
        self._timeout = timeout

    def __enter__(self):
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
        meta = {"pid": os.getpid(), "at": utcnow()}
        (self._dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return self

    def __exit__(self, *exc_info):
        self._remove()
        return False

    def _recover_if_stale(self) -> None:
        meta_path = self._dir / "meta.json"
        stale_reason = None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            holder_pid = int(meta.get("pid", -1))
            held_at = datetime.fromisoformat(meta["at"])
            age = (datetime.now(timezone.utc) - held_at).total_seconds()
            if age > self._timeout:
                stale_reason = f"held for {int(age)}s > timeout"
            elif not _pid_alive(holder_pid):
                stale_reason = f"holder pid {holder_pid} is dead"
        except (OSError, ValueError, KeyError):
            # No/corrupt meta: only stale once the dir itself outlives the timeout
            # (grace for the window between mkdir and meta write).
            try:
                age = time.time() - self._dir.stat().st_mtime
            except OSError:
                return  # already gone
            if age > self._timeout:
                stale_reason = f"ownerless mutex dir for {int(age)}s > timeout"
        if stale_reason:
            self._remove()
            self._audit.append({"event": "mutation_mutex_recovered",
                                "mutex": str(self._dir), "reason": stale_reason})

    def _remove(self) -> None:
        try:
            (self._dir / "meta.json").unlink()
        except OSError:
            pass
        try:
            os.rmdir(self._dir)
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
