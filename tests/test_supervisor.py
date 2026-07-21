"""Directed tests for rehearse + arm/disarm + daemon (PLAN-006)."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from regent.activity import ActivityService
from regent.conduction import supervisor as sup
from tests.test_loop import _fake_agent_runner


class SupervisorTest(unittest.TestCase):
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
        self.plandir = self.root / ".regent" / "plans" / "PLAN-006"
        self.artdir = self.plandir / "build"
        self.artdir.mkdir(parents=True)
        self.plan = self.plandir / "PLAN.md"
        self.plan.write_text(
            "### STEP-01\n- **Gate:** `test -f work/STEP-01.out`\n"
            "### STEP-02\n- **Gate:** `test -f work/STEP-02.out`\n", encoding="utf-8")
        (self.plandir / "APPROVAL.md").write_text("status: APPROVED\n", encoding="utf-8")
        (self.root / "work").mkdir()
        self.template = self.root / "template.txt"
        self.template.write_text("Do {step}; gate {gate}", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "seed"], check=True)
        self.service.start("build", "PLAN-006")
        subprocess.run(["git", "-C", str(self.root), "add", ".regent/control.json"],
                       check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"], check=True)

    def _config(self):
        return {"prompt_template": str(self.template),
                "envelope": [str(self.root / "work")], "gate_envelope": [],
                "declared_in": str(self.plan), "artifact_dir": str(self.artdir),
                "max_turns": 20, "timeout": 900.0}

    # -- rehearse ---------------------------------------------------------

    def test_rehearse_lists_pending_steps_and_gates(self):
        r = sup.rehearse(self.root, plan_id="PLAN-006", declared_in=self.plan)
        self.assertFalse(r["complete"])
        self.assertEqual([p["step"] for p in r["pending"]], ["STEP-01", "STEP-02"])
        self.assertEqual(r["pending"][0]["gate"], "test -f work/STEP-01.out")
        self.assertEqual(r["pending"][0]["next_attempt"], 1)

    def test_rehearse_is_read_only(self):
        before = subprocess.run(["git", "-C", str(self.root), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        sup.rehearse(self.root, plan_id="PLAN-006", declared_in=self.plan)
        after = subprocess.run(["git", "-C", str(self.root), "status", "--porcelain"],
                               capture_output=True, text=True).stdout
        self.assertEqual(before, after)

    def test_rehearse_complete_plan(self):
        empty = self.plandir / "EMPTY.md"
        empty.write_text("# no steps here\n", encoding="utf-8")
        r = sup.rehearse(self.root, plan_id="PLAN-006", declared_in=empty)
        self.assertTrue(r["complete"])
        self.assertEqual(r["pending"], [])

    # -- arm / disarm -----------------------------------------------------

    def test_arm_writes_bound_token(self):
        payload = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        self.assertEqual(payload["plan_id"], "PLAN-006")
        self.assertIn("arm_id", payload)
        read = sup.read_arm(self.service)
        self.assertEqual(read["arm_id"], payload["arm_id"])

    def test_arm_refuses_without_matching_active_build(self):
        self.service.conclude("ACCEPTED")  # no ACTIVE build now
        with self.assertRaises(sup.SupervisorError) as ctx:
            sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        self.assertEqual(ctx.exception.code, "NOT_EXECUTABLE")

    def test_arm_other_plan_is_already_armed(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        with self.assertRaises(sup.SupervisorError) as ctx:
            sup.arm(self.service, plan_id="PLAN-007", config=self._config())
        self.assertEqual(ctx.exception.code, "ALREADY_ARMED")

    def test_arm_token_stale_after_takeover_ignored(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        # rotate the token (as a takeover would) without changing the epoch
        def fn(body):
            body["activity"]["turn"]["token"] = "ff" * 16
            return body
        self.service.store.mutate(fn)
        self.assertIsNone(sup.read_arm(self.service))  # discarded

    def test_arm_token_stale_epoch_ignored(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        # a full activity cycle (conclude + restart) bumps the epoch and token;
        # the arm-token bound to the old epoch must not survive it.
        self.service.conclude("ACCEPTED")
        self.service.start("build", "PLAN-006")
        self.assertIsNone(sup.read_arm(self.service))

    def test_disarm_cas_old_id_does_not_remove_rearm(self):
        first = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        # a rearm (new arm_id) after disarming the first
        sup.disarm(self.service, arm_id=first["arm_id"])
        second = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        # the OLD daemon tries to disarm with the stale id — must NOT remove B
        r = sup.disarm(self.service, arm_id=first["arm_id"])
        self.assertFalse(r["disarmed"])
        self.assertEqual(sup.read_arm(self.service)["arm_id"], second["arm_id"])

    def test_disarm_idempotent(self):
        self.assertFalse(sup.disarm(self.service)["disarmed"])  # nothing armed

    def test_read_arm_discard_cas_keeps_rearm_under_race(self):
        # True A→B interleaving: A reads a STALE snapshot (arm_id OLD, unbound);
        # meanwhile disk holds a fresh BOUND token B. A's discard must re-read
        # under the lock and, seeing arm_id OLD != B, NOT delete B.
        fresh = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.supervisor as mod
        real_raw = mod._raw_arm
        calls = {"n": 0}
        stale = {"arm_id": "OLD", "plan_id": "PLAN-006", "activity_epoch": -1,
                 "turn_token": "00" * 16, "config": {}}

        def fake_raw(state_dir):
            calls["n"] += 1
            return stale if calls["n"] == 1 else real_raw(state_dir)
        mod._raw_arm = fake_raw
        try:
            self.assertIsNone(sup.read_arm(self.service))  # stale → None
        finally:
            mod._raw_arm = real_raw
        self.assertEqual(sup.read_arm(self.service)["arm_id"], fresh["arm_id"])  # B lives

    def test_disarm_reports_false_when_unlink_fails(self):
        # advisor finding #1 (round 2): a failed removal must NOT report success.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.supervisor as mod
        orig = mod._unlink_durable
        mod._unlink_durable = lambda p: (_ for _ in ()).throw(OSError("boom"))
        try:
            r = sup.disarm(self.service)
        finally:
            mod._unlink_durable = orig
        self.assertFalse(r["disarmed"])
        self.assertIsNotNone(sup._raw_arm(self.service.state_dir))  # still armed

    def test_read_arm_discard_no_audit_when_removal_fails(self):
        # advisor finding #2 (round 3): the audit must NOT claim discarded if the
        # removal fails.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        def fn(body):  # invalidate binding so read_arm attempts discard
            body["activity"]["turn"]["token"] = "cc" * 16
            return body
        self.service.store.mutate(fn)
        import regent.conduction.supervisor as mod
        orig = mod._unlink_durable
        mod._unlink_durable = lambda p: (_ for _ in ()).throw(OSError("boom"))
        try:
            self.assertIsNone(sup.read_arm(self.service))  # still returns None
        finally:
            mod._unlink_durable = orig
        events = [e.get("event") for e in self.service.audit.read_all()]
        self.assertNotIn("arm_token_discarded", events)  # never claimed
        self.assertIsNotNone(sup._raw_arm(self.service.state_dir))  # token kept

    def test_arm_persists_canonical_absolute_paths(self):
        # advisor finding #3 (round 2): the token stores CANONICAL absolute paths
        # so the daemon behaves the same from any CWD.
        payload = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        cfg = payload["config"]
        for key in ("prompt_template", "declared_in", "artifact_dir"):
            self.assertTrue(Path(cfg[key]).is_absolute(), key)
        self.assertTrue(all(Path(p).is_absolute() for p in cfg["envelope"]))

    # -- arm config validation (advisor finding #4) -----------------------

    def test_arm_rejects_missing_template(self):
        cfg = self._config()
        cfg["prompt_template"] = str(self.root / "nope.txt")
        with self.assertRaises(sup.SupervisorError) as ctx:
            sup.arm(self.service, plan_id="PLAN-006", config=cfg)
        self.assertEqual(ctx.exception.code, "NOT_EXECUTABLE")

    def test_arm_rejects_declared_in_outside_plan_dir(self):
        stray = self.root / "STRAY.md"
        stray.write_text("### STEP-01\n- **Gate:** `true`\n", encoding="utf-8")
        cfg = self._config()
        cfg["declared_in"] = str(stray)
        with self.assertRaises(sup.SupervisorError) as ctx:
            sup.arm(self.service, plan_id="PLAN-006", config=cfg)
        self.assertEqual(ctx.exception.code, "NOT_EXECUTABLE")

    def test_arm_rejects_plan_without_steps(self):
        empty = self.plandir / "EMPTY.md"
        empty.write_text("# no steps\n", encoding="utf-8")
        cfg = self._config()
        cfg["declared_in"] = str(empty)
        with self.assertRaises(sup.SupervisorError) as ctx:
            sup.arm(self.service, plan_id="PLAN-006", config=cfg)
        self.assertEqual(ctx.exception.code, "NOT_EXECUTABLE")

    def test_arm_token_stale_after_takeover_ignored(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        # rotate the token (as a takeover would) without changing the epoch
        def fn(body):
            body["activity"]["turn"]["token"] = "ff" * 16
            return body
        self.service.store.mutate(fn)
        self.assertIsNone(sup.read_arm(self.service))  # discarded

    def test_disarm_cas_old_id_does_not_remove_rearm(self):
        first = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        sup.disarm(self.service, arm_id=first["arm_id"])
        second = sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        # the OLD daemon tries to disarm with the stale id — must NOT remove B
        r = sup.disarm(self.service, arm_id=first["arm_id"])
        self.assertFalse(r["disarmed"])
        self.assertEqual(sup.read_arm(self.service)["arm_id"], second["arm_id"])

    # -- daemon (STEP-02) -------------------------------------------------

    def test_daemon_idle_without_arm(self):
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "IDLE")

    def test_daemon_once_single_cycle(self):
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["transitions"], ["IDLE"])  # exactly one cycle, no loop

    def test_daemon_never_acts_on_unarmed_plan(self):
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "IDLE")
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "work/"],
            capture_output=True, text=True).stdout.strip(), "")  # no turn ran

    def test_daemon_drives_armed_plan_to_complete(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "STEPS_COMPLETE")
        self.assertEqual(r["turns"], 2)

    def test_daemon_reports_steps_complete_not_accepted(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "STEPS_COMPLETE")  # NOT "ACCEPTED"
        # the daemon does NOT conclude the activity — that is mediated
        self.assertEqual(self.service.store.load()["activity"]["state"], "ACTIVE")
        self.assertFalse((self.artdir / "CONCLUSION.md").exists())

    def test_daemon_disarms_after_complete(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertIsNone(sup.read_arm(self.service))

    def test_daemon_disarms_on_halted(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        r = sup.run_daemon(self.service, once=True,
                           runner=_fake_agent_runner({"STEP-01": "noop"}))
        self.assertEqual(r["final_state"], "HALTED")
        self.assertIsNone(sup.read_arm(self.service))

    def test_daemon_disarms_on_stopped(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        self.service.stop_request(reason="owner stops")
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "STOPPED")
        self.assertIsNone(sup.read_arm(self.service))

    def test_daemon_respects_stop_request(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        self.service.stop_request(reason="owner stops")
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "STOPPED")
        # the stop was honored BEFORE any turn ran
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "work/"],
            capture_output=True, text=True).stdout.strip(), "")

    def _disarming_runner(self):
        """Wraps the fake agent so it disarms right after STEP-01's turn — the
        loop guard must then refuse to START STEP-02 (DISARMED)."""
        inner = _fake_agent_runner({})
        service = self.service

        class Runner:
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                result = inner.run(argv, cwd=cwd, timeout=timeout, env=env, cancel=cancel)
                if argv and argv[0] != "bash" and "STEP-01" in argv[argv.index("-p") + 1]:
                    sup.disarm(service)  # owner disarms mid-run
                return result
        return Runner()

    def test_daemon_guard_disarm_stops_between_turns(self):
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        r = sup.run_daemon(self.service, once=True, runner=self._disarming_runner())
        self.assertEqual(r["final_state"], "DISARMED")
        self.assertIsNone(sup.read_arm(self.service))

    def test_daemon_stops_on_disarm_between_cycles(self):
        # even with once=False, a disarm mid-run returns DISARMED and does not
        # loop back to re-arm on its own.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        r = sup.run_daemon(self.service, once=False, runner=self._disarming_runner())
        self.assertEqual(r["final_state"], "DISARMED")

    def test_daemon_refuses_to_start_when_conclusion_present(self):
        # advisor finding #2: a mediated CONCLUSION.md (committed cleanly after
        # arm — e.g. a crash between writing it and `activity conclude`) must
        # stop the daemon from STARTING any turn; the guard checks it each turn.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        (self.artdir / "CONCLUSION.md").write_text("mediated\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "conc"], check=True)
        r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        self.assertEqual(r["final_state"], "DISARMED")
        self.assertIsNone(sup.read_arm(self.service))
        # no turn ran → no work files
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "work/"],
            capture_output=True, text=True).stdout.strip(), "")

    def test_daemon_guard_revalidates_approval(self):
        # advisor finding #2 (round 2): APPROVAL revoked in the window between the
        # loop's top check and the launch must stop the turn via the guard.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.loop as lm
        import regent.conduction.supervisor as sm
        calls = {"n": 0}

        def fake_status(root, plan):
            calls["n"] += 1
            return "APPROVED" if calls["n"] == 1 else "CANCELLED"
        lm_orig, sm_orig = lm._approval_status, sm._approval_status
        lm._approval_status = fake_status
        sm._approval_status = fake_status
        try:
            r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        finally:
            lm._approval_status, sm._approval_status = lm_orig, sm_orig
        self.assertEqual(r["final_state"], "DISARMED")
        self.assertIsNone(sup.read_arm(self.service))

    def test_daemon_streaming_exception_disarms(self):
        # advisor finding #4 (round 2): a broken on_state sink must not escape
        # the daemon un-disarmed.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())

        def boom(state, extra):
            if state == "RUNNING":
                raise BrokenPipeError("sink gone")
        r = sup.run_daemon(self.service, once=True,
                           runner=_fake_agent_runner({}), on_state=boom)
        self.assertEqual(r["final_state"], "DISARMED")
        self.assertIsNone(sup.read_arm(self.service))

    def test_daemon_reports_disarm_failed_when_removal_persists_failing(self):
        # advisor finding #1 (round 3): a terminal that cannot remove the token
        # must report DISARM_FAILED (still armed), never a clean terminal.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.supervisor as mod
        orig = mod._unlink_durable
        mod._unlink_durable = lambda p: (_ for _ in ()).throw(OSError("boom"))
        try:
            r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        finally:
            mod._unlink_durable = orig
        self.assertEqual(r["final_state"], "DISARM_FAILED")
        self.assertFalse(r["ok"])
        self.assertIsNotNone(sup._raw_arm(self.service.state_dir))  # still armed

    def test_daemon_disarm_failed_when_dir_fsync_persistently_fails(self):
        # advisor finding #1 (round 4): a dir-fsync failure (file already unlinked)
        # must NOT be masked as benign "no arm token" — removal isn't durable, so
        # the terminal is DISARM_FAILED.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.supervisor as mod
        orig = mod._fsync_dir
        mod._fsync_dir = lambda p: (_ for _ in ()).throw(OSError("fsync"))
        try:
            r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        finally:
            mod._fsync_dir = orig
        self.assertEqual(r["final_state"], "DISARM_FAILED")

    def test_daemon_recovers_when_dir_fsync_succeeds_on_retry(self):
        # a TRANSIENT fsync failure: attempt 1 unlinks but fsync fails; the retry
        # re-runs the durability barrier and, on success, confirms removal.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.supervisor as mod
        orig = mod._fsync_dir
        calls = {"n": 0}

        def flaky(p):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("transient")
            return orig(p)
        mod._fsync_dir = flaky
        try:
            r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        finally:
            mod._fsync_dir = orig
        self.assertEqual(r["final_state"], "STEPS_COMPLETE")
        self.assertIsNone(sup._raw_arm(self.service.state_dir))  # durably gone

    def test_daemon_disarms_on_unexpected_failure(self):
        # advisor finding #4: a non-LoopError escaping run_loop must still disarm.
        sup.arm(self.service, plan_id="PLAN-006", config=self._config())
        import regent.conduction.supervisor as mod
        orig = mod.run_loop
        mod.run_loop = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            r = sup.run_daemon(self.service, once=True, runner=_fake_agent_runner({}))
        finally:
            mod.run_loop = orig
        self.assertEqual(r["final_state"], "FAILED")
        self.assertIsNone(sup.read_arm(self.service))


if __name__ == "__main__":
    unittest.main()
