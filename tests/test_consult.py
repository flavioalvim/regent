"""Directed tests for regent advisor consult (PLAN-003 STEP-01)."""

import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from regent.cli import main
from regent.conduction.consult import AdvisorUnavailable, run_consult
from regent.conduction.evidence import EvidenceConflict
from regent.conduction.process import RunResult


class FakeRunner:
    def __init__(self, exit_code=0, timed_out=False, message="opinião...\nCONCORDA\n",
                 raw_output="raw log"):
        self.exit_code, self.timed_out = exit_code, timed_out
        self.message, self.raw_output = message, raw_output
        self.argv = None

    def run(self, argv, *, cwd, timeout):
        self.argv = argv
        msg_file = argv[argv.index("-o") + 1]
        if not self.timed_out and self.message is not None:
            Path(msg_file).write_text(self.message, encoding="utf-8")
        return RunResult(None if self.timed_out else self.exit_code,
                         self.raw_output.encode("utf-8"), self.timed_out)


class ConsultTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / ".regent").mkdir()
        self.prompt = self.root / "PROMPT-src.md"
        self.prompt.write_text("Avalie o plano.\nTERMINE com CONCORDA ou DISCORDA.",
                               encoding="utf-8")
        self.artifact = self.root / ".regent" / "plans" / "P" / "ADVISOR-1.md"

    def _consult(self, runner, **kwargs):
        return run_consult(self.root, prompt_file=self.prompt,
                           artifact=self.artifact, linkage="PLAN-003",
                           runner=runner, **kwargs)

    def test_consult_success_persists_tuple_and_verdict(self):
        result = self._consult(FakeRunner())
        self.assertTrue(result["ok"])
        self.assertEqual(result["verdict"], "CONCORDA")
        text = self.artifact.read_text(encoding="utf-8")
        self.assertIn("outcome: SUCCESS", text)
        self.assertIn("exit_code: 0", text)
        self.assertIn("linkage: PLAN-003", text)
        self.assertIn("verdict: CONCORDA", text)
        self.assertIn("opinião...", text)

    def test_consult_prompt_copy_byte_identical(self):
        self._consult(FakeRunner())
        copy = Path(str(self.artifact) + "-PROMPT.md")
        self.assertEqual(copy.read_bytes(), self.prompt.read_bytes())

    def test_consult_sandbox_flags_forced(self):
        runner = FakeRunner()
        self._consult(runner)
        argv = runner.argv
        self.assertIn("--sandbox", argv)
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertIn("--ask-for-approval", argv)
        self.assertEqual(argv[argv.index("--ask-for-approval") + 1], "never")

    def test_consult_timeout_records_and_fails_closed(self):
        result = self._consult(FakeRunner(timed_out=True, message=None))
        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], "TIMEOUT")
        text = self.artifact.read_text(encoding="utf-8")
        self.assertIn("outcome: TIMEOUT", text)
        self.assertIn("exit_code: null", text)

    def test_consult_failure_records_exit_code(self):
        result = self._consult(FakeRunner(exit_code=7, message=None,
                                          raw_output="boom"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], "FAILURE")
        self.assertIn("exit_code: 7", self.artifact.read_text(encoding="utf-8"))
        self.assertIn("boom", self.artifact.read_text(encoding="utf-8"))

    def test_consult_expect_verdict_fail_closed(self):
        result = self._consult(FakeRunner(message="análise sem veredicto final\n"),
                               expect_verdict=r"^APROVADO$")
        self.assertFalse(result["ok"])  # SUCCESS outcome, but demanded verdict absent
        self.assertEqual(result["outcome"], "SUCCESS")
        self.assertIsNone(result["verdict"])

    def test_consult_default_regex_null_verdict_is_informational(self):
        result = self._consult(FakeRunner(message="sem veredicto\n"))
        self.assertTrue(result["ok"])  # no explicit expectation: null allowed
        self.assertIsNone(result["verdict"])

    def test_consult_pair_conflict_either_file(self):
        copy = Path(str(self.artifact) + "-PROMPT.md")
        copy.parent.mkdir(parents=True)
        copy.write_text("pre-existing", encoding="utf-8")
        with self.assertRaises(EvidenceConflict):
            self._consult(FakeRunner())
        self.assertFalse(self.artifact.exists())  # nothing else was written

    def test_consult_refuses_existing_artifact(self):
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_text("old evidence", encoding="utf-8")
        with self.assertRaises(EvidenceConflict):
            self._consult(FakeRunner())
        self.assertEqual(self.artifact.read_text(encoding="utf-8"), "old evidence")

    def test_consult_terminal_outcome_always_completes_pair(self):
        for runner in (FakeRunner(), FakeRunner(timed_out=True, message=None),
                       FakeRunner(exit_code=3, message=None)):
            with self.subTest(runner=runner):
                self._consult(runner)
                self.assertTrue(self.artifact.exists())
                self.assertTrue(Path(str(self.artifact) + "-PROMPT.md").exists())
                self.artifact.unlink()
                Path(str(self.artifact) + "-PROMPT.md").unlink()

    def test_consult_missing_codex_is_capability_error(self):
        with self.assertRaises(AdvisorUnavailable):
            run_consult(self.root, prompt_file=self.prompt,
                        artifact=self.artifact, linkage="X",
                        codex_bin="definitely-not-a-real-binary-xyz")

    def test_conflict_race_on_main_cleans_prompt_orphan(self):
        artifact = self.artifact

        class RacingRunner(FakeRunner):
            def run(inner, argv, *, cwd, timeout):
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("raced-in evidence", encoding="utf-8")
                return super().run(argv, cwd=cwd, timeout=timeout)

        with self.assertRaises(EvidenceConflict):
            self._consult(RacingRunner())
        self.assertFalse(Path(str(artifact) + "-PROMPT.md").exists())  # cleaned
        self.assertEqual(artifact.read_text(encoding="utf-8"),
                         "raced-in evidence")  # the racer's evidence untouched

    def test_runner_never_inherits_stdin(self):
        from regent.conduction.process import SubprocessRunner
        result = SubprocessRunner().run(
            ["bash", "-c", "cat; echo done"], cwd=str(self.root), timeout=5)
        self.assertFalse(result.timed_out)  # cat gets EOF immediately (DEVNULL)
        self.assertIn("done", result.output)

    def test_consult_cli_with_fake_codex_on_path(self):
        bindir = self.root / "bin"
        bindir.mkdir()
        fake = bindir / "codex"
        fake.write_text('#!/usr/bin/env bash\n'
                        'while [ "$1" != "-o" ]; do shift; done\n'
                        'printf "parecer\\nCONCORDA\\n" > "$2"\n', encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{bindir}:{old_path}"
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["advisor", "--project", str(self.root), "consult",
                         "--prompt-file", str(self.prompt),
                         "--artifact", str(self.artifact),
                         "--linkage", "PLAN-003",
                         "--expect-verdict", "^CONCORDA$"])
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["verdict"], "CONCORDA")


if __name__ == "__main__":
    unittest.main()
