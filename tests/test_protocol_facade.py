"""Directed test for the protocol façade exports (PLAN-001 STEP-04)."""

import unittest

EXPECTED_SYMBOLS = (
    "AuditLog",
    "ControlSchemaError",
    "ControlStore",
    "LockHeld",
    "MutationMutexBusy",
    "NotLockOwner",
    "StaleLock",
    "TurnLock",
    "VersionConflict",
    "read_valid_stop_request",
    "record_stop_request",
    "suspend_activity",
)


class FacadeTest(unittest.TestCase):
    def test_facade_exports_all_symbols(self):
        import regent.protocol as protocol
        for symbol in EXPECTED_SYMBOLS:
            self.assertTrue(hasattr(protocol, symbol), f"missing export: {symbol}")
        self.assertEqual(sorted(protocol.__all__), sorted(EXPECTED_SYMBOLS))


if __name__ == "__main__":
    unittest.main()
