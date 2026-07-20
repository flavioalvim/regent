"""Directed tests for the activity application layer (PLAN-002 STEP-01)."""

import json
import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path

from regent.activity import (ActivityOpen, ActivityService, LockSuspectError,
                             NoActivity, NotActive, NotSuspended, TokenMismatch)
from regent.protocol import TurnLock
from regent.protocol.audit import AuditLog


def _service(root: Path, state: Path) -> ActivityService:
    (root / ".regent").mkdir(parents=True, exist_ok=True)
    service = ActivityService(root, state_dir=state)
    if not service.store.path.exists():
        service.store.seed()
    return service


def _crashing_op(root: str, state: str, op: str, point: str) -> None:
    from regent import activity as activity_mod
    activity_mod._CRASH_POINTS.add(point)
    service = ActivityService(Path(root), state_dir=Path(state))
    if op == "start":
        service.start("plan", "PLAN-X")
    elif op == "suspend":
        service.suspend(checkpoint="CP", reason="stop")
    elif op == "resume":
        service.resume()
    elif op == "conclude":
        service.conclude("ACCEPTED")


def _concurrent_start(root: str, state: str, barrier, queue) -> None:
    service = ActivityService(Path(root), state_dir=Path(state))
    barrier.wait()
    try:
        service.start("plan", f"PLAN-{mp.current_process().pid}")
        queue.put("ok")
    except (ActivityOpen, Exception):
        queue.put("refused")


class ActivityServiceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.root = base / "repo"
        self.state = base / "state"
        self.root.mkdir()
        self.state.mkdir()
        self.service = _service(self.root, self.state)

    def _crash(self, op: str, point: str, expect_code: int = 43):
        proc = mp.Process(target=_crashing_op,
                          args=(str(self.root), str(self.state), op, point))
        proc.start()
        proc.join(timeout=20)
        self.assertEqual(proc.exitcode, expect_code)

    # -- lifecycle ---------------------------------------------------------

    def test_start_resume_suspend_conclude_epochs(self):
        started = self.service.start("plan", "PLAN-A")
        self.assertEqual(started["activity"]["epoch"], 0)  # fresh floor(-1) + 1
        self.assertEqual(started["activity"]["state"], "ACTIVE")
        self.service.suspend(checkpoint="STEP-02", reason="pause",
                             evidence=[".regent/plans"])
        resumed = self.service.resume()
        self.assertEqual(resumed["checkpoint"], "STEP-02")
        self.assertGreater(resumed["activity"]["epoch"], started["activity"]["epoch"])
        concluded = self.service.conclude("ACCEPTED")
        self.assertEqual(concluded["last_concluded"]["id"], "PLAN-A")
        self.assertEqual(concluded["last_concluded"]["epoch"],
                         resumed["activity"]["epoch"])
        self.assertIsNone(self.service.status()["control"]["activity"])
        self.assertEqual(self.service.status()["lock"]["state"], "free")
        self.assertFalse(self.service.status()["local_token_present"])

    def test_resume_increments_epoch(self):
        self.service.start("plan", "PLAN-A")
        self.service.suspend(checkpoint="CP", reason="r")
        first = self.service.resume()["activity"]["epoch"]
        self.service.suspend(checkpoint="CP2", reason="r")
        second = self.service.resume()["activity"]["epoch"]
        self.assertGreater(second, first)

    def test_start_refuses_second_activity(self):
        self.service.start("plan", "PLAN-A")
        with self.assertRaises(ActivityOpen):
            self.service.start("brainstorm", "ROUND-001")

    def test_suspend_requires_active_and_resume_requires_suspended(self):
        with self.assertRaises(NoActivity):
            self.service.suspend(checkpoint="CP", reason="r")
        with self.assertRaises(NoActivity):
            self.service.resume()
        self.service.start("plan", "PLAN-A")
        with self.assertRaises(NotSuspended):
            self.service.resume()
        self.service.suspend(checkpoint="CP", reason="r")
        with self.assertRaises(NotActive):
            self.service.suspend(checkpoint="CP", reason="r")

    def test_suspend_records_evidence_paths(self):
        self.service.start("build", "PLAN-B")
        self.service.suspend(checkpoint="STEP-01:GATE-RED", reason="stop",
                             evidence=["docs/PRD.md", "missing/file.md"])
        suspension = self.service.store.load()["activity"]["suspension"]
        self.assertEqual(suspension["evidence"], ["docs/PRD.md", "missing/file.md"])
        resumed = self.service.resume()
        self.assertIn("missing/file.md", resumed["missing_evidence"])

    def test_heartbeat_renews(self):
        self.service.start("plan", "PLAN-A")
        before = json.loads((self.service.lock.path / "owner.json").read_text())
        result = self.service.heartbeat()
        self.assertIn("heartbeat_at", result)
        after = json.loads((self.service.lock.path / "owner.json").read_text())
        self.assertGreaterEqual(after["heartbeat_at"], before["heartbeat_at"])

    def test_no_lock_files_under_regent_dir(self):
        self.service.start("plan", "PLAN-A")
        self.service.suspend(checkpoint="CP", reason="r")
        stray = list((self.root / ".regent").rglob("*.lock")) \
            + list((self.root / ".regent").rglob("*.lock.d"))
        self.assertEqual(stray, [])

    # -- recovery table (non-sane rows) ------------------------------------

    def test_recovery_row_2_and_12_local_token_repaired(self):
        started = self.service.start("plan", "PLAN-A")
        self.service.token_file.unlink()  # row 2
        self.service.heartbeat()  # recovery rewrites it
        self.assertTrue(self.service.token_file.exists())
        self.service.token_file.write_text(
            json.dumps({"token": "ff" * 16}), encoding="utf-8")  # row 12
        self.service.heartbeat()
        repaired = json.loads(self.service.token_file.read_text())["token"]
        self.assertEqual(repaired, started["token"])

    def test_recovery_row_3_active_without_lock_demands_takeover(self):
        self.service.start("plan", "PLAN-A")
        token = json.loads(self.service.token_file.read_text())["token"]
        self.service.lock.release(token)  # out-of-protocol removal
        with self.assertRaises(LockSuspectError):
            self.service.heartbeat()
        result = self.service.takeover(reason="row 3 recovery")
        control = self.service.store.load()
        self.assertEqual(control["activity"]["turn"]["token"], result["token"])

    def test_recovery_row_4_suspect_lock_demands_takeover(self):
        stale_lock = TurnLock(self.state, AuditLog(self.state / "a.jsonl"),
                              stale_after=0.0)
        service = ActivityService(self.root, state_dir=self.state)
        service.lock = stale_lock
        service.start("plan", "PLAN-A")
        with self.assertRaises(LockSuspectError):
            service.suspend(checkpoint="CP", reason="r")

    def test_recovery_row_5_token_mismatch(self):
        self.service.start("plan", "PLAN-A")

        def fn(body):
            body["activity"]["turn"]["token"] = "aa" * 16
            return body
        self.service.store.mutate(fn)
        with self.assertRaises(TokenMismatch):
            self.service.suspend(checkpoint="CP", reason="r")

    def test_recovery_rows_6_8_lock_released_after_crash(self):
        self._crash("start", "start:after_cas")  # ACTIVE + held, no local token
        self._crash_recovered_suspend_path()

    def _crash_recovered_suspend_path(self):
        # Recovery row 2 rewrites the local token; then suspend crashes
        # after CAS (row 6: SUSPENDED + held) and a later entry releases.
        self._crash("suspend", "suspend:after_cas")
        control = self.service._recover()
        self.assertEqual(control["activity"]["state"], "SUSPENDED")
        self.assertEqual(self.service.lock.status()["state"], "free")  # row 6 repaired

    def test_recovery_rows_10_11_token_cleanup(self):
        self.service.start("plan", "PLAN-A")
        self._crash("suspend", "suspend:before_token_cleanup")  # row 10
        self.assertTrue(self.service.token_file.exists())
        self.service._recover()
        self.assertFalse(self.service.token_file.exists())

    # -- fault injection at remaining boundaries ---------------------------

    def test_crash_start_between_lock_and_cas(self):
        self._crash("start", "start:after_lock")
        # control idle + lock held (rows 8): recovery releases and start works.
        self.service.start("plan", "PLAN-A")

    def test_crash_resume_between_lock_and_cas(self):
        self.service.start("plan", "PLAN-A")
        self.service.suspend(checkpoint="CP", reason="r")
        self._crash("resume", "resume:after_lock")
        resumed = self.service.resume()  # rows 6-analog repaired by recovery
        self.assertEqual(resumed["checkpoint"], "CP")

    def test_crash_conclude_between_cas_and_release(self):
        self.service.start("plan", "PLAN-A")
        self._crash("conclude", "conclude:after_cas")  # idle + held (row 8)
        control = self.service._recover()
        self.assertIsNone(control["activity"])
        self.assertEqual(self.service.lock.status()["state"], "free")
        self.service.start("plan", "PLAN-B")  # and life goes on

    def test_double_start_concurrent_one_wins(self):
        barrier = mp.Barrier(2)
        queue = mp.Queue()
        procs = [mp.Process(target=_concurrent_start,
                            args=(str(self.root), str(self.state), barrier, queue))
                 for _ in range(2)]
        for p in procs:
            p.start()
        outcomes = sorted(queue.get(timeout=20) for _ in procs)
        for p in procs:
            p.join(timeout=20)
        self.assertEqual(outcomes, ["ok", "refused"])
        control = self.service.store.load()
        self.assertEqual(control["activity"]["state"], "ACTIVE")

    def test_takeover_rotates_and_writes_local_token(self):
        self.service.start("plan", "PLAN-A")
        old = json.loads(self.service.token_file.read_text())["token"]
        self.service.lock.release(old)  # manufacture row 3
        result = self.service.takeover(reason="test")
        self.assertNotEqual(result["token"], old)
        self.assertEqual(result["previous_owner"], old)
        control = self.service.store.load()
        self.assertEqual(control["activity"]["turn"]["token"], result["token"])
        local = json.loads(self.service.token_file.read_text())["token"]
        self.assertEqual(local, result["token"])


if __name__ == "__main__":
    unittest.main()
