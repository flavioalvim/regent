"""Directed tests for cancellable runner + abort-request (PLAN-005 STEP-01)."""

import json
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
        abortmod.write_turn_nonce(self.state, "nonce")
        self._write(activity_epoch=99)  # wrong epoch
        claimed = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNone(claimed)
        events = [r["event"] for r in self.audit.read_all()]
        self.assertIn("abort_request_discarded", events)

    def test_abort_no_turn_in_flight_discarded(self):
        self._write()  # no turn nonce written (turn_nonce=None)
        claimed = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNone(claimed)

    def test_abort_bound_to_specific_turn_nonce(self):
        # An abort captured against turn A's nonce is NOT honored for turn B.
        abortmod.write_turn_nonce(self.state, "nonceA")
        self._write()  # binds turn_nonce=nonceA
        abortmod.clear_turn_nonce(self.state)
        abortmod.write_turn_nonce(self.state, "nonceB")  # a new turn
        claimed = abortmod.claim_matching_abort(
            self.state, self.audit, activity_id="PLAN-005", activity_epoch=4,
            turn_token="ab" * 16)
        self.assertIsNone(claimed)  # A's abort never kills B

    def test_abort_claimed_once(self):
        abortmod.write_turn_nonce(self.state, "nonce")  # turn in flight FIRST
        self._write()
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

    def test_recover_turn_reconciles_suspended_abort(self):
        # Simulate a crashed abort: claimed marker present + activity ACTIVE.
        activity = self.service.store.load()["activity"]
        claimed = self.service.state_dir / f"abort.claimed-{'a'*8}"
        import json as _json
        claimed.write_text(_json.dumps(
            {"id": "a" * 8, "activity_id": activity["id"],
             "activity_epoch": activity["epoch"],
             "turn_token": activity["turn"]["token"]}), encoding="utf-8")
        rec = turnmod.recover_turn(self.root, linkage="PLAN-005/STEP-01",
                                   step="PLAN-005/STEP-01", service=self.service)
        self.assertEqual(rec["state"], "ABORT_RECONCILED")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")
        self.assertEqual(self.service.lock.status()["state"], "free")
        self.assertFalse(list(self.service.state_dir.glob("abort.claimed-*")))

    def test_recover_claimed_takes_precedence_over_trailer(self):
        # Simulate crash after the ABORTED op-commit (trailer present) but before
        # suspend: .claimed still present + activity ACTIVE → recover suspends,
        # NOT COMMITTED.
        activity = self.service.store.load()["activity"]
        subprocess.run(["git", "-C", str(self.root), "commit", "--allow-empty",
                        "-qm", "x\n\nRegent-Turn: PLAN-005/STEP-01/try1"], check=True)
        claimed = self.service.state_dir / "abort.claimed-c1"
        import json as _json
        claimed.write_text(_json.dumps(
            {"id": "c1", "activity_id": activity["id"],
             "activity_epoch": activity["epoch"],
             "turn_token": activity["turn"]["token"]}), encoding="utf-8")
        rec = turnmod.recover_turn(self.root, linkage="PLAN-005/STEP-01/try1",
                                   step="PLAN-005/STEP-01", service=self.service)
        self.assertEqual(rec["state"], "ABORT_RECONCILED")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")

    def test_recover_reconciles_suspended_via_owning_turn(self):
        # After suspend, the token lives in suspension.owning_turn (turn=null).
        token = self.service.store.load()["activity"]["turn"]["token"]
        self.service.suspend(checkpoint="turn:LAUNCHED", reason="aborted")
        claimed = self.service.state_dir / "abort.claimed-c2"
        import json as _json
        claimed.write_text(_json.dumps(
            {"id": "c2", "activity_id": "PLAN-005", "activity_epoch":
             self.service.store.load()["activity"]["epoch"], "turn_token": token}),
            encoding="utf-8")
        rec = turnmod.recover_turn(self.root, linkage="PLAN-005/STEP-01",
                                   step="PLAN-005/STEP-01", service=self.service)
        self.assertEqual(rec["state"], "ABORT_RECONCILED")  # bound via owning_turn
        self.assertFalse(list(self.service.state_dir.glob("abort.claimed-*")))

    def test_recover_turn_unbound_marker_left_for_mediator(self):
        claimed = self.service.state_dir / f"abort.claimed-{'b'*8}"
        import json as _json
        claimed.write_text(_json.dumps(
            {"id": "b" * 8, "activity_id": "PLAN-OTHER", "activity_epoch": 99}),
            encoding="utf-8")
        rec = turnmod.recover_turn(self.root, linkage="PLAN-005/STEP-01",
                                   step="PLAN-005/STEP-01", service=self.service)
        self.assertEqual(rec["state"], "ABORT_MARKER_UNBOUND")
        self.assertTrue(list(self.service.state_dir.glob("abort.claimed-*")))  # kept

    def test_abort_during_gate_is_honored(self):
        activity = self.service.store.load()["activity"]
        state_dir = self.service.state_dir
        act = activity

        class AbortDuringGateRunner:
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                if argv and argv[0] == "bash":
                    # the gate: issue the abort now, then honor cancel like the
                    # cancellable runner would (killed → aborted).
                    abortmod.write_abort_request(
                        state_dir, activity_id=act["id"],
                        activity_epoch=act["epoch"],
                        turn_token=act["turn"]["token"], reason="abort in gate")
                    for _ in range(300):  # up to 30s; keepalive ticks each ~1s
                        if cancel and cancel.is_set():
                            return RunResult(None, b"", False, aborted=True)
                        time.sleep(0.1)
                    return RunResult(0, b"gate ok", False)
                # agent writes inside the envelope so the turn would otherwise pass
                settings = json.loads(Path(argv[argv.index("--settings")+1]).read_text())
                hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"].split()
                he = dict(os.environ, **(env or {}))
                t = str(Path(cwd) / "work" / "out.txt")
                for ph in ("PreToolUse", "PostToolUse"):
                    if ph == "PostToolUse":
                        Path(t).parent.mkdir(parents=True, exist_ok=True)
                        Path(t).write_text("x", encoding="utf-8")
                    subprocess.run(hook + [ph], input=json.dumps(
                        {"hook_event_name": ph, "tool_name": "Write",
                         "tool_input": {"file_path": t}, "tool_use_id": "g0"}),
                        text=True, capture_output=True, env=he)
                return RunResult(0, b"", False)

        self.plan.write_text("### STEP-01\n- **Gate:** `test -f work/out.txt`\n",
                             encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "gate"], check=True)
        result = turnmod.run_turn(
            self.root, prompt_file=self.prompt, envelope=[str(self.work)],
            gate_command="test -f work/out.txt", declared_in=self.plan,
            step="PLAN-005/STEP-01", artifact_dir=self.artdir,
            linkage="PLAN-005/STEP-01", runner=AbortDuringGateRunner(),
            service=self.service)
        self.assertEqual(result["outcome"], "ABORTED")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")
        self.assertEqual(self.service.lock.status()["state"], "free")
        self.assertFalse(list(self.service.state_dir.glob("abort.claimed-*")))

    def test_abort_after_gate_during_verify_is_honored(self):
        # Inject the abort so it is only visible at the FINAL cancel check
        # (after the gate boundary), simulating a claim during verify/evidence.
        activity = self.service.store.load()["activity"]
        state_dir = self.service.state_dir

        class LateAbortRunner:
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                if argv and argv[0] == "bash":
                    r = SubprocessRunner().run(argv, cwd=cwd, timeout=timeout,
                                               env=env, cancel=cancel)
                    # after the gate finished, set cancel directly (as the
                    # keepalive would, having claimed an abort during verify)
                    if cancel is not None:
                        cancel.set()
                    return r
                settings = json.loads(Path(argv[argv.index("--settings")+1]).read_text())
                hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"].split()
                he = dict(os.environ, **(env or {}))
                t = str(Path(cwd) / "work" / "out.txt")
                for ph in ("PreToolUse", "PostToolUse"):
                    if ph == "PostToolUse":
                        Path(t).parent.mkdir(parents=True, exist_ok=True)
                        Path(t).write_text("x", encoding="utf-8")
                    subprocess.run(hook + [ph], input=json.dumps(
                        {"hook_event_name": ph, "tool_name": "Write",
                         "tool_input": {"file_path": t}, "tool_use_id": "v0"}),
                        text=True, capture_output=True, env=he)
                return RunResult(0, b"", False)

        # a matching claimed marker must exist for the ABORTED suspend/clear path
        (state_dir / "turn.nonce").write_text("n", encoding="utf-8")
        (state_dir / "abort.claimed-v1").write_text(json.dumps(
            {"id": "v1", "activity_id": activity["id"],
             "activity_epoch": activity["epoch"],
             "turn_token": activity["turn"]["token"]}), encoding="utf-8")
        self.plan.write_text("### STEP-01\n- **Gate:** `test -f work/out.txt`\n",
                             encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "g"], check=True)
        result = turnmod.run_turn(
            self.root, prompt_file=self.prompt, envelope=[str(self.work)],
            gate_command="test -f work/out.txt", declared_in=self.plan,
            step="PLAN-005/STEP-01", artifact_dir=self.artdir,
            linkage="PLAN-005/STEP-01", runner=LateAbortRunner(), service=self.service)
        self.assertEqual(result["outcome"], "ABORTED")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "work/out.txt"],
            capture_output=True, text=True).stdout.strip(), "")  # STEP not committed

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
