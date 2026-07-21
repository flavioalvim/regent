"""Directed tests for cancellable runner + abort-request (PLAN-005 STEP-01)."""

import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

from regent.activity import ActivityService
from regent.conduction import abort as abortmod
from regent.conduction import turn as turnmod
from regent.conduction.process import RunResult, SubprocessRunner
from regent.protocol.audit import AuditLog


class CancellableRunnerTest(unittest.TestCase):
    def test_runner_cancel_kills_group(self):
        cancel = threading.Event()
        pidfile = Path(tempfile.mktemp())
        self.addCleanup(lambda: pidfile.exists() and pidfile.unlink())
        runner = SubprocessRunner()

        def fire():
            time.sleep(0.5)
            cancel.set()
        threading.Thread(target=fire, daemon=True).start()
        result = runner.run(
            ["bash", "-c", f"sleep 60 & echo $! > {pidfile}; wait"],
            cwd="/tmp", timeout=30, cancel=cancel)
        self.assertTrue(result.aborted)
        self.assertFalse(result.timed_out)
        time.sleep(0.2)
        child = int(pidfile.read_text().strip())
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)  # the child died with the group

    def test_runner_no_deadlock_on_large_output(self):
        result = SubprocessRunner().run(
            ["bash", "-c", "yes X | head -c 500000"], cwd="/tmp", timeout=30)
        self.assertFalse(result.aborted)
        self.assertFalse(result.timed_out)
        self.assertGreaterEqual(len(result.output_bytes), 500000)

    def test_timeout_precedence_and_flag(self):
        result = SubprocessRunner().run(["bash", "-c", "sleep 30"], cwd="/tmp",
                                        timeout=0.4)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.aborted)


class AbortRequestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.audit = AuditLog(self.state / "audit.jsonl")

    def _write(self, **kw):
        base = dict(activity_id="PLAN-005", activity_epoch=4,
                    turn_token="ab" * 16, reason="stop it")
        base.update(kw)
        return abortmod.write_abort_request(self.state, **base)

    def test_abort_request_atomic_and_bound(self):
        req = self._write()
        self.assertEqual(req["activity_id"], "PLAN-005")
        self.assertTrue(abortmod.request_path(self.state).exists())

    def test_abort_o_excl_second_is_pending(self):
        self._write()
        with self.assertRaises(abortmod.AbortPending):
            self._write()

    def test_abort_stale_binding_discarded(self):
        self._write(activity_epoch=99)  # wrong epoch
        abortmod.write_turn_nonce(self.state, "nonce")
        claimed = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNone(claimed)
        events = [r["event"] for r in self.audit.read_all()]
        self.assertIn("abort_request_discarded", events)

    def test_abort_no_turn_in_flight_discarded(self):
        self._write()  # no turn nonce written
        claimed = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNone(claimed)

    def test_abort_claimed_once(self):
        self._write()
        abortmod.write_turn_nonce(self.state, "nonce")
        first = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNotNone(first)
        second = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNone(second)  # already claimed


class TurnAbortIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "repo"
        self.root.mkdir()
        self.addCleanup(self._tmp.cleanup)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        self.state = Path(self._tmp.name) / "state"
        self.service = ActivityService(self.root, state_dir=self.state)
        self.service.store.seed()
        self.plan = self.root / ".regent" / "plans" / "PLAN-005" / "PLAN.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("### STEP-01\n- **Gate:** `true`\n", encoding="utf-8")
        self.work = self.root / "work"
        self.work.mkdir()
        self.artdir = self.root / ".regent" / "plans" / "PLAN-005" / "build"
        self.artdir.mkdir(parents=True)
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("do", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "seed"], check=True)
        self.service.start("build", "PLAN-005")
        subprocess.run(["git", "-C", str(self.root), "add", ".regent/control.json"],
                       check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"], check=True)

    def test_turn_aborted_suspends_via_app_layer_releasing_lock(self):
        activity = self.service.store.load()["activity"]

        class AbortingRunner:
            def __init__(self, service, activity):
                self.service, self.activity = service, activity
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                if argv and argv[0] == "bash":
                    return SubprocessRunner().run(argv, cwd=cwd, timeout=timeout,
                                                  env=env, cancel=cancel)
                # owner issues an abort while this turn is "in flight"
                abortmod.write_abort_request(
                    self.service.state_dir, activity_id=self.activity["id"],
                    activity_epoch=self.activity["epoch"],
                    turn_token=self.activity["turn"]["token"], reason="abort now")
                for _ in range(50):
                    if cancel and cancel.is_set():
                        return RunResult(None, b"", False, aborted=True)
                    time.sleep(0.1)
                return RunResult(0, b"", False)

        result = turnmod.run_turn(
            self.root, prompt_file=self.prompt, envelope=[str(self.work)],
            gate_command="true", declared_in=self.plan, step="PLAN-005/STEP-01",
            artifact_dir=self.artdir, linkage="PLAN-005/STEP-01",
            runner=AbortingRunner(self.service, activity), service=self.service)
        self.assertEqual(result["outcome"], "ABORTED")
        control = self.service.store.load()
        self.assertEqual(control["activity"]["state"], "SUSPENDED")
        self.assertEqual(self.service.lock.status()["state"], "free")  # lock RELEASED

    def test_stop_path_also_releases_lock(self):
        self.service.stop_request(reason="stop")

        class Runner:
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                if argv and argv[0] == "bash":
                    return SubprocessRunner().run(argv, cwd=cwd, timeout=timeout,
                                                  env=env, cancel=cancel)
                return RunResult(0, b"", False)

        with self.assertRaises(turnmod.TurnError):
            turnmod.run_turn(
                self.root, prompt_file=self.prompt, envelope=[str(self.work)],
                gate_command="true", declared_in=self.plan, step="PLAN-005/STEP-01",
                artifact_dir=self.artdir, linkage="PLAN-005/STEP-01",
                runner=Runner(), service=self.service)
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")
        self.assertEqual(self.service.lock.status()["state"], "free")  # lock RELEASED


if __name__ == "__main__":
    unittest.main()
