"""Directed tests for regent gate run (PLAN-003 STEP-02)."""

import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from regent.conduction.evidence import EvidenceConflict
from regent.conduction.gate import ProvenanceError, run_gate


class GateTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.plan = self.root / "PLAN.md"
        self.artifact = self.root / "evidence" / "GATE-01.md"

    def _declare(self, command: str):
        self.plan.write_text(f"## Etapa\n- **Gate:** `{command}`\n", encoding="utf-8")
        return command

    def _run(self, command, **kwargs):
        return run_gate(self.root, command=command, declared_in=self.plan,
                        artifact=self.artifact, linkage="PLAN-003/STEP-02",
                        **kwargs)

    def test_gate_green_persists_and_exits_zero(self):
        result = self._run(self._declare("echo gate-ok"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], "GREEN")
        text = self.artifact.read_text(encoding="utf-8")
        self.assertIn("outcome: GREEN", text)
        self.assertIn("command: echo gate-ok", text)
        self.assertIn("gate-ok", text)
        self.assertIn("truncated: False", text)

    def test_gate_red_fails_closed_with_artifact(self):
        result = self._run(self._declare("echo failing; exit 5"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], "RED")
        self.assertEqual(result["exit_code"], 5)
        self.assertIn("outcome: RED", self.artifact.read_text(encoding="utf-8"))

    def test_gate_provenance_required(self):
        self.plan.write_text("no gates declared here", encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            self._run("echo undeclared")
        self.assertFalse(self.artifact.exists())

    def test_gate_timeout_recorded(self):
        result = self._run(self._declare("sleep 30"), timeout=0.5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], "TIMEOUT")
        self.assertIn("exit_code: null", self.artifact.read_text(encoding="utf-8"))

    def test_gate_timeout_kills_process_group(self):
        pidfile = self.root / "child.pid"
        command = self._declare(f"sleep 60 & echo $! > {pidfile}; wait")
        result = self._run(command, timeout=0.5)
        self.assertEqual(result["outcome"], "TIMEOUT")
        time.sleep(0.2)
        child_pid = int(pidfile.read_text().strip())
        with self.assertRaises(ProcessLookupError):  # the CHILD died with the group
            import os
            os.kill(child_pid, 0)

    def test_gate_refuses_existing_artifact(self):
        self._declare("echo x")
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_text("old evidence", encoding="utf-8")
        with self.assertRaises(EvidenceConflict):
            self._run("echo x")
        self.assertEqual(self.artifact.read_text(encoding="utf-8"), "old evidence")

    def test_full_log_sidecar_over_200k(self):
        command = self._declare("yes A | head -c 300000")
        result = self._run(command)
        self.assertEqual(result["outcome"], "GREEN")
        full = Path(str(self.artifact) + "-FULL.log")
        self.assertTrue(full.exists())
        self.assertGreaterEqual(full.stat().st_size, 300000)
        text = self.artifact.read_text(encoding="utf-8")
        self.assertIn("truncated: True", text)
        self.assertIn("output_bytes: 300000", text)
        self.assertIn("[truncated:", text)

    def test_gate_output_tail_truncation_declared(self):
        command = self._declare("seq 1 100000")
        self._run(command)
        text = self.artifact.read_text(encoding="utf-8")
        self.assertIn("100000", text)  # the tail keeps the END of the output

    def test_gate_full_sidecar_conflict(self):
        self._declare("echo x")
        full = Path(str(self.artifact) + "-FULL.log")
        full.parent.mkdir(parents=True)
        full.write_text("pre-existing evidence", encoding="utf-8")
        with self.assertRaises(EvidenceConflict):
            self._run("echo x")
        self.assertFalse(self.artifact.exists())


if __name__ == "__main__":
    unittest.main()
