"""Directed tests for the transactional control store (PLAN-001 STEP-01)."""

import json
import multiprocessing as mp
import os
import tempfile
import unittest
from pathlib import Path

from regent.protocol.audit import AuditLog
from regent.protocol.control import (ControlSchemaError, ControlStore,
                                     VersionConflict, initial_control)


def _store(root: Path) -> ControlStore:
    return ControlStore(root / "control.json", AuditLog(root / "audit.jsonl"),
                        mutation_timeout=5.0)


def _cas_writer(root: str, barrier, queue) -> None:
    store = _store(Path(root))
    barrier.wait()
    try:
        body = store.load()
        body["last_concluded"] = {"type": "plan", "id": f"PLAN-{os.getpid()}",
                                  "status": "ACCEPTED", "at": "2026-01-01T00:00:00+00:00"}
        store.cas_write(0, body)
        queue.put("ok")
    except VersionConflict:
        queue.put("conflict")


def _mutating_writer(root: str, field_id: str, barrier) -> None:
    store = _store(Path(root))
    barrier.wait()
    if field_id == "stop":
        def fn(body):
            body["stop_request"] = {"id": "req-1", "activity_id": "PLAN-001",
                                    "activity_epoch": 1, "turn_token": None,
                                    "requested_at": "2026-01-01T00:00:00+00:00"}
            return body
    else:
        def fn(body):
            body["last_concluded"] = {"type": "plan", "id": "PLAN-000",
                                      "status": "ACCEPTED", "at": "2026-01-01T00:00:00+00:00"}
            return body
    store.mutate(fn, retries=50)


def _crashing_writer(root: str) -> None:
    from regent.protocol import control as control_mod
    control_mod._CRASH_BEFORE_REPLACE = True
    store = _store(Path(root))
    body = store.load()
    body["last_concluded"] = {"type": "plan", "id": "PLAN-CRASH",
                              "status": "ACCEPTED", "at": "2026-01-01T00:00:00+00:00"}
    store.cas_write(0, body)  # os._exit(42) fires before os.replace


def _audit_appender(root: str, worker: int, barrier) -> None:
    log = AuditLog(Path(root) / "audit.jsonl")
    barrier.wait()
    for i in range(25):
        log.append({"event": "concurrency", "worker": worker, "seq": i})


class ControlStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.store = _store(self.root)
        self.store.seed()

    def test_cas_two_processes_one_wins(self):
        barrier = mp.Barrier(2)
        queue = mp.Queue()
        procs = [mp.Process(target=_cas_writer, args=(str(self.root), barrier, queue))
                 for _ in range(2)]
        for p in procs:
            p.start()
        results = sorted(queue.get(timeout=15) for _ in procs)
        for p in procs:
            p.join(timeout=15)
        self.assertEqual(results, ["conflict", "ok"])
        self.assertEqual(self.store.load()["version"], 1)

    def test_concurrent_stop_and_executor_update_no_field_loss(self):
        barrier = mp.Barrier(2)
        procs = [mp.Process(target=_mutating_writer, args=(str(self.root), fid, barrier))
                 for fid in ("stop", "concluded")]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=15)
            self.assertEqual(p.exitcode, 0)
        final = self.store.load()
        self.assertIsNotNone(final["stop_request"])
        self.assertIsNotNone(final["last_concluded"])
        self.assertEqual(final["version"], 2)

    def test_corrupt_control_rejected_untouched(self):
        path = self.root / "control.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ControlSchemaError):
            self.store.load()
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")

    def test_invariant_violation_rejected(self):
        body = initial_control()
        body["activity"] = {"type": "plan", "id": "PLAN-001", "epoch": 1,
                            "state": "ACTIVE", "turn": None, "suspension": None}
        with self.assertRaises(ControlSchemaError):
            self.store.cas_write(0, body)

    def test_kill_before_replace_leaves_control_intact(self):
        before = (self.root / "control.json").read_text(encoding="utf-8")
        proc = mp.Process(target=_crashing_writer, args=(str(self.root),))
        proc.start()
        proc.join(timeout=15)
        self.assertEqual(proc.exitcode, 42)
        self.assertEqual((self.root / "control.json").read_text(encoding="utf-8"), before)

    def test_mutation_recovers_and_writes_after_crash(self):
        proc = mp.Process(target=_crashing_writer, args=(str(self.root),))
        proc.start()
        proc.join(timeout=15)
        control = self.store.mutate(lambda body: body)  # crashed mutex must not block
        self.assertEqual(control["version"], 1)

    def test_mutation_mutex_stale_recovered_after_crash(self):
        mutex = self.root / "control.json.lock.d"
        mutex.mkdir()
        (mutex / "meta.json").write_text(
            json.dumps({"pid": 99999999, "at": "2026-01-01T00:00:00+00:00"}),
            encoding="utf-8")
        control = self.store.mutate(lambda body: body)
        self.assertEqual(control["version"], 1)
        events = [r["event"] for r in AuditLog(self.root / "audit.jsonl").read_all()]
        self.assertIn("mutation_mutex_recovered", events)

    def test_orphan_tempfiles_cleaned(self):
        orphan = self.root / ".control-tmp-deadbeef"
        orphan.write_text("junk", encoding="utf-8")
        self.store.mutate(lambda body: body)
        self.assertFalse(orphan.exists())

    def test_audit_append_fsynced_and_concurrent(self):
        fsyncs = []
        original = os.fsync
        try:
            os.fsync = lambda fd: fsyncs.append(fd) or original(fd)
            AuditLog(self.root / "audit.jsonl").append({"event": "one"})
        finally:
            os.fsync = original
        self.assertTrue(fsyncs, "append must fsync")

        barrier = mp.Barrier(4)
        procs = [mp.Process(target=_audit_appender, args=(str(self.root), n, barrier))
                 for n in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=15)
        records = AuditLog(self.root / "audit.jsonl").read_all()
        concurrent = [r for r in records if r.get("event") == "concurrency"]
        self.assertEqual(len(concurrent), 100)  # no torn/lost lines


if __name__ == "__main__":
    unittest.main()
