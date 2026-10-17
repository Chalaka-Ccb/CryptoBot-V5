import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from live.bitget_emergency_controller import EmergencyController

class EmergencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'incidents.sqlite'
        self.journal=Mock()
        self.journal.unresolved.return_value=[]
        self.c=EmergencyController(self.path,self.journal)
        self.report=SimpleNamespace(client_id='abc',status='FILLED_PROTECTION_UNVERIFIED',position_amount='2')
    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()
    def test_incident_is_durable_and_blocks(self):
        self.c.handle(self.report)
        self.assertEqual(self.c.unresolved(),['abc'])
        with self.assertRaises(RuntimeError):self.c.assert_entry_blocked_if_unsafe()
        self.c.close()
        self.c=EmergencyController(self.path,self.journal)
        self.assertEqual(self.c.unresolved(),['abc'])
    def test_journal_halted(self):
        self.c.handle(self.report)
        self.journal.halt.assert_called_once_with('abc')
    def test_journal_failure_still_persists_incident(self):
        self.journal.halt.side_effect=RuntimeError('database busy')
        with self.assertRaises(RuntimeError):self.c.handle(self.report)
        self.assertEqual(self.c.unresolved(),['abc'])
    def test_safe_report_not_incident(self):
        self.report.status='PROTECTED_SNAPSHOT_UNVERIFIED_HISTORY'
        with self.assertRaises(ValueError):self.c.handle(self.report)
    def test_no_auto_close(self):
        self.c.handle(self.report)
        response=self.c.prepare_manual_response('abc')
        self.assertFalse(response['automatic_cancel_or_close'])
        self.assertFalse(response['live_execution_authorized'])
    def test_unknown_child_incident(self):
        self.report.status='UNKNOWN_CHILD_ORDER'
        self.c.handle(self.report)
        self.assertEqual(self.c.unresolved(),['abc'])
    def test_unresolved_journal_blocks(self):
        self.journal.unresolved.return_value=['old']
        with self.assertRaises(RuntimeError):self.c.assert_entry_blocked_if_unsafe()
    def test_no_incidents_no_journal_returns_only_local_check(self):
        self.assertTrue(self.c.assert_entry_blocked_if_unsafe())
    def test_duplicate_id_does_not_clear(self):
        self.c.handle(self.report)
        self.c.handle(self.report)
        self.assertEqual(self.c.unresolved(),['abc'])
if __name__=='__main__':unittest.main()
