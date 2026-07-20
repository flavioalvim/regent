"""Directed tests for the STEP-06 review fixes (PLAN-002 build)."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from regent.activity import (ActivityService, NoActivity, NotActive,
                             explain_control_diff)
from regent.initcmd import EXIT_CONFLICT, run_init


class Step06FixesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.root = base / "repo"
        (self.root / ".regent").mkdir(parents=True)
        self.state = base / "state"
        self.state.mkdir()
        self.service = ActivityService(self.root, state_dir=self.state)
        self.service.store.seed()

    # -- finding 5: takeover only recovers ACTIVE activities ----------------

    def test_takeover_refused_when_idle(self):
        with self.assertRaises(NoActivity):
            self.service.takeover(reason="nothing to recover")
        self.assertEqual(self.service.lock.status()["state"], "free")

    def test_takeover_refused_when_suspended(self):
        self.service.start("plan", "PLAN-A")
        self.service.suspend(checkpoint="CP", reason="r")
        with self.assertRaises(NotActive):
            self.service.takeover(reason="suspended is resume's job")

    # -- finding 3: failures are never converted into success ---------------

    def test_suspend_release_failure_surfaces(self):
        self.service.start("plan", "PLAN-A")
        os.chmod(self.service.lock.path, 0o500)
        try:
            with self.assertRaises(OSError):
                self.service.suspend(checkpoint="CP", reason="r")
        finally:
            os.chmod(self.service.lock.path, 0o700)
        # Control already SUSPENDED (CAS happened) + lock held = row 6; a later
        # entry recovers it instead of pretending the release worked.
        control = self.service._recover()
        self.assertEqual(control["activity"]["state"], "SUSPENDED")
        self.assertEqual(self.service.lock.status()["state"], "free")

    # -- finding 2: hardened attributability --------------------------------

    def test_explain_rejects_forged_stop_and_schema_change(self):
        before = {"schema_version": 1, "version": 1, "updated_at": "t1",
                  "activity": {"id": "PLAN-A", "epoch": 0}, "stop_request": None,
                  "last_concluded": None}
        forged = dict(before, schema_version=2, version=2, updated_at="t2",
                      stop_request={"activity_id": "PLAN-OTHER",
                                    "activity_epoch": 9})
        diff = explain_control_diff(before, forged)
        self.assertIn("schema_version", diff["unexplained"])
        self.assertIn("stop_request", diff["unexplained"])

        legit = dict(before, version=2, updated_at="t2",
                     stop_request={"activity_id": "PLAN-A", "activity_epoch": 0})
        diff = explain_control_diff(before, legit)
        self.assertIn("stop_request", diff["explained"])
        self.assertEqual(diff["unexplained"], [])

        vanished = dict(before, version=2, updated_at="t2")
        diff = explain_control_diff(dict(before, stop_request={"activity_id":
                                                               "PLAN-A",
                                                               "activity_epoch": 0}),
                                    vanished)
        self.assertIn("stop_request", diff["unexplained"])  # disappearance

    def test_explain_flags_disallowed_audit_events(self):
        before = {"schema_version": 1, "version": 1, "updated_at": "t",
                  "activity": None, "stop_request": None, "last_concluded": None}
        diff = explain_control_diff(before, dict(before),
                                    audit_delta=[{"event": "turn_lock_takeover"}])
        self.assertIn("audit:turn_lock_takeover", diff["unexplained"])

    def test_control_explain_cli_detects_hijack(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        for k, v in (("user.name", "t"), ("user.email", "t@t")):
            subprocess.run(["git", "-C", str(self.root), "config", k, v], check=True)
        self.service.start("build", "PLAN-B")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "flush"],
                       check=True)
        from regent.cli import main
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["control", "--project", str(self.root), "explain"])
        self.assertEqual(code, 0, out.getvalue())  # no changes = explained

        def hijack(body):
            body["activity"]["id"] = "PLAN-HIJACKED"
            return body
        self.service.store.mutate(hijack)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["control", "--project", str(self.root), "explain"])
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 3)
        self.assertEqual(payload["error"], "UNATTRIBUTABLE")
        self.assertIn("activity", payload["detail"]["unexplained"])

    # -- finding 7: reason flows and suspended checkpoint in status ---------

    def test_stop_reason_flows_to_check_and_status_carries_checkpoint(self):
        self.service.start("plan", "PLAN-A")
        self.service.stop_request(reason="owner asked politely")
        check = self.service.stop_check()
        self.assertEqual(check["request"]["reason"], "owner asked politely")
        self.service.suspend(checkpoint="PLAN.md pendente", reason="stop")
        activity = self.service.status()["control"]["activity"]
        self.assertEqual(activity["checkpoint"], "PLAN.md pendente")
        self.assertEqual(activity["reason"], "stop")

    # -- finding 8: two schemes = corruption --------------------------------

    def test_two_schemes_present_is_corruption(self):
        en = self.root / ".regent" / "brainstorm" / "rounds" / "ROUND-001"
        pt = self.root / ".regent" / "brainstorm" / "rodadas" / "RODADA-001"
        en.mkdir(parents=True)
        (en / "DECISION.md").write_text("closed", encoding="utf-8")  # even closed
        pt.mkdir(parents=True)
        (pt / "DECISAO.md").write_text("closed", encoding="utf-8")
        report = self.service.status()
        self.assertEqual(report["workspace"]["verdict"], "MULTIPLE_SCHEMES")

    # -- finding 4: symlinked skill target is never overwritten -------------

    def test_init_refuses_symlinked_skill(self):
        import io
        outside = Path(self._tmp.name) / "outside.md"
        outside.write_text("precious host file", encoding="utf-8")
        skill_dir = self.root / ".regent" / "skills" / "regent"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").symlink_to(outside)
        out = io.StringIO()
        code = run_init(self.root, out=out)
        self.assertEqual(code, EXIT_CONFLICT)
        self.assertEqual(outside.read_text(encoding="utf-8"), "precious host file")

    # -- finding 1: concurrent start end-state coherence --------------------

    def test_concurrent_start_final_state_coherent(self):
        import multiprocessing as mp

        def contender(root, state, barrier, queue):
            service = ActivityService(Path(root), state_dir=Path(state))
            barrier.wait()
            try:
                service.start("plan", f"PLAN-{mp.current_process().pid}")
                queue.put("ok")
            except Exception:  # noqa: BLE001 — outcome recorded below
                queue.put("refused")

        barrier, queue = mp.Barrier(2), mp.Queue()
        procs = [mp.Process(target=contender,
                            args=(str(self.root), str(self.state), barrier, queue))
                 for _ in range(2)]
        for p in procs:
            p.start()
        outcomes = sorted(queue.get(timeout=20) for _ in procs)
        for p in procs:
            p.join(timeout=20)
        self.assertEqual(outcomes, ["ok", "refused"])
        control = self.service.store.load()
        lock_owner = json.loads(
            (self.service.lock.path / "owner.json").read_text())["token"]
        self.assertEqual(control["activity"]["turn"]["token"], lock_owner)


if __name__ == "__main__":
    unittest.main()
