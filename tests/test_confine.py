"""Directed tests for confinement composition + git attribution (PLAN-004 STEP-02)."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from regent.conduction import confine
from regent.conduction.hookscript import _append_event
from regent.conduction.turnlog import (Violation, append_terminal_seal,
                                       attribute_changes, read_events, verify_chain)


class ComposeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.envelope = [str(self.root / "work")]
        (self.root / "work").mkdir()

    def test_compose_isolated_settings_sources_empty(self):
        turn = confine.compose(envelope=self.envelope)
        self.addCleanup(turn.cleanup)
        argv = confine.launch_argv(turn, prompt="do it")
        self.assertIn("--setting-sources", argv)
        self.assertEqual(argv[argv.index("--setting-sources") + 1], "")

    def test_claude_argv_tools_restrictive_no_bash(self):
        turn = confine.compose(envelope=self.envelope)
        self.addCleanup(turn.cleanup)
        argv = confine.launch_argv(turn, prompt="x")
        tools = argv[argv.index("--tools") + 1]
        self.assertNotIn("Bash", tools)
        self.assertEqual(set(tools.split(",")),
                         {"Read", "Write", "Edit", "MultiEdit"})

    def test_permission_mode_acceptedits_forced(self):
        turn = confine.compose(envelope=self.envelope)
        self.addCleanup(turn.cleanup)
        argv = confine.launch_argv(turn, prompt="x")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")

    def test_env_is_minimal_allowlist(self):
        turn = confine.compose(envelope=self.envelope)
        self.addCleanup(turn.cleanup)
        env = confine.launch_env(turn)
        self.assertIn("REGENT_TURN_SECRET", env)
        self.assertIn("REGENT_ENVELOPE", env)
        for key in env:
            self.assertTrue(key.startswith("REGENT_") or key in confine.ENV_ALLOWLIST)

    def test_settings_and_hook_are_read_only(self):
        turn = confine.compose(envelope=self.envelope)
        self.addCleanup(turn.cleanup)
        self.assertEqual(turn.settings_path.stat().st_mode & 0o777, 0o400)
        self.assertEqual((turn.private_dir / "hookscript.py").stat().st_mode & 0o777,
                         0o400)

    def test_compose_cleanup_removes_private_dir(self):
        turn = confine.compose(envelope=self.envelope)
        private = turn.private_dir
        self.assertTrue(private.exists())
        turn.cleanup()
        self.assertFalse(private.exists())


class AttributionTest(unittest.TestCase):
    """The git-anchored proof: diff == attributed set."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        (self.root / "seed").write_text("seed", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "seed"],
                       check=True)
        self.work = self.root / "work"
        self.work.mkdir()
        self._logdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._logdir.cleanup)
        self.log = Path(self._logdir.name) / "events.log"

    def _write_and_post(self, relpath, content, tool_use_id="t1"):
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        import os
        os.environ["REGENT_EVENT_LOG"] = str(self.log)
        os.environ["REGENT_TURN_SECRET"] = "cd" * 16
        try:
            _append_event({"kind": "post", "tool": "Write",
                           "tool_use_id": tool_use_id, "path": str(path),
                           "content_sha256": hashlib.sha256(
                               content.encode()).hexdigest()})
        finally:
            for key in ("REGENT_EVENT_LOG", "REGENT_TURN_SECRET"):
                os.environ.pop(key, None)

    def _attribute(self, **kwargs):
        events = read_events(self.log)
        return attribute_changes(self.root, events, **kwargs)

    def test_diff_equals_attributed_set_ok(self):
        self._write_and_post("work/a.txt", "hello")
        result = self._attribute(envelope=["work"], gate_envelope=[], exemptions=[])
        self.assertIn("work/a.txt", result["attributed"])

    def test_unlogged_change_is_violation(self):
        (self.work / "sneaky.txt").write_text("no post event", encoding="utf-8")
        with self.assertRaises(Violation) as ctx:
            self._attribute(envelope=["work"], gate_envelope=[], exemptions=[])
        self.assertIn("no post event", str(ctx.exception.detail))

    def test_blob_sha_mismatch_is_violation(self):
        self._write_and_post("work/a.txt", "declared")
        (self.work / "a.txt").write_text("SWAPPED after the post", encoding="utf-8")
        with self.assertRaises(Violation) as ctx:
            self._attribute(envelope=["work"], gate_envelope=[], exemptions=[])
        self.assertIn("blob sha mismatch", str(ctx.exception.detail))

    def test_posted_but_outside_envelope_is_violation(self):
        self._write_and_post("elsewhere/x.txt", "content")
        with self.assertRaises(Violation):
            self._attribute(envelope=["work"], gate_envelope=[], exemptions=[])

    def test_gate_touching_inside_gate_envelope_ok(self):
        (self.root / "dist").mkdir()
        (self.root / "dist" / "built.whl").write_text("artifact", encoding="utf-8")
        result = self._attribute(envelope=["work"], gate_envelope=["dist"],
                                  exemptions=[])
        self.assertIn("dist/built.whl", result["attributed"])

    def test_gate_touching_outside_envelope_violation(self):
        (self.root / "random.txt").write_text("stray gate effect", encoding="utf-8")
        with self.assertRaises(Violation):
            self._attribute(envelope=["work"], gate_envelope=["dist"], exemptions=[])

    def test_operational_exemptions_pass(self):
        control = self.root / ".regent" / "control.json"
        control.parent.mkdir(parents=True)
        control.write_text("{}", encoding="utf-8")
        result = self._attribute(envelope=["work"], gate_envelope=[],
                                  exemptions=[".regent/control.json"])
        self.assertNotIn(".regent/control.json", result["attributed"])  # exempt


if __name__ == "__main__":
    unittest.main()
