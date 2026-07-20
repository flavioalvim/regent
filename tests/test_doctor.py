"""Tests for regent doctor: exit codes and per-capability report."""

import io
import tempfile
import unittest
from pathlib import Path

from regent.doctor import EXIT_OK, EXIT_UNAVAILABLE, run_doctor


def probe_all_ok(argv):
    return "OK", f"{argv[0]} 1.0.0"


def probe_advisor_missing(argv):
    if argv[0] == "codex":
        return "MISSING", "'codex' not found on PATH"
    return "OK", "claude 1.0.0"


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _doctor(self, probe):
        out = io.StringIO()
        code = run_doctor(self.root, out=out, probe=probe)
        return code, out.getvalue()

    def test_all_capabilities_ok(self):
        code, output = self._doctor(probe_all_ok)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("executor", output)
        self.assertIn("advisor", output)
        self.assertIn("NOT-INITIALIZED", output)

    def test_missing_capability_fails(self):
        code, output = self._doctor(probe_advisor_missing)
        self.assertEqual(code, EXIT_UNAVAILABLE)
        self.assertIn("MISSING", output)

    def test_initialized_project_is_reported(self):
        (self.root / ".regent").mkdir()
        code, output = self._doctor(probe_all_ok)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("INITIALIZED", output)


if __name__ == "__main__":
    unittest.main()
