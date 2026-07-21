"""Directed tests for the rehearse/arm/disarm/daemon CLI (PLAN-006 STEP-03)."""

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from regent.cli import main


def _run(argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    text = out.getvalue().strip()
    return code, json.loads(text) if text else None


class SupervisorCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.root = base / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(os.environ.pop, "XDG_STATE_HOME", None)
        from regent.activity import ActivityService
        self.service = ActivityService(self.root)
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
        self.template = self.root / "t.txt"
        self.template.write_text("Do {step}", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "seed"], check=True)
        self.service.start("build", "PLAN-006")
        subprocess.run(["git", "-C", str(self.root), "add", ".regent/control.json"],
                       check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"], check=True)

    def _arm_argv(self):
        return ["arm", "--project", str(self.root), "--plan", "PLAN-006",
                "--prompt-template", str(self.template),
                "--envelope", str(self.root / "work"),
                "--declared-in", str(self.plan), "--artifact-dir", str(self.artdir)]

    def test_rehearse_cli_json(self):
        code, payload = _run(["rehearse", "--project", str(self.root),
                              "--plan", "PLAN-006", "--declared-in", str(self.plan)])
        self.assertEqual(code, 0)
        self.assertFalse(payload["complete"])
        self.assertEqual([p["step"] for p in payload["pending"]],
                         ["STEP-01", "STEP-02"])

    def test_arm_disarm_cli(self):
        code, armed = _run(self._arm_argv())
        self.assertEqual(code, 0)
        self.assertTrue(armed["ok"])
        arm_id = armed["arm_id"]
        code, dis = _run(["disarm", "--project", str(self.root), "--arm-id", arm_id])
        self.assertEqual(code, 0)
        self.assertTrue(dis["disarmed"])

    def test_arm_other_plan_already_armed_exit_code(self):
        _run(self._arm_argv())
        argv = self._arm_argv()
        argv[argv.index("PLAN-006")] = "PLAN-007"  # the --plan value
        code, payload = _run(argv)
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "ALREADY_ARMED")

    def test_daemon_run_cli_once(self):
        # nothing armed → IDLE, exit 0, no agent launched
        code, payload = _run(["daemon", "--project", str(self.root), "run", "--once"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["final_state"], "IDLE")

    def test_daemon_exit_codes(self):
        # armed + stop-request → STOPPED before any turn; exit 2, no claude spawned
        _run(self._arm_argv())
        self.service.stop_request(reason="owner stops")
        code, payload = _run(["daemon", "--project", str(self.root), "run", "--once"])
        self.assertEqual(code, 2)
        self.assertEqual(payload["final_state"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
