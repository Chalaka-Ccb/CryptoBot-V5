import unittest
from unittest.mock import Mock
from live.bitget_safety_supervisor import BitgetSafetySupervisor


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.r = Mock()
        self.r.inspect.return_value = Mock(client_id='abc', status='PROTECTED_SNAPSHOT_UNVERIFIED_HISTORY', emergency_attention=False)
        self.e = Mock()
        self.e.unresolved.return_value = []
        self.j = Mock()
        self.j.unresolved.return_value = []
        self.s = BitgetSafetySupervisor(self.r, self.e, self.j)
        self.args = dict(plan_order_id='p1', since_ms=1000, until_ms=2000)

    def test_protected_snapshot_never_unlocks(self):
        x = self.s.check_once('abc', **self.args)
        self.assertTrue(x.entry_blocked)
        self.assertFalse(x.live_execution_authorized)
        self.e.handle.assert_not_called()

    def test_unprotected_fill_creates_incident(self):
        self.r.inspect.return_value.status = 'FILLED_PROTECTION_UNVERIFIED'
        self.r.inspect.return_value.emergency_attention = True
        x = self.s.check_once('abc', **self.args)
        self.assertTrue(x.incident_recorded)
        self.e.handle.assert_called_once()

    def test_api_failure_creates_incident(self):
        self.r.inspect.side_effect = TimeoutError('exchange timeout')
        x = self.s.check_once('abc', **self.args)
        self.assertEqual(x.status, 'RECONCILIATION_ERROR')
        self.e.handle.assert_called_once()

    def test_persistence_failure_raises(self):
        self.r.inspect.side_effect = TimeoutError()
        self.e.handle.side_effect = OSError('disk full')
        with self.assertRaises(RuntimeError):
            self.s.check_once('abc', **self.args)

    def test_existing_incident_never_rechecks_as_clean(self):
        self.e.unresolved.return_value = ['abc']
        x = self.s.check_once('abc', **self.args)
        self.assertEqual(x.status, 'PERSISTED_INCIDENT')
        self.r.inspect.assert_not_called()

    def test_identity_mismatch_is_incident(self):
        self.r.inspect.return_value.client_id = 'other'
        self.assertEqual(self.s.check_once('abc', **self.args).status, 'RECONCILIATION_ERROR')

    def test_account_snapshot_zero_still_blocked(self):
        g = Mock()
        g.connect.return_value = {'id':'SOLUSDT', 'swap':True, 'linear':True}
        g.fetch_positions.return_value = []
        g.exchange.has = {'fetchOpenOrders':True}
        g.exchange.fetch_open_orders.return_value = []
        inspector = Mock()
        inspector.fetch_all.return_value = []
        result = self.s.check_account_snapshot(g, inspector)
        self.assertTrue(result['entry_blocked'])
        self.assertFalse(result['live_execution_authorized'])

    def test_account_snapshot_detects_exposure(self):
        g = Mock()
        g.connect.return_value = {'id':'SOLUSDT', 'swap':True, 'linear':True}
        g.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts':1}]
        g.exchange.has = {'fetchOpenOrders':True}
        g.exchange.fetch_open_orders.return_value = []
        inspector = Mock()
        inspector.fetch_all.return_value = []
        self.assertEqual(self.s.check_account_snapshot(g, inspector)['open_positions'], 1)

    def test_invalid_position_rejected(self):
        g = Mock()
        g.connect.return_value = {'id':'SOLUSDT', 'swap':True, 'linear':True}
        g.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts':float('nan')}]
        with self.assertRaises(RuntimeError):
            self.s.check_account_snapshot(g, Mock())

if __name__ == '__main__':
    unittest.main()
