"""Directed tests for the commit choreography (PLAN-002 STEP-05).

The choreography is executed by the skill; these tests exercise its normative
properties with real git repos + the executable helpers that back them."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from regent.activity import ActivityService, explain_control_diff


def _git(repo: Path, *argv) -> str:
    return subprocess.run(["git", "-C", str(repo), *argv], capture_output=True,
                          text=True, check=True).stdout.strip()


class ChoreographyTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.repo = base / "repo"
        (self.repo / ".regent").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        _git(self.repo, "config", "user.name", "test")
        _git(self.repo, "config", "user.email", "t@t")
        self.service = ActivityService(self.repo, state_dir=base / "state")
        self.service.store.seed()
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-qm", "seed")

    def test_build_choreography_base_sha_after_operational_flush(self):
        # Pending control mutation before build start...
        self.service.start("build", "PLAN-Z")
        dirty = _git(self.repo, "status", "--porcelain")
        self.assertIn("control.json", dirty)
        # ...must be flushed by an operational commit BEFORE taking BASE-SHA.
        _git(self.repo, "add", ".regent")
        _git(self.repo, "commit", "-qm", "operational: flush control before baseline")
        base_sha = _git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(_git(self.repo, "status", "--porcelain"), "")
        # The baseline is clean INCLUDING the exempted files.
        self.assertIn("operational", _git(self.repo, "log", "-1", "--format=%s",
                                          base_sha))

    def test_step_commit_attributability_of_exempted_files(self):
        self.service.start("build", "PLAN-Z")
        before = self.service.store.load()
        # Explained mutation: an external stop request arrives mid-step.
        self.service.stop_request()
        after = self.service.store.load()
        diff = explain_control_diff(before, after)
        self.assertIn("stop_request", diff["explained"])
        self.assertEqual(diff["unexplained"], [])

        # Unexplained mutation: the activity itself changed under the step.
        def rogue(body):
            body["activity"]["id"] = "PLAN-HIJACKED"
            return body
        self.service.store.mutate(rogue, retries=2)
        hijacked = self.service.store.load()
        diff = explain_control_diff(before, hijacked)
        self.assertIn("activity", diff["unexplained"])  # step commit must FAIL

    def test_stop_after_staging_goes_to_next_operational_commit(self):
        self.service.start("build", "PLAN-Z")
        _git(self.repo, "add", ".regent")  # staging closes the boundary snapshot
        staged_before = _git(self.repo, "diff", "--cached", "--name-only")
        self.service.stop_request()  # arrives AFTER staging
        staged_after = _git(self.repo, "diff", "--cached", "--name-only")
        self.assertEqual(staged_before, staged_after)  # deliberate commit untouched
        _git(self.repo, "commit", "-qm", "step commit (deliberate)")
        # The post-staging mutation is still pending for the NEXT commit:
        pending = _git(self.repo, "status", "--porcelain")
        self.assertIn("control.json", pending)
        check = self.service.stop_check()
        self.assertTrue(check["stop_requested"])  # honored at the boundary


if __name__ == "__main__":
    unittest.main()
