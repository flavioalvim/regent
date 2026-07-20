"""Directed tests for the executor turn lock (PLAN-001 STEP-02)."""

import json
import os
import multiprocessing as mp
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from regent.protocol.audit import AuditLog
from regent.protocol.control import ControlStore, NotLockOwner, initial_control
from regent.protocol.lock import LockHeld, StaleLock, TurnLock


def _takeover_candidate(state_dir: str, audit_path: str, barrier, queue) -> None:
    # Realistic threshold: the OLD seed lock is suspect; the winner's fresh
    # lock (heartbeat=now) is NOT, so exactly one candidate can win.
    lock = TurnLock(Path(state_dir), AuditLog(Path(audit_path)), stale_after=3600.0)
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
        graceless.path.mkdir()  # legacy crash artifact: dir without owner.json
        time.sleep(0.01)
        self.assertEqual(graceless.status()["state"], "suspect")
        graceless.takeover(actor="test", reason="crash window")

    def test_release_removal_failure_raises(self):
        token = self.lock.acquire()
        os.chmod(self.lock.path, 0o500)  # children cannot be unlinked
        try:
            with self.assertRaises(OSError):
                self.lock.release(token)
            self.assertTrue(self.lock.path.exists())  # caller KNOWS it still exists
        finally:
            os.chmod(self.lock.path, 0o700)
        self.lock.release(token)  # now it works, and is verified gone
        self.assertFalse(self.lock.path.exists())

    def test_takeover_removal_failure_leaves_control_unrotated(self):
        stale = TurnLock(self.state, self.audit, stale_after=0.0)
        old_token = stale.acquire()
        store = ControlStore(Path(self._tmp.name) / "control.json", self.audit)
        store.seed()
        body = initial_control()
        body["activity"] = {"type": "build", "id": "PLAN-001", "epoch": 1,
                            "state": "ACTIVE", "suspension": None,
                            "turn": {"owner": "executor", "token": old_token,
                                     "acquired_at": "2026-01-01T00:00:00+00:00"}}
        store.cas_write(0, body)
        time.sleep(0.01)
        os.chmod(stale.path, 0o500)  # strict removal will fail
        try:
            with self.assertRaises(OSError):
                stale.takeover(actor="mediator", reason="stale",
                               control_store=store)
        finally:
            os.chmod(stale.path, 0o700)
        control = store.load()
        self.assertEqual(control["activity"]["turn"]["token"], old_token)  # NOT rotated
        self.assertTrue(stale.path.exists())  # old lock preserved

    def test_acquire_refuses_ownerless_dir(self):
        # A plain acquire must NEVER absorb an existing dir — ownerless
        # included (POSIX rename could replace an empty target silently);
        # eviction is takeover's graced, audited job.
        self.lock.path.mkdir()
        with self.assertRaises(LockHeld):
            self.lock.acquire()
        self.assertTrue(self.lock.path.exists())  # untouched

    def test_takeover_race_single_winner(self):
        seed = TurnLock(self.state, self.audit)
        seed.acquire()
        owner_path = seed.path / "owner.json"
        stale_owner = json.loads(owner_path.read_text(encoding="utf-8"))
        stale_owner["heartbeat_at"] = "2020-01-01T00:00:00+00:00"  # long-dead beat
        owner_path.write_text(json.dumps(stale_owner), encoding="utf-8")
        barrier = mp.Barrier(2)
        queue = mp.Queue()
        procs = [mp.Process(target=_takeover_candidate,
                            args=(str(self.state), str(self.audit.path), barrier, queue))
                 for _ in range(2)]
        for p in procs:
            p.start()
        results = sorted((queue.get(timeout=15) for _ in procs), key=lambda r: r[0])
        for p in procs:
            p.join(timeout=15)
        self.assertEqual([r[0] for r in results], ["lost", "won"])
        winner_token = dict(results)["won"]
        owner = json.loads((seed.path / "owner.json").read_text(encoding="utf-8"))
        self.assertEqual(owner["token"], winner_token)  # winner IS the final owner

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
        # Control EXISTS FIRST with the old token; takeover(control_store=...)
        # must rotate it in the same operation (end-to-end fencing).
        stale = TurnLock(self.state, self.audit, stale_after=0.0)
        old_token = stale.acquire()
        store = ControlStore(Path(self._tmp.name) / "control.json", self.audit)
        store.seed()
        body = initial_control()
        body["activity"] = {"type": "build", "id": "PLAN-001", "epoch": 1,
                            "state": "ACTIVE", "suspension": None,
                            "turn": {"owner": "executor", "token": old_token,
                                     "acquired_at": "2026-01-01T00:00:00+00:00"}}
        store.cas_write(0, body)
        time.sleep(0.01)

        new_token = stale.takeover(actor="mediator", reason="stale",
                                   control_store=store)
        control = store.load()
        self.assertEqual(control["activity"]["turn"]["token"], new_token)

        with self.assertRaises(NotLockOwner):  # previous holder is fenced out
            store.cas_write(control["version"], dict(control), turn_token=old_token)
        store.cas_write(control["version"], dict(control), turn_token=new_token)

    def test_heartbeat_old_token_after_takeover_does_not_usurp(self):
        stale = TurnLock(self.state, self.audit, stale_after=0.0)
        old_token = stale.acquire()
        time.sleep(0.01)
        new_token = stale.takeover(actor="mediator", reason="stale")
        with self.assertRaises((NotLockOwner, StaleLock)):
            stale.heartbeat(old_token)
        owner = json.loads((stale.path / "owner.json").read_text(encoding="utf-8"))
        self.assertEqual(owner["token"], new_token)  # new holder untouched

    def test_release_old_token_after_takeover_preserves_new_lock(self):
        stale = TurnLock(self.state, self.audit, stale_after=0.0)
        old_token = stale.acquire()
        time.sleep(0.01)
        new_token = stale.takeover(actor="mediator", reason="stale")
        with self.assertRaises((NotLockOwner, StaleLock)):
            stale.release(old_token)
        owner = json.loads((stale.path / "owner.json").read_text(encoding="utf-8"))
        self.assertEqual(owner["token"], new_token)  # lock NOT destroyed
        stale.release(new_token)  # rightful owner still can release


if __name__ == "__main__":
    unittest.main()
