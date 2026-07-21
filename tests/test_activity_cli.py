"""Directed tests for the CLI JSON contract (PLAN-002 STEP-02)."""

import io
import json
import os
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
    return code, json.loads(text) if text else None


class ActivityCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.root = base / "repo"
        (self.root / ".regent").mkdir(parents=True)
        state = base / "state"
        os.environ["XDG_STATE_HOME"] = str(state)
        self.addCleanup(os.environ.pop, "XDG_STATE_HOME", None)
        self.project = ["--project", str(self.root)]

    def _seed_control(self):
        from regent.activity import ActivityService
        ActivityService(self.root).store.seed()

    def test_status_shapes_uninitialized_idle_active(self):
        code, payload = _run(["status", *self.project])
        self.assertEqual(code, 0)
        self.assertEqual(payload["control"], "uninitialized")
        self.assertIn(payload["lock"]["state"], ("free", "held", "suspect"))
        self.assertIn("capabilities", payload)

        self._seed_control()
        code, payload = _run(["status", *self.project])
        self.assertEqual(code, 0)
        self.assertIsNone(payload["control"]["activity"])
        self.assertFalse(payload["local_token_present"])

        _run(["activity", *self.project, "start", "--type", "plan", "--id", "PLAN-A"])
        code, payload = _run(["status", *self.project])
        self.assertEqual(payload["control"]["activity"]["state"], "ACTIVE")
        self.assertTrue(payload["local_token_present"])

    def test_status_shape_corrupt(self):
        (self.root / ".regent" / "control.json").write_text("{broken",
                                                            encoding="utf-8")
        code, payload = _run(["status", *self.project])
        self.assertEqual(code, 0)  # status reports, never fails on state
        self.assertEqual(payload["control"], "corrupt")

    def test_error_envelope_and_exit_codes(self):
        self._seed_control()
        code, payload = _run(["activity", *self.project, "suspend",
                              "--checkpoint", "CP", "--reason", "r"])
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "NO_ACTIVITY")
        self.assertIn("detail", payload)

        _run(["activity", *self.project, "start", "--type", "plan", "--id", "PLAN-A"])
        code, payload = _run(["activity", *self.project, "start",
                              "--type", "plan", "--id", "PLAN-B"])
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "ACTIVITY_OPEN")
        self.assertEqual(payload["detail"]["activity"]["id"], "PLAN-A")

    def test_json_purity_on_usage_error(self):
        code, payload = _run(["activity", "--project", str(self.root), "start"])
        self.assertEqual(code, 64)
        self.assertEqual(payload["error"], "USAGE")
        self.assertIsInstance(payload["detail"], str)

    def test_root_discovery_upward_and_project_flag(self):
        self._seed_control()
        nested = self.root / "src" / "deep"
        nested.mkdir(parents=True)
        cwd = os.getcwd()
        try:
            os.chdir(nested)
            code, payload = _run(["status"])  # discovered upward
            self.assertEqual(code, 0)
            self.assertIsInstance(payload["control"], dict)
        finally:
            os.chdir(cwd)
        code, payload = _run(["status", "--project", str(self.root / "nowhere")])
        self.assertEqual(code, 2)
        self.assertEqual(payload["error"], "UNINITIALIZED")

    def test_full_lifecycle_via_cli(self):
        self._seed_control()
        code, started = _run(["activity", *self.project, "start",
                              "--type", "build", "--id", "PLAN-002"])
        self.assertEqual(code, 0)
        self.assertTrue(started["ok"])
        self.assertEqual(len(started["token"]), 32)

        code, hb = _run(["activity", *self.project, "heartbeat"])
        self.assertEqual(code, 0)

        code, sus = _run(["activity", *self.project, "suspend", "--checkpoint",
                          "STEP-01:GATE-GREEN", "--reason", "owner stop",
                          "--evidence", "docs/PRD.md"])
        self.assertEqual(code, 0)
        self.assertEqual(sus["activity"]["state"], "SUSPENDED")

        code, res = _run(["activity", *self.project, "resume"])
        self.assertEqual(code, 0)
        self.assertEqual(res["checkpoint"], "STEP-01:GATE-GREEN")

        code, done = _run(["activity", *self.project, "conclude",
                           "--status", "ACCEPTED"])
        self.assertEqual(code, 0)
        self.assertEqual(done["last_concluded"]["status"], "ACCEPTED")

    def test_stop_request_and_check_cli(self):
        self._seed_control()
        _run(["activity", *self.project, "start", "--type", "plan", "--id", "PLAN-A"])
        code, req = _run(["stop", *self.project, "request"])
        self.assertEqual(code, 0)
        self.assertFalse(req["noop"])
        code, check = _run(["stop", *self.project, "check"])
        self.assertEqual(code, 0)
        self.assertTrue(check["stop_requested"])

    def test_stop_request_suspended_is_noop(self):
        self._seed_control()
        _run(["activity", *self.project, "start", "--type", "plan", "--id", "PLAN-A"])
        _run(["activity", *self.project, "suspend", "--checkpoint", "CP",
              "--reason", "r"])
        code, req = _run(["stop", *self.project, "request"])
        self.assertEqual(code, 0)
        self.assertTrue(req["noop"])

    def test_takeover_via_cli_audited(self):
        self._seed_control()
        _, started = _run(["activity", *self.project, "start",
                           "--type", "plan", "--id", "PLAN-A"])
        from regent.activity import ActivityService
        service = ActivityService(self.root)
        service.lock.release(started["token"])  # manufacture ACTIVE+free (row 3)

        code, payload = _run(["activity", *self.project, "heartbeat"])
        self.assertEqual(code, 3)
        self.assertEqual(payload["error"], "LOCK_SUSPECT")

        code, taken = _run(["activity", *self.project, "takeover",
                            "--reason", "row-3 recovery"])
        self.assertEqual(code, 0)
        self.assertEqual(taken["previous_owner"], started["token"])
        events = [r["event"] for r in service.audit.read_all()]
        self.assertIn("turn_lock_takeover", events)


class VersionTest(unittest.TestCase):
    def test_cli_version_reports_080(self):
        import regent
        self.assertEqual(regent.__version__, "0.8.0")


if __name__ == "__main__":
    unittest.main()
