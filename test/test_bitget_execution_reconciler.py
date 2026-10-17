import unittest
from unittest.mock import Mock
from live.bitget_execution_reconciler import BitgetExecutionReconciler

class Tests(unittest.TestCase):
    def setUp(self):
        self.journal=Mock()
        self.intent=Mock(client_id='abc',symbol='SOL/USDT:USDT',side='long',contracts=2)
        self.journal.get.return_value={'intent':self.intent,'status':'acknowledged'}
        self.triggers=Mock()
        self.triggers.find_verified.return_value=Mock(plan_order_id='p1',client_id='abc',child_order_id='o1')
        self.fills=Mock()
        self.fills.inspect.return_value=Mock(order_id='o1',amount=1)
        self.gateway=Mock()
        self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','side':'long','contracts':1}]
        self.protection=Mock()
        self.protection.check.return_value=Mock(filled_contracts='1')
        self.r=BitgetExecutionReconciler(self.journal,self.triggers,self.fills,self.gateway,self.protection)
        self.args=dict(plan_order_id='p1',since_ms=1000,until_ms=2000)
    def test_protected_snapshot_not_authorized(self):
        x=self.r.inspect('abc',**self.args)
        self.assertEqual(x.status,'PROTECTED_SNAPSHOT_UNVERIFIED_HISTORY')
        self.assertFalse(x.live_execution_authorized)
    def test_missing_child_never_assumed_canceled(self):
        self.triggers.find_verified.return_value.child_order_id=None
        x=self.r.inspect('abc',**self.args)
        self.assertEqual(x.status,'UNKNOWN_CHILD_ORDER')
        self.assertTrue(x.emergency_attention)
        self.fills.inspect.assert_not_called()
    def test_missing_protection_emergency(self):
        self.protection.check.side_effect=RuntimeError('No stop')
        x=self.r.inspect('abc',**self.args)
        self.assertEqual(x.status,'FILLED_PROTECTION_UNVERIFIED')
        self.assertTrue(x.emergency_attention)
    def test_fill_position_mismatch(self):
        self.gateway.fetch_positions.return_value=[]
        x=self.r.inspect('abc',**self.args)
        self.assertEqual(x.status,'POSITION_FILL_MISMATCH')
    def test_overfill_fails_closed(self):
        self.fills.inspect.return_value.amount=3
        with self.assertRaises(RuntimeError):self.r.inspect('abc',**self.args)
    def test_wrong_child_order_fails_closed(self):
        self.fills.inspect.return_value.order_id='wrong'
        with self.assertRaises(RuntimeError):self.r.inspect('abc',**self.args)
    def test_no_fills_not_proof_of_flat(self):
        self.fills.inspect.return_value.amount=0
        self.gateway.fetch_positions.return_value=[]
        x=self.r.inspect('abc',**self.args)
        self.assertEqual(x.status,'NO_CONFIRMED_FILL')
        self.assertFalse(x.live_execution_authorized)
    def test_conflicting_position_fails_closed(self):
        self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','side':'short','contracts':1}]
        with self.assertRaises(RuntimeError):self.r.inspect('abc',**self.args)
if __name__=='__main__':unittest.main()
