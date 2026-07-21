"""Directed tests for regent turn run (PLAN-004 STEP-03).

fake-claude simulates the agent: it reads the private settings, then invokes
the REAL hook with real Pre/PostToolUse payloads for each write it attempts —
exercising the true confinement + attribution pipeline end to end."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from regent.activity import ActivityService
from regent.conduction import turn as turnmod
from regent.conduction.process import RunResult


def _fake_claude_runner(writes):
    """Returns a runner that, on launch, performs `writes` [(relpath, content,
    allowed_bool)] by invoking the real hook exactly as Claude Code would."""
    from regent.conduction.process import SubprocessRunner
    real = SubprocessRunner()

    class Runner:
        def run(self, argv, *, cwd, timeout, env=None):
            if argv and argv[0] == "bash":  # the gate: run it for real
                return real.run(argv, cwd=cwd, timeout=timeout, env=env)
            settings = json.loads(Path(argv[argv.index("--settings") + 1])
                                  .read_text())
            hook_cmd = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
            hook_env = dict(os.environ, **(env or {}))
            for i, (relpath, content, _allowed) in enumerate(writes):
                target = str(Path(cwd) / relpath)
                pre = {"hook_event_name": "PreToolUse", "tool_name": "Write",
                       "tool_input": {"file_path": target}, "tool_use_id": f"t{i}"}
                out = subprocess.run(hook_cmd.split() + ["PreToolUse"],
                                     input=json.dumps(pre), text=True,
                                     capture_output=True, env=hook_env)
                decision = "allow"
                if out.stdout.strip():
                    decision = json.loads(out.stdout).get("hookSpecificOutput", {}) \
                        .get("permissionDecision", "allow")
                if decision == "deny":
                    continue  # confined: the write does not happen
                Path(target).parent.mkdir(parents=True, exist_ok=True)
                Path(target).write_text(content, encoding="utf-8")
                post = {"hook_event_name": "PostToolUse", "tool_name": "Write",
                        "tool_input": {"file_path": target}, "tool_use_id": f"t{i}"}
                subprocess.run(hook_cmd.split() + ["PostToolUse"],
                               input=json.dumps(post), text=True,
                               capture_output=True, env=hook_env)
            return RunResult(0, b"fake claude done", False)
    return Runner()


class TurnTest(unittest.TestCase):
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
        # plan with the current step + its declared gate
        self.plan = self.root / ".regent" / "plans" / "PLAN-004" / "PLAN.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text("### STEP-09\n- **Gate:** `echo turn-gate-ok`\n",
                             encoding="utf-8")
        self.work = self.root / "work"
        self.work.mkdir()
        self.artdir = self.root / ".regent" / "plans" / "PLAN-004" / "build"
        self.artdir.mkdir(parents=True)
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("write work/out.txt", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "seed"],
                       check=True)

    def _start_build(self):
        self.service.start("build", "PLAN-004")
        subprocess.run(["git", "-C", str(self.root), "add", ".regent/control.json"],
                       check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"],
                       check=True)

    def _run(self, runner, **kw):
        return turnmod.run_turn(
            self.root, prompt_file=self.prompt, envelope=[str(self.work)],
            gate_command="echo turn-gate-ok", declared_in=self.plan,
            step="PLAN-004/STEP-09", artifact_dir=self.artdir,
            linkage="PLAN-004/STEP-09", runner=runner, service=self.service, **kw)

    def test_turn_ok_commits_attributed_set_with_trailers(self):
        self._start_build()
        result = self._run(_fake_claude_runner([("work/out.txt", "hi", True)]))
        self.assertEqual(result["outcome"], "TURN_OK", result)
        self.assertTrue(result["ok"])
        self.assertIn("work/out.txt", result["files_committed"])
        msg = subprocess.run(["git", "-C", str(self.root), "log", "-1", "--format=%B"],
                             capture_output=True, text=True).stdout
        self.assertIn("Regent-Step: PLAN-004/STEP-09", msg)
        self.assertIn("Regent-Turn: PLAN-004/STEP-09", msg)
        self.assertTrue((self.artdir / "STEP-09.md").exists())

    def test_turn_violation_when_agent_escapes_envelope(self):
        self._start_build()
        # fake agent writes DIRECTLY outside the envelope, bypassing the hook
        class EscapingRunner:
            def __init__(self, root):
                self.root = root
            def run(self, argv, *, cwd, timeout, env=None):
                (Path(cwd) / "escaped.txt").write_text("pwned", encoding="utf-8")
                from regent.conduction.turnlog import append_terminal_seal
                # note: no post event for this file → attribution violation
                return RunResult(0, b"", False)
        result = self._run(EscapingRunner(self.root))
        self.assertEqual(result["outcome"], "TURN_VIOLATION")
        self.assertFalse(result["ok"])
        # no product commit: escaped file is NOT committed
        tracked = subprocess.run(["git", "-C", str(self.root), "ls-files", "escaped.txt"],
                                 capture_output=True, text=True).stdout
        self.assertEqual(tracked.strip(), "")

    def test_requires_active_build_activity(self):
        with self.assertRaises(turnmod.TurnError) as ctx:
            self._run(_fake_claude_runner([]))
        self.assertEqual(ctx.exception.code, "NOT_ACTIVE")

    def test_step_must_belong_to_declared_plan(self):
        self._start_build()
        with self.assertRaises(turnmod.TurnError) as ctx:
            turnmod.run_turn(
                self.root, prompt_file=self.prompt, envelope=[str(self.work)],
                gate_command="echo turn-gate-ok", declared_in=self.plan,
                step="PLAN-004/STEP-99", artifact_dir=self.artdir,
                linkage="x", runner=_fake_claude_runner([]), service=self.service)
        self.assertEqual(ctx.exception.code, "STEP_MISMATCH")

    def test_artifact_dir_must_be_under_regent(self):
        self._start_build()
        with self.assertRaises(turnmod.TurnError) as ctx:
            turnmod.run_turn(
                self.root, prompt_file=self.prompt, envelope=[str(self.work)],
                gate_command="echo turn-gate-ok", declared_in=self.plan,
                step="PLAN-004/STEP-09", artifact_dir=self.root / "outside",
                linkage="x", runner=_fake_claude_runner([]), service=self.service)
        self.assertEqual(ctx.exception.code, "ARTIFACT_OUTSIDE_REGENT")

    def test_gate_red_no_product_commit(self):
        self._start_build()
        self.plan.write_text("### STEP-09\n- **Gate:** `exit 1`\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "red gate"],
                       check=True)
        result = turnmod.run_turn(
            self.root, prompt_file=self.prompt, envelope=[str(self.work)],
            gate_command="exit 1", declared_in=self.plan, step="PLAN-004/STEP-09",
            artifact_dir=self.artdir, linkage="PLAN-004/STEP-09",
            runner=_fake_claude_runner([("work/out.txt", "hi", True)]),
            service=self.service)
        self.assertEqual(result["outcome"], "GATE_RED")
        self.assertFalse((self.artdir / "STEP-09.md").exists())  # no step file
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "work/out.txt"],
            capture_output=True, text=True).stdout.strip(), "")  # not committed

    def test_step_already_done_refused(self):
        self._start_build()
        (self.artdir / "STEP-09.md").write_text("done", encoding="utf-8")
        with self.assertRaises(turnmod.TurnError) as ctx:
            self._run(_fake_claude_runner([]))
        self.assertEqual(ctx.exception.code, "STEP_ALREADY_DONE")


if __name__ == "__main__":
    unittest.main()
