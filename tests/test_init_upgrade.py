"""Directed tests for init upgrade-by-manifest + control seeding (PLAN-002 STEP-03)."""

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from regent import initcmd
from regent.doctor import EXIT_OK, EXIT_UNAVAILABLE, run_doctor
from regent.initcmd import EXIT_CONFLICT, EXIT_FAILURE, run_init

OLD_CONTENT = "---\nname: regent\n---\nv0 legacy skill body\n"
OLD_HASH = hashlib.sha256(OLD_CONTENT.encode()).hexdigest()


def _probe_ok(argv):
    return "OK", f"{argv[0]} 1.0"


class InitUpgradeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _init(self):
        out = io.StringIO()
        code = run_init(self.root, out=out)
        return code, out.getvalue()

    def _patched_manifest(self):
        manifest = initcmd._manifest()
        patched = {key: list(hashes) + [OLD_HASH] for key, hashes in manifest.items()}
        return mock.patch.object(initcmd, "_manifest", lambda: patched)

    def _write_legacy_host(self):
        skill = self.root / ".regent" / "skills" / "regent" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(OLD_CONTENT, encoding="utf-8")
        return skill

    def test_upgrade_v0_host_to_v1(self):
        skill = self._write_legacy_host()
        with self._patched_manifest():
            code, output = self._init()
        self.assertEqual(code, 0, output)
        self.assertIn("upgraded .regent/skills/regent/SKILL.md", output)
        self.assertNotEqual(skill.read_text(encoding="utf-8"), OLD_CONTENT)
        self.assertTrue((self.root / ".regent" / "control.json").is_file())

    def test_unknown_skill_content_is_conflict(self):
        skill = self._write_legacy_host()
        skill.write_text("edited by the host in unknown ways", encoding="utf-8")
        code, output = self._init()
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertEqual(skill.read_text(encoding="utf-8"),
                         "edited by the host in unknown ways")  # preserved
        self.assertFalse((self.root / ".regent" / "control.json").exists())

    def test_upgrade_failure_rolls_back_without_temps(self):
        skill = self._write_legacy_host()
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "skills").write_text("not a dir")  # forces failure
        with self._patched_manifest():
            code, output = self._init()
        self.assertEqual(code, EXIT_FAILURE)
        self.assertIn("rolled back", output)
        self.assertEqual(skill.read_text(encoding="utf-8"), OLD_CONTENT)  # restored
        self.assertFalse((self.root / ".regent" / "control.json").exists())
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_reinit_v1_with_evolved_control_noop(self):
        self.assertEqual(self._init()[0], 0)
        from regent.activity import ActivityService
        service = ActivityService(self.root,
                                  state_dir=self.root / ".state-for-test")
        service.start("plan", "PLAN-X")  # control evolves past version 0
        version = service.store.load()["version"]
        code, output = self._init()
        self.assertEqual(code, 0)
        self.assertIn("already initialized", output)
        self.assertEqual(service.store.load()["version"], version)  # untouched

    def test_init_seeds_valid_control(self):
        self.assertEqual(self._init()[0], 0)
        from regent.protocol import AuditLog, ControlStore
        control = ControlStore(self.root / ".regent" / "control.json",
                               AuditLog(self.root / "a.jsonl")).load()
        self.assertEqual(control["version"], 0)
        self.assertIsNone(control["activity"])

    def test_doctor_corrupt_control_nonzero(self):
        self.assertEqual(self._init()[0], 0)
        (self.root / ".regent" / "control.json").write_text("{broken",
                                                            encoding="utf-8")
        out = io.StringIO()
        code = run_doctor(self.root, out=out, probe=_probe_ok)
        self.assertEqual(code, EXIT_UNAVAILABLE)
        self.assertIn("CORRUPT", out.getvalue())

    def test_doctor_ok_with_valid_control(self):
        self.assertEqual(self._init()[0], 0)
        out = io.StringIO()
        code = run_doctor(self.root, out=out, probe=_probe_ok)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("INITIALIZED", out.getvalue())


if __name__ == "__main__":
    unittest.main()
