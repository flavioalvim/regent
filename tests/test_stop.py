"""Directed tests for stop-request representation/transitions (PLAN-001 STEP-03)."""

import tempfile
import unittest
from pathlib import Path

from regent.protocol.audit import AuditLog
from regent.protocol.control import (ControlStore, NotLockOwner, initial_control)
from regent.protocol.stop import (read_valid_stop_request, record_stop_request,
                                  suspend_activity)

TOKEN = "token-current"


class StopRequestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.audit = AuditLog(root / "audit.jsonl")
        self.store = ControlStore(root / "control.json", self.audit)
        self.store.seed()
        self._activate()

    def _activate(self, *, activity_id="PLAN-001", epoch=1, token=TOKEN):
        def fn(body):
            body["activity"] = {"type": "build", "id": activity_id, "epoch": epoch,
                                "state": "ACTIVE", "suspension": None,
                                "turn": {"owner": "executor", "token": token,
                                         "acquired_at": "2026-01-01T00:00:00+00:00"}}
            return body
        self.store.mutate(fn)

    def test_stop_request_linked_and_readable(self):
        recorded = record_stop_request(self.store, turn_token=TOKEN)
        request = read_valid_stop_request(self.store)
        self.assertEqual(request["id"], recorded["id"])
        self.assertEqual(request["activity_id"], "PLAN-001")
        self.assertEqual(request["activity_epoch"], 1)
        again = record_stop_request(self.store, turn_token=TOKEN)  # idempotent
        self.assertEqual(again["id"], recorded["id"])

    def test_mediator_stop_request_null_token_valid(self):
        record_stop_request(self.store, turn_token=None)
        self.assertIsNotNone(read_valid_stop_request(self.store))
        self._rotate_turn("token-after-takeover")  # mediator channel survives takeover
        self.assertIsNotNone(read_valid_stop_request(self.store))

    def test_stale_stop_request_discarded_with_audit(self):
        record_stop_request(self.store, turn_token=TOKEN)
        self._activate(activity_id="PLAN-002", epoch=2)  # activity changed
        self.assertIsNone(read_valid_stop_request(self.store))
        self.assertIsNone(self.store.load()["stop_request"])
        events = [r for r in self.audit.read_all() if r["event"] == "stop_request_discarded"]
        self.assertEqual(len(events), 1)

    def test_stop_request_old_turn_token_stale_after_takeover(self):
        record_stop_request(self.store, turn_token=TOKEN)
        self._rotate_turn("token-after-takeover")
        self.assertIsNone(read_valid_stop_request(self.store))
        events = [r for r in self.audit.read_all() if r["event"] == "stop_request_discarded"]
        self.assertEqual(len(events), 1)

    def test_suspend_requires_full_payload(self):
        with self.assertRaises(NotLockOwner):
            suspend_activity(self.store, turn_token="wrong-token",
                             checkpoint="STEP-02", reason="owner asked")
        applied = suspend_activity(self.store, turn_token=TOKEN,
                                   checkpoint="STEP-02", reason="owner asked",
                                   in_flight="advisor consultation")
        self.assertTrue(applied)
        activity = self.store.load()["activity"]
        self.assertEqual(activity["state"], "SUSPENDED")
        self.assertIsNone(activity["turn"])
        suspension = activity["suspension"]
        for field in ("previous_state", "checkpoint", "owning_turn", "in_flight",
                      "reason", "at"):
            self.assertIn(field, suspension)
        self.assertEqual(suspension["owning_turn"], TOKEN)

    def test_transitions_idempotent(self):
        first = record_stop_request(self.store, turn_token=TOKEN)
        version_after_record = self.store.load()["version"]
        again = record_stop_request(self.store, turn_token=TOKEN)
        self.assertEqual(again["id"], first["id"])
        self.assertEqual(self.store.load()["version"], version_after_record)  # true no-op

        self.assertTrue(suspend_activity(self.store, turn_token=TOKEN,
                                         checkpoint="STEP-02", reason="stop"))
        self.assertIsNone(self.store.load()["stop_request"])  # consumed
        version_after_suspend = self.store.load()["version"]
        self.assertFalse(suspend_activity(self.store, turn_token=TOKEN,
                                          checkpoint="STEP-02", reason="stop"))
        self.assertEqual(self.store.load()["version"], version_after_suspend)  # true no-op
        with self.assertRaises(NotLockOwner):  # re-apply demands the suspending turn
            suspend_activity(self.store, turn_token="another-token",
                             checkpoint="STEP-02", reason="stop")
        self.assertEqual(self.store.load()["activity"]["state"], "SUSPENDED")

    def _rotate_turn(self, new_token):
        def fn(body):
            body["activity"]["turn"]["token"] = new_token
            return body
        self.store.mutate(fn)


if __name__ == "__main__":
    unittest.main()
