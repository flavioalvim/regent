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
    # daemon streams one JSON line per transition, then the final object last;
    # every other command emits a single line. Parse the LAST non-empty line.
    last = text.splitlines()[-1] if text else ""
    return code, json.loads(last) if last else None


# A real fake-claude: parses the prompt for the STEP, then writes
# work/<step>.out THROUGH the confined hook (PreToolUse/PostToolUse) exactly as a
# genuine agent would — so the turn's git-anchored attribution is satisfied.
_FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys
argv = sys.argv
prompt = argv[argv.index("-p") + 1]
settings = json.loads(open(argv[argv.index("--settings") + 1]).read())
hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"].split()
m = re.search(r"STEP-\d+", prompt)
step = m.group(0) if m else "STEP-01"
target = os.path.join(os.getcwd(), "work", step + ".out")
for phase in ("PreToolUse", "PostToolUse"):
    if phase == "PostToolUse":
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "w").write("done")
    subprocess.run(hook + [phase], input=json.dumps(
        {"hook_event_name": phase, "tool_name": "Write",
         "tool_input": {"file_path": target}, "tool_use_id": step}),
        text=True, capture_output=True, env=os.environ.copy())
sys.exit(0)
'''


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

    def test_daemon_cli_streams_transitions(self):
        # per-transition JSON lines, then the final object last (advisor finding #5)
        out = io.StringIO()
        with redirect_stdout(out):
            main(["daemon", "--project", str(self.root), "run", "--once"])
        lines = [json.loads(ln) for ln in out.getvalue().splitlines() if ln.strip()]
        self.assertGreaterEqual(len(lines), 2)  # a transition line + final object
        self.assertEqual(lines[0].get("transition"), "IDLE")
        self.assertEqual(lines[-1]["final_state"], "IDLE")

    def test_e2e_arm_daemon_drives_two_steps_to_complete(self):
        # STEP-04 e2e: a REAL fake-claude, driven through the CLI end to end.
        fake = Path(self._tmp.name) / "fake-claude.py"
        fake.write_text(_FAKE_CLAUDE, encoding="utf-8")
        fake.chmod(0o755)
        code, armed = _run(self._arm_argv())
        self.assertEqual(code, 0)
        code, payload = _run(["daemon", "--project", str(self.root), "run",
                              "--once", "--claude-bin", str(fake)])
        self.assertEqual(code, 0)
        self.assertEqual(payload["final_state"], "STEPS_COMPLETE")
        self.assertEqual(payload["turns"], 2)
        # both steps really committed with their trailers
        log = subprocess.run(["git", "-C", str(self.root), "log", "--format=%B"],
                             capture_output=True, text=True).stdout
        self.assertIn("Regent-Step: PLAN-006/STEP-01", log)
        self.assertIn("Regent-Step: PLAN-006/STEP-02", log)
        # disarmed after the terminal condition
        from regent.conduction import supervisor as sup
        self.assertIsNone(sup.read_arm(self.service))
        # and the daemon did NOT conclude the activity (mediated)
        self.assertEqual(self.service.store.load()["activity"]["state"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
