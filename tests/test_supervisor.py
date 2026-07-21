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


if __name__ == "__main__":
    unittest.main()
