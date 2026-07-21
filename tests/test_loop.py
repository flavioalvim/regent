"""Directed tests for the turn loop driver (PLAN-005 STEP-02)."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from regent.activity import ActivityService
from regent.conduction import loop as loopmod
from regent.conduction.process import RunResult


def _fake_agent_runner(writes_per_step):
    """A runner that, per turn, writes work/<step>.out via the real hook, or
    escapes/does nothing to force non-OK outcomes. writes_per_step: dict
    step_name -> "ok"|"escape"|"noop"|"red"."""
    from regent.conduction.process import SubprocessRunner
    real = SubprocessRunner()

    class Runner:
        def run(self, argv, *, cwd, timeout, env=None, cancel=None):
            if argv and argv[0] == "bash":
                return real.run(argv, cwd=cwd, timeout=timeout, env=env, cancel=cancel)
            # infer the current step from the prompt file content in argv
            prompt = argv[argv.index("-p") + 1]
            import re
            m = re.search(r"STEP-\d+", prompt)
            step = m.group(0) if m else "STEP-01"
            mode = writes_per_step.get(step, "ok")
            if mode == "escape":
                (Path(cwd) / "escaped.txt").write_text("x", encoding="utf-8")
                return RunResult(0, b"", False)
            if mode == "noop":
                return RunResult(0, b"", False)
            # ok: write inside the envelope via the real hook
            settings = json.loads(Path(argv[argv.index("--settings") + 1]).read_text())
            hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"].split()
            he = dict(os.environ, **(env or {}))
            target = str(Path(cwd) / "work" / f"{step}.out")
            for phase in ("PreToolUse", "PostToolUse"):
                if phase == "PostToolUse":
                    Path(target).parent.mkdir(parents=True, exist_ok=True)
                    Path(target).write_text("done", encoding="utf-8")
                subprocess.run(hook + [phase], input=json.dumps(
                    {"hook_event_name": phase, "tool_name": "Write",
                     "tool_input": {"file_path": target}, "tool_use_id": step}),
                    text=True, capture_output=True, env=he)
            return RunResult(0, b"", False)
    return Runner()


class LoopTest(unittest.TestCase):
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
        self.plandir = self.root / ".regent" / "plans" / "PLAN-005"
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
        self.service.start("build", "PLAN-005")
        subprocess.run(["git", "-C", str(self.root), "add", ".regent/control.json"],
                       check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"], check=True)

    def _loop(self, runner, **kw):
        return loopmod.run_loop(
            self.root, plan_id="PLAN-005", prompt_template=self.template,
            envelope=[str(self.root / "work")], gate_envelope=[],
            declared_in=self.plan, artifact_dir=self.artdir, runner=runner,
            service=self.service, **kw)

    def test_loop_runs_all_steps_to_complete(self):
        result = self._loop(_fake_agent_runner({}))
        self.assertEqual(result["stop_condition"], "COMPLETE", result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        self.assertEqual([t["outcome"] for t in result["turns"]], ["TURN_OK", "TURN_OK"])

    def test_loop_current_step_needs_committed_trailer(self):
        # A STEP file present but NOT committed with the trailer must not advance.
        (self.artdir / "STEP-01.md").write_text("forged", encoding="utf-8")
        # loop should still target STEP-01 (not treat it as done)
        result = self._loop(_fake_agent_runner({}))
        self.assertEqual(result["turns"][0]["step"], "STEP-01")

    def test_loop_halts_on_violation(self):
        result = self._loop(_fake_agent_runner({"STEP-01": "escape"}))
        self.assertEqual(result["stop_condition"], "HALTED")
        self.assertEqual(result["turns"][0]["outcome"], "TURN_VIOLATION")

    def test_loop_halts_on_gate_red(self):
        # STEP-01 does nothing → the gate `test -f work/STEP-01.out` fails RED
        result = self._loop(_fake_agent_runner({"STEP-01": "noop"}))
        self.assertEqual(result["stop_condition"], "HALTED")
        self.assertEqual(result["turns"][0]["outcome"], "GATE_RED")

    def test_loop_respects_max_turns(self):
        # noop steps never advance; cap stops the loop
        result = self._loop(_fake_agent_runner({"STEP-01": "noop"}), max_turns=1)
        self.assertIn(result["stop_condition"], ("HALTED", "MAX_TURNS"))
        self.assertLessEqual(result["count"], 1)

    def test_loop_retry_after_halt_new_attempt(self):
        self._loop(_fake_agent_runner({"STEP-01": "noop"}))  # attempt 1 halts
        # a fresh loop run retries STEP-01 as attempt 2 (no EvidenceConflict)
        result = self._loop(_fake_agent_runner({}))
        self.assertEqual(result["turns"][0]["attempt"], 2)
        self.assertEqual(result["stop_condition"], "COMPLETE")

    def test_loop_revalidates_approval_each_turn(self):
        (self.plandir / "APPROVAL.md").write_text("status: CANCELLED\n", encoding="utf-8")
        result = self._loop(_fake_agent_runner({}))
        self.assertEqual(result["stop_condition"], "PLAN_NOT_EXECUTABLE")

    def test_loop_lock_excludes_second_run(self):
        from regent.protocol.control import _FlockMutex
        held = _FlockMutex(self.state / "loop.lock", timeout=0.2)
        held.__enter__()
        try:
            with self.assertRaises(loopmod.LoopError) as ctx:
                self._loop(_fake_agent_runner({}))
            self.assertEqual(ctx.exception.code, "LOOP_BUSY")
        finally:
            held.__exit__(None, None, None)

    def test_loop_completes_evidence_committed(self):
        self._loop(_fake_agent_runner({}))
        loops = list(self.artdir.glob("LOOP-*.md"))
        self.assertTrue(loops)
        log = _git = subprocess.run(
            ["git", "-C", str(self.root), "log", "-1", "--format=%B"],
            capture_output=True, text=True).stdout
        self.assertIn("Regent-Loop: COMPLETE", log)


if __name__ == "__main__":
    unittest.main()
