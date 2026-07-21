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
        def run(self, argv, *, cwd, timeout, env=None, cancel=None):
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
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
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

    def test_artifact_dir_must_be_canonical_build(self):
        self._start_build()
        # a DIFFERENT dir under .regent must NOT be accepted (bypass closed)
        alt = self.root / ".regent" / "elsewhere"
        alt.mkdir(parents=True)
        with self.assertRaises(turnmod.TurnError) as ctx:
            turnmod.run_turn(
                self.root, prompt_file=self.prompt, envelope=[str(self.work)],
                gate_command="echo turn-gate-ok", declared_in=self.plan,
                step="PLAN-004/STEP-09", artifact_dir=alt,
                linkage="x", runner=_fake_claude_runner([]), service=self.service)
        self.assertEqual(ctx.exception.code, "ARTIFACT_OUTSIDE_REGENT")

    def test_build_symlink_escape_refused(self):
        import os
        self._start_build()
        # replace the build dir with a symlink pointing outside the repo
        outside = Path(self._tmp.name) / "evil-build"
        outside.mkdir()
        import shutil
        shutil.rmtree(self.artdir)
        os.symlink(outside, self.artdir)
        with self.assertRaises(turnmod.TurnError) as ctx:
            self._run(_fake_claude_runner([("work/out.txt", "hi", True)]))
        self.assertEqual(ctx.exception.code, "ARTIFACT_OUTSIDE_REGENT")

    def test_agent_precreated_gate_evidence_is_violation(self):
        self._start_build()
        class PoisonRunner:
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                # agent writes the supervisor's gate evidence path itself
                gate = Path(cwd) / ".regent/plans/PLAN-004/build/GATE-STEP-09.md"
                gate.parent.mkdir(parents=True, exist_ok=True)
                gate.write_text("forged gate evidence", encoding="utf-8")
                return RunResult(0, b"", False)
        result = self._run(PoisonRunner())
        self.assertEqual(result["outcome"], "TURN_VIOLATION")
        self.assertFalse(result["ok"])
        # the forged gate file is NOT committed
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files",
             ".regent/plans/PLAN-004/build/GATE-STEP-09.md"],
            capture_output=True, text=True).stdout.strip(), "")

    def test_stop_during_turn_suspends_activity(self):
        self._start_build()
        self.service.stop_request(reason="owner stops mid-turn")
        with self.assertRaises(turnmod.TurnError) as ctx:
            self._run(_fake_claude_runner([("work/out.txt", "hi", True)]))
        self.assertEqual(ctx.exception.code, "STOPPED")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")

    def _stop_only_at_call(self, n):
        """Wrap the service so stop_check returns True only on its Nth call —
        lets a test place the stop AFTER the phase boundaries, at pre-commit."""
        real = self.service.stop_check
        state = {"i": 0}
        def wrapped():
            state["i"] += 1
            if state["i"] >= n:
                return {"stop_requested": True, "request": {"reason": "late"}}
            return {"stop_requested": False, "request": None}
        self.service.stop_check = wrapped
        return real

    def test_stop_at_pre_commit_suspends_turn_ok_no_commit(self):
        # A stop visible only at the pre-commit boundary (after COMPOSED/LAUNCHED/
        # GATED) must suspend a TURN_OK instead of committing the product.
        self._start_build()
        self._stop_only_at_call(4)  # 1=COMPOSED 2=LAUNCHED 3=GATED 4=pre-commit
        with self.assertRaises(turnmod.TurnError) as ctx:
            self._run(_fake_claude_runner([("work/out.txt", "hi", True)]))
        self.assertEqual(ctx.exception.code, "STOPPED")
        self.assertEqual(ctx.exception.detail["phase"], "PRE_COMMIT")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "work/out.txt"],
            capture_output=True, text=True).stdout.strip(), "")

    def test_stop_at_pre_commit_suspends_gate_red_no_operational_commit(self):
        # Even a non-TURN_OK (GATE_RED) suspends at pre-commit; no operational
        # evidence commit while a stop is pending.
        self._start_build()
        self.plan.write_text("### STEP-09\n- **Gate:** `exit 1`\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "red"], check=True)
        head_before = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                     capture_output=True, text=True).stdout.strip()
        self._stop_only_at_call(4)
        with self.assertRaises(turnmod.TurnError) as ctx:
            turnmod.run_turn(
                self.root, prompt_file=self.prompt, envelope=[str(self.work)],
                gate_command="exit 1", declared_in=self.plan, step="PLAN-004/STEP-09",
                artifact_dir=self.artdir, linkage="PLAN-004/STEP-09",
                runner=_fake_claude_runner([("work/out.txt", "hi", True)]),
                service=self.service)
        self.assertEqual(ctx.exception.code, "STOPPED")
        self.assertEqual(self.service.store.load()["activity"]["state"], "SUSPENDED")
        head_after = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                    capture_output=True, text=True).stdout.strip()
        self.assertEqual(head_before, head_after)  # no operational commit

    def test_recover_turn_reports_committed_step_and_partial(self):
        self._start_build()
        r = self._run(_fake_claude_runner([("work/out.txt", "hi", True)]))
        self.assertEqual(r["outcome"], "TURN_OK")
        rec = turnmod.recover_turn(self.root, linkage="PLAN-004/STEP-09",
                                   step="PLAN-004/STEP-09", service=self.service)
        self.assertEqual(rec["state"], "COMMITTED")
        rec2 = turnmod.recover_turn(self.root, linkage="NOPE",
                                    step="PLAN-004/STEP-09", service=self.service)
        self.assertEqual(rec2["state"], "STEP_DONE")  # STEP file present

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

    def test_done_step_is_not_current(self):
        # A step with its STEP-NN.md present is no longer the current step;
        # asking to run it is refused (current-step computation).
        self._start_build()
        (self.artdir / "STEP-09.md").write_text("done", encoding="utf-8")
        with self.assertRaises(turnmod.TurnError) as ctx:
            self._run(_fake_claude_runner([]))
        self.assertEqual(ctx.exception.code, "STEP_MISMATCH")

    def test_gate_must_be_the_declared_step_gate(self):
        self._start_build()
        with self.assertRaises(turnmod.TurnError) as ctx:
            turnmod.run_turn(
                self.root, prompt_file=self.prompt, envelope=[str(self.work)],
                gate_command="echo something-else", declared_in=self.plan,
                step="PLAN-004/STEP-09", artifact_dir=self.artdir,
                linkage="x", runner=_fake_claude_runner([]), service=self.service)
        self.assertEqual(ctx.exception.code, "PROVENANCE")

    def test_nonzero_agent_exit_is_failure(self):
        self._start_build()
        class ExitOneRunner:
            def run(self, argv, *, cwd, timeout, env=None, cancel=None):
                if argv and argv[0] == "bash":
                    from regent.conduction.process import SubprocessRunner
                    return SubprocessRunner().run(argv, cwd=cwd, timeout=timeout, env=env)
                return RunResult(1, b"agent failed", False)  # non-zero exit
        result = self._run(ExitOneRunner())
        self.assertEqual(result["outcome"], "FAILURE")
        self.assertFalse((self.artdir / "STEP-09.md").exists())


if __name__ == "__main__":
    unittest.main()
