"""Directed tests for the loop CLI contract (PLAN-005 STEP-03)."""

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from regent.cli import main
from tests.test_loop import _fake_agent_runner  # reuse the fake agent


def _run(argv):
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(argv)
    text = out.getvalue().strip()
    return code, json.loads(text) if text else None


class LoopCliTest(unittest.TestCase):
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
        self.plandir = self.root / ".regent" / "plans" / "PLAN-005"
        self.artdir = self.plandir / "build"
        self.artdir.mkdir(parents=True)
        (self.plandir / "PLAN.md").write_text(
            "### STEP-01\n- **Gate:** `test -f work/STEP-01.out`\n", encoding="utf-8")
        (self.plandir / "APPROVAL.md").write_text("status: APPROVED\n", encoding="utf-8")
        (self.root / "work").mkdir()
        self.template = self.root / "t.txt"
        self.template.write_text("Do {step}", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "seed"], check=True)
        self.service.start("build", "PLAN-005")
        subprocess.run(["git", "-C", str(self.root), "add", ".regent/control.json"],
                       check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"], check=True)

    def test_loop_abort_cli(self):
        code, payload = _run(["loop", "--project", str(self.root), "abort",
                              "--reason", "stop the loop"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertIn("abort_id", payload)
        # a second abort while one is pending is rejected
        code, payload = _run(["loop", "--project", str(self.root), "abort",
                              "--reason", "again"])
        self.assertEqual(code, 3)
        self.assertEqual(payload["error"], "ABORT_PENDING")

    def test_loop_run_halted_exit_code(self):
        # patch the runner path is not exposed via CLI, so drive run_loop directly
        # to a HALTED via a red gate (noop agent), then check CLI maps exit codes
        # by invoking the CLI with a real claude-bin that does nothing.
        fake = Path(self._tmp.name) / "noop-claude"
        fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        code, payload = _run(["loop", "--project", str(self.root), "run",
                              "--plan", "PLAN-005", "--prompt-template",
                              str(self.template), "--envelope", str(self.root / "work"),
                              "--declared-in", str(self.plandir / "PLAN.md"),
                              "--artifact-dir", str(self.artdir),
                              "--claude-bin", str(fake)])
        self.assertEqual(code, 3)  # gate red → LOOP_HALTED
        self.assertEqual(payload["error"], "LOOP_HALTED")
        self.assertEqual(payload["detail"]["stop_condition"], "HALTED")


if __name__ == "__main__":
    unittest.main()
