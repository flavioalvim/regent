"""Directed tests for the confinement hook + authenticated chain (PLAN-004 STEP-01).

The REAL hook is exercised: a fake agent invokes hookscript.main with real
PreToolUse/PostToolUse payloads, exactly as Claude Code would."""

import json
import multiprocessing as mp
import os
import tempfile
import unittest
from pathlib import Path

from regent.conduction import hookscript
from regent.conduction.turnlog import (ChainError, append_terminal_seal,
                                       read_events, verify_chain)

SECRET = "ab" * 16


class HookTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.envelope_dir = self.root / "work"
        self.envelope_dir.mkdir()
        self.log = self.root / "events.log"
        os.environ["REGENT_EVENT_LOG"] = str(self.log)
        os.environ["REGENT_TURN_SECRET"] = SECRET
        os.environ["REGENT_ENVELOPE"] = json.dumps([str(self.envelope_dir)])
        for key in ("REGENT_EVENT_LOG", "REGENT_TURN_SECRET", "REGENT_ENVELOPE"):
            self.addCleanup(os.environ.pop, key, None)

    def _pre(self, tool, file_path, tool_use_id="t1"):
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool,
                              "tool_input": {"file_path": file_path},
                              "tool_use_id": tool_use_id})
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hookscript.main(["hook"], payload)
        return json.loads(buf.getvalue()) if buf.getvalue().strip() else {}

    def _post(self, tool, file_path, tool_use_id="t1"):
        payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": tool,
                              "tool_input": {"file_path": file_path},
                              "tool_use_id": tool_use_id})
        hookscript.main(["hook"], payload)

    def _decision(self, output):
        return output.get("hookSpecificOutput", {}).get("permissionDecision")

    def test_hook_allows_envelope_write(self):
        target = self.envelope_dir / "a.txt"
        out = self._pre("Write", str(target))
        self.assertIsNone(self._decision(out))  # allow = no deny decision
        events = read_events(self.log)
        self.assertEqual(events[-1]["decision"], "allow")

    def test_hook_denies_outside_envelope(self):
        out = self._pre("Write", str(self.root / "escape.txt"))
        self.assertEqual(self._decision(out), "deny")
        self.assertEqual(read_events(self.log)[-1]["decision"], "deny")

    def test_hook_denies_symlink_and_dotdot_escape(self):
        link = self.envelope_dir / "link"
        link.symlink_to(self.root)  # inside-envelope name, outside real target
        out = self._pre("Write", str(link / "pwned.txt"))
        self.assertEqual(self._decision(out), "deny")
        out = self._pre("Write", str(self.envelope_dir / ".." / "escape.txt"))
        self.assertEqual(self._decision(out), "deny")

    def test_hook_denies_bash_and_exec_tools(self):
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                              "tool_input": {"command": "rm -rf /"},
                              "tool_use_id": "b1"})
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hookscript.main(["hook"], payload)
        self.assertEqual(json.loads(buf.getvalue())["hookSpecificOutput"]
                         ["permissionDecision"], "deny")

    def test_hook_allows_read_only_tools(self):
        out = self._pre("Read", str(self.root / "anything.txt"))
        self.assertEqual(out, {})  # no deny, no event required

    def test_hook_error_fails_closed(self):
        del os.environ["REGENT_ENVELOPE"]  # force an internal error
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write",
                              "tool_input": {"file_path": "x"}, "tool_use_id": "e1"})
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hookscript.main(["hook"], payload)
        self.assertEqual(json.loads(buf.getvalue())["hookSpecificOutput"]
                         ["permissionDecision"], "deny")

    def test_pre_post_correlated_by_tool_use_id(self):
        target = self.envelope_dir / "b.txt"
        self._pre("Write", str(target), tool_use_id="xyz")
        target.write_text("content", encoding="utf-8")
        self._post("Write", str(target), tool_use_id="xyz")
        events = read_events(self.log)
        pre = next(e for e in events if e["kind"] == "pre")
        post = next(e for e in events if e["kind"] == "post")
        self.assertEqual(pre["tool_use_id"], post["tool_use_id"])
        self.assertIsNotNone(post["content_sha256"])

    # -- chain + terminal seal --------------------------------------------

    def _seal(self):
        append_terminal_seal(self.log, SECRET)

    def test_chain_verifies_clean_log_with_terminal_seal(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        self._seal()
        events = verify_chain(self.log, SECRET)
        self.assertEqual(events[-1]["kind"], "__regent_terminal_seal__")

    def test_missing_terminal_seal_is_tampered(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        with self.assertRaises(ChainError):
            verify_chain(self.log, SECRET)  # no seal appended

    def test_chain_detects_edit(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        self._seal()
        lines = self.log.read_text().splitlines()
        tampered = json.loads(lines[0])
        tampered["paths"] = ["/etc/passwd"]  # edit the body, keep the hmac
        lines[0] = json.dumps(tampered, sort_keys=True)
        self.log.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ChainError):
            verify_chain(self.log, SECRET)

    def test_chain_detects_removal(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        self._pre("Write", str(self.envelope_dir / "b"))
        self._seal()
        lines = self.log.read_text().splitlines()
        del lines[1]  # drop a middle event
        self.log.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ChainError):
            verify_chain(self.log, SECRET)

    def test_chain_detects_last_event_removal(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        self._seal()
        lines = self.log.read_text().splitlines()
        del lines[-1]  # drop the terminal seal
        self.log.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ChainError):
            verify_chain(self.log, SECRET)

    def test_chain_detects_injection(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        self._seal()
        lines = self.log.read_text().splitlines()
        forged = {"kind": "pre", "tool": "Write", "seq": 1,
                  "paths": ["/evil"], "decision": "allow", "hmac": "deadbeef"}
        lines.insert(1, json.dumps(forged, sort_keys=True))
        self.log.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ChainError):
            verify_chain(self.log, SECRET)

    def test_chain_detects_reorder(self):
        self._pre("Write", str(self.envelope_dir / "a"))
        self._pre("Write", str(self.envelope_dir / "b"))
        self._seal()
        lines = self.log.read_text().splitlines()
        lines[0], lines[1] = lines[1], lines[0]
        self.log.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ChainError):
            verify_chain(self.log, SECRET)

    def test_concurrent_append_flock_serialized(self):
        def worker(log, secret, envelope, n):
            os.environ["REGENT_EVENT_LOG"] = log
            os.environ["REGENT_TURN_SECRET"] = secret
            os.environ["REGENT_ENVELOPE"] = envelope
            for i in range(10):
                hookscript._append_event({"kind": "pre", "tool": "Write",
                                          "worker": n, "i": i, "paths": [],
                                          "decision": "allow"})

        args = (str(self.log), SECRET, json.dumps([str(self.envelope_dir)]))
        procs = [mp.Process(target=worker, args=(*args, n)) for n in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=15)
        events = read_events(self.log)
        self.assertEqual(len(events), 40)  # no lost/torn lines
        self.assertEqual([e["seq"] for e in events], list(range(40)))  # no fork
        append_terminal_seal(self.log, SECRET)
        verify_chain(self.log, SECRET)  # chain still verifies


if __name__ == "__main__":
    unittest.main()
