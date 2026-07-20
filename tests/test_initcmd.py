"""Tests for regent init: seeding, idempotency, conflict detection, rollback."""

import io
import os
import tempfile
import unittest
from pathlib import Path

from regent.initcmd import EXIT_CONFLICT, EXIT_FAILURE, EXIT_OK, run_init


class InitTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _init(self):
        out = io.StringIO()
        code = run_init(self.root, out=out)
        return code, out.getvalue()

    def test_fresh_project_seeds_everything(self):
        code, output = self._init()
        self.assertEqual(code, EXIT_OK, output)
        for name in ("regent", "regent-stop"):
            skill = self.root / ".regent" / "skills" / name / "SKILL.md"
            self.assertTrue(skill.is_file())
            self.assertIn(f"name: {name}", skill.read_text())
            link = self.root / ".claude" / "skills" / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), f"../../.regent/skills/{name}")
            self.assertTrue((link / "SKILL.md").is_file())  # symlink resolves
        self.assertTrue((self.root / ".regent" / "brainstorm" / "rounds").is_dir())
        self.assertTrue((self.root / ".regent" / "plans").is_dir())

    def test_rerun_is_noop(self):
        self.assertEqual(self._init()[0], EXIT_OK)
        code, output = self._init()
        self.assertEqual(code, EXIT_OK)
        self.assertIn("already initialized", output)

    def test_divergent_content_is_conflict_and_untouched(self):
        skill = self.root / ".regent" / "skills" / "regent" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("host content that differs")
        code, output = self._init()
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertIn("conflict", output)
        self.assertEqual(skill.read_text(), "host content that differs")
        self.assertFalse((self.root / ".claude").exists())  # nothing else was created

    def test_failure_rolls_back_everything(self):
        # A FILE at .claude/skills makes the symlink parent creation fail mid-run.
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "skills").write_text("not a directory")
        code, output = self._init()
        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("rolled back", output)
        self.assertFalse((self.root / ".regent").exists())

    def test_missing_seed_completes_partial_prior_state(self):
        # An identical prior artifact is kept; only the absent ones are seeded.
        self.assertEqual(self._init()[0], EXIT_OK)
        link = self.root / ".claude" / "skills" / "regent"
        link.unlink()
        code, output = self._init()
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(link.is_symlink())


if __name__ == "__main__":
    unittest.main()
