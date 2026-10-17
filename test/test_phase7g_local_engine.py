import unittest
from unittest.mock import Mock
from live.phase7g_local_engine import LocalShadowSession,snapshot_is_clear

CLEAR=dict(open_positions=0,ordinary_open_orders=0,pending_plan_orders=0,
           unresolved_intents=0,unresolved_incidents=0,entry_blocked=True,
           live_execution_authorized=False)

class LocalShadowTests(unittest.TestCase):
    def setUp(self):
        self.gateway=Mock();self.inspector=Mock();self.supervisor=Mock();self.shadow=Mock()
        self.supervisor.check_account_snapshot.return_value=dict(CLEAR)
        self.shadow.tick.return_value=Mock(status='NO_SIGNAL',candle_timestamp='2026-10-17T00:00:00+00:00',proposal=None)
        self.session=LocalShadowSession(self.gateway,self.inspector,self.supervisor,self.shadow)
    def test_clear_snapshot(self):self.assertTrue(snapshot_is_clear(CLEAR))
    def test_unverified_authorization_rejected(self):
        self.assertFalse(snapshot_is_clear({**CLEAR,'live_execution_authorized':True}))
    def test_missing_field_rejected(self):
        self.assertFalse(snapshot_is_clear({k:v for k,v in CLEAR.items() if k!='pending_plan_orders'}))
    def test_boolean_counter_rejected(self):
        self.assertFalse(snapshot_is_clear({**CLEAR,'open_positions':False}))
    def test_pending_plan_blocks(self):
        self.supervisor.check_account_snapshot.return_value={**CLEAR,'pending_plan_orders':1}
        self.assertEqual(self.session.tick()['shadow_status'],'BLOCKED_ACCOUNT_STATE')
        self.shadow.tick.assert_not_called()
    def test_unresolved_incident_blocks(self):
        self.supervisor.check_account_snapshot.return_value={**CLEAR,'unresolved_incidents':1}
        self.assertEqual(self.session.tick()['shadow_status'],'BLOCKED_ACCOUNT_STATE')
    def test_clear_invokes_shadow(self):
        x=self.session.tick();self.assertEqual(x['shadow_status'],'NO_SIGNAL')
        self.assertFalse(x['live_execution_authorized'])
        self.assertTrue(self.shadow.safety_check())
    def test_error_clears_snapshot(self):
        self.session.tick()
        self.supervisor.check_account_snapshot.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):self.session.tick()
        self.assertFalse(self.shadow.safety_check())
    def test_run_catches_errors(self):
        self.supervisor.check_account_snapshot.side_effect=RuntimeError('offline')
        self.session.run(10,max_cycles=1)
        self.shadow.tick.assert_not_called()
    def test_interval_minimum(self):
        with self.assertRaises(ValueError):self.session.run(9,max_cycles=1)
if __name__=='__main__':unittest.main()
