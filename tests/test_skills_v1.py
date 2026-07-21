"""Directed tests for the v1 skills (PLAN-002 STEP-04): anti-drift and the
executable control×files matrix."""

import re
import tempfile
import unittest
from importlib import resources
from pathlib import Path

from regent.activity import WORKSPACE_VERDICTS, ActivityService
from regent.activity_cli import _EXIT_BY_CODE

KNOWN_SUBCOMMANDS = {
    "regent status", "regent init", "regent doctor",
    "regent activity start", "regent activity resume", "regent activity suspend",
    "regent activity conclude", "regent activity heartbeat",
    "regent activity takeover", "regent stop request", "regent stop check",
    "regent control explain", "regent advisor consult", "regent gate run",
    "regent turn run", "regent loop run", "regent loop abort",
    "regent rehearse", "regent arm", "regent disarm", "regent daemon run",
}


def _templates() -> dict[str, str]:
    base = resources.files("regent").joinpath("templates/skills")
    return {name: base.joinpath(name, "SKILL.md").read_text(encoding="utf-8")
            for name in ("regent", "regent-stop")}


class SkillAntiDriftTest(unittest.TestCase):
    def test_skill_templates_reference_real_subcommands(self):
        # Only COMMAND citations count: `regent ...` inside backtick spans.
        for name, text in _templates().items():
            for span in re.findall(r"`([^`]*)`", text.replace("\n", " ")):
                match = re.match(r"regent (?:(activity|stop|control|advisor|gate|turn|loop|daemon) )?([a-z-]+)", span)
                if not match:
                    continue
                group, word = match.group(1), match.group(2)
                command = f"regent {group + ' ' if group else ''}{word}"
                self.assertIn(command, KNOWN_SUBCOMMANDS,
                              f"{name}: unknown command cited: {command!r}")

    def test_skill_no_longer_prescribes_raw_codex(self):
        for name, text in _templates().items():
            self.assertNotIn("codex --ask-for-approval", text,
                             f"{name}: raw codex invocation still prescribed")

    def test_skill_templates_error_codes_exist(self):
        allowed = set(_EXIT_BY_CODE) | set(WORKSPACE_VERDICTS) | {
            "SUCCESS", "DISCORDA"}
        structural = {"STEP", "PLAN", "ROUND", "QUESTION", "REQUEST", "DECISION",
                      "APPROVAL", "CONCLUSION", "BASE", "SHA", "MANIFEST",
                      "SUSPENDED", "ACTIVE", "OK", "PROMPT", "NNN", "TIMEOUT",
                      "FAILURE", "CANCELLED", "APPROVED", "REJECTED", "ACCEPTED"}
        for name, text in _templates().items():
            for code in re.findall(r"`([A-Z][A-Z_-]{3,})`", text):
                base = code.split("-")[0]
                if re.fullmatch(r"[A-Z_]+", code) and base not in structural:
                    self.assertIn(code, allowed,
                                  f"{name}: unknown code cited: {code}")


class WorkspaceMatrixTest(unittest.TestCase):
    """Every row of the PLAN-002 control×files matrix, with its own fixture."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / ".regent").mkdir()

    def _open_plan(self, name, approved=False, build_open=False, concluded=False):
        plan = self.root / ".regent" / "plans" / name
        plan.mkdir(parents=True)
        if approved:
            (plan / "APPROVAL.md").write_text("status: APPROVED", encoding="utf-8")
        if build_open:
            (plan / "build").mkdir()
        if concluded:
            (plan / "build").mkdir(exist_ok=True)
            (plan / "build" / "CONCLUSION.md").write_text("status: ACCEPTED",
                                                          encoding="utf-8")
        return plan

    def _open_round(self, name, decided=False):
        rnd = self.root / ".regent" / "brainstorm" / "rounds" / name
        rnd.mkdir(parents=True)
        if decided:
            (rnd / "DECISION.md").write_text("x", encoding="utf-8")
        return rnd

    def _verdict(self, activity):
        service = ActivityService(self.root, state_dir=self.root / ".state")
        return service.workspace_report(activity)["verdict"]

    def _active(self, atype, aid, state="ACTIVE"):
        return {"type": atype, "id": aid, "epoch": 1, "state": state}

    def test_row_ok_active_coherent(self):
        self._open_plan("PLAN-001")
        self.assertEqual(self._verdict(self._active("plan", "PLAN-001")), "OK")

    def test_row_type_mismatch(self):
        self._open_round("ROUND-001")
        self.assertEqual(self._verdict(self._active("plan", "ROUND-001")),
                         "TYPE_MISMATCH")

    def test_row_orphan_no_dir(self):
        self.assertEqual(self._verdict(self._active("plan", "PLAN-009")),
                         "ORPHAN_NO_DIR")

    def test_row_orphan_with_other_open(self):
        self._open_round("ROUND-002")
        self.assertEqual(self._verdict(self._active("plan", "PLAN-009")),
                         "ORPHAN_WITH_OTHER_OPEN")

    def test_row_terminal_exists(self):
        self._open_plan("PLAN-001", approved=True)  # terminal for a plan activity
        self.assertEqual(self._verdict(self._active("plan", "PLAN-001")),
                         "TERMINAL_EXISTS")

    def test_row_second_artifact(self):
        self._open_plan("PLAN-001")
        self._open_round("ROUND-003")
        self.assertEqual(self._verdict(self._active("plan", "PLAN-001")),
                         "SECOND_ARTIFACT")

    def test_row_suspended_ok_and_orphan(self):
        import shutil
        plan = self._open_plan("PLAN-001")
        self.assertEqual(
            self._verdict(self._active("plan", "PLAN-001", state="SUSPENDED")),
            "SUSPENDED_OK")
        shutil.rmtree(plan)  # no other open artifacts remain
        self.assertEqual(
            self._verdict(self._active("plan", "PLAN-001", state="SUSPENDED")),
            "SUSPENDED_ORPHAN")

    def test_row_legacy_open_artifact_idle(self):
        self._open_round("ROUND-001")
        self.assertEqual(self._verdict(None), "LEGACY_OPEN_ARTIFACT")

    def test_row_multiple_open(self):
        self._open_round("ROUND-001")
        self._open_plan("PLAN-001")
        self.assertEqual(self._verdict(None), "MULTIPLE_OPEN")

    def test_row_idle_clean_and_build_open(self):
        self.assertEqual(self._verdict(None), "IDLE_CLEAN")
        self._open_plan("PLAN-002", approved=True, build_open=True)
        self.assertEqual(self._verdict(self._active("build", "PLAN-002")), "OK")

    def test_legacy_pt_scheme_detected(self):
        legacy = self.root / ".regent" / "brainstorm" / "rodadas" / "RODADA-004"
        legacy.mkdir(parents=True)
        self.assertEqual(self._verdict(None), "LEGACY_OPEN_ARTIFACT")

    def test_status_carries_workspace(self):
        service = ActivityService(self.root, state_dir=self.root / ".state")
        service.store.seed()
        report = service.status()
        self.assertEqual(report["workspace"]["verdict"], "IDLE_CLEAN")


if __name__ == "__main__":
    unittest.main()
