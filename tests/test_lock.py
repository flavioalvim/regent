"""Directed tests for the executor turn lock (PLAN-001 STEP-02)."""

import json
import multiprocessing as mp
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from regent.protocol.audit import AuditLog
from regent.protocol.control import (ControlStore, NotLockOwner as ControlTokenMismatch,
                                     initial_control)
from regent.protocol.lock import LockHeld, NotLockOwner, StaleLock, TurnLock


def _takeover_candidate(state_dir: str, audit_path: str, barrier, queue) -> None:
    lock = TurnLock(Path(state_dir), AuditLog(Path(audit_path)), stale_after=0.0)
    barrier.wait()
    try:
        queue.put(("won", lock.takeover(actor="test", reason="race")))
    except LockHeld:
        queue.put(("lost", None))


class TurnLockTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name) / "state"
        self.state.mkdir()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        self.audit = AuditLog(Path(self._tmp.name) / "audit.jsonl")
        self.addCleanup(self._tmp.cleanup)
        self.lock = TurnLock(self.state, self.audit,
                             stale_after=3600.0, ownerless_grace=3600.0)

    def test_second_acquire_fails(self):
        self.lock.acquire()
        with self.assertRaises(LockHeld):
            self.lock.acquire()

    def test_release_wrong_token_fails(self):
        token = self.lock.acquire()
        with self.assertRaises(NotLockOwner):
            self.lock.release("not-the-token")
        self.lock.release(token)
        self.assertEqual(self.lock.status()["state"], "free")

    def test_heartbeat_after_release_is_stale(self):
        token = self.lock.acquire()
        self.lock.release(token)
        with self.assertRaises(StaleLock):
            self.lock.heartbeat(token)

    def test_takeover_fresh_lock_refused(self):
        self.lock.acquire()
        with self.assertRaises(LockHeld):
            self.lock.takeover(actor="test", reason="impatience")

    def test_takeover_stale_lock_audited(self):
        stale = TurnLock(self.state, self.audit, stale_after=0.0)
        old_token = stale.acquire()
        time.sleep(0.01)
        new_token = stale.takeover(actor="mediator", reason="daemon crashed")
        self.assertNotEqual(old_token, new_token)
        records = [r for r in self.audit.read_all() if r["event"] == "turn_lock_takeover"]
        self.assertEqual(len(records), 1)
        for field in ("actor", "reason", "previous_owner", "age_seconds", "at"):
            self.assertIn(field, records[0])
        self.assertEqual(records[0]["previous_owner"], old_token)

    def test_ownerless_lock_suspect_after_grace(self):
        graceless = TurnLock(self.state, self.audit, ownerless_grace=0.0)
        graceless.path.mkdir()  # crash window: mkdir happened, owner.json never written
        time.sleep(0.01)
        self.assertEqual(graceless.status()["state"], "suspect")
        graceless.takeover(actor="test", reason="crash window")

    def test_takeover_race_single_winner(self):
        seed = TurnLock(self.state, self.audit, stale_after=0.0)
        seed.acquire()
        time.sleep(0.01)
        barrier = mp.Barrier(2)
        queue = mp.Queue()
        procs = [mp.Process(target=_takeover_candidate,
                            args=(str(self.state), str(self.audit.path), barrier, queue))
                 for _ in range(2)]
        for p in procs:
            p.start()
        outcomes = sorted(queue.get(timeout=15)[0] for _ in procs)
        for p in procs:
            p.join(timeout=15)
        self.assertEqual(outcomes, ["lost", "won"])

    def test_acquire_leaves_regent_and_git_untouched(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        regent_dir = self.repo / ".regent"
        regent_dir.mkdir()
        (regent_dir / "control.json").write_text("{}", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "-A"], check=True)
        before = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                                capture_output=True, text=True, check=True).stdout
        snapshot = {p: p.read_bytes() for p in regent_dir.rglob("*") if p.is_file()}

        self.lock.acquire()  # P-01: only the XDG-side state dir may change

        after = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(before, after)
        for path, content in snapshot.items():
            self.assertEqual(path.read_bytes(), content)

    def test_control_op_with_divergent_token_rejected_after_takeover(self):
        stale = TurnLock(self.state, self.audit, stale_after=0.0)
        old_token = stale.acquire()
        time.sleep(0.01)
        new_token = stale.takeover(actor="mediator", reason="stale")

        store = ControlStore(Path(self._tmp.name) / "control.json", self.audit)
        store.seed()
        body = initial_control()
        body["activity"] = {"type": "build", "id": "PLAN-001", "epoch": 1,
                            "state": "ACTIVE", "suspension": None,
                            "turn": {"owner": "executor", "token": new_token,
                                     "acquired_at": "2026-01-01T00:00:00+00:00"}}
        store.cas_write(0, body)

        with self.assertRaises(ControlTokenMismatch):  # previous holder is fenced out
            store.cas_write(1, body, turn_token=old_token)
        store.cas_write(1, dict(store.load()), turn_token=new_token)


if __name__ == "__main__":
    unittest.main()
