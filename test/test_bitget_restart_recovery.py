import unittest
from unittest.mock import Mock
from live.bitget_restart_recovery import BitgetRestartRecovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.journal=Mock()
        self.journal.unresolved.return_value=[]
        self.gateway=Mock()
        self.gateway.connect.return_value={'id':'SOLUSDT','swap':True,'linear':True}
        self.gateway.fetch_positions.return_value=[]
        self.gateway.exchange.has={'fetchOpenOrders':True}
        self.gateway.exchange.fetch_open_orders.return_value=[]
        self.inspector=Mock()
        self.inspector.fetch_all.return_value=[]
        self.reader=BitgetRestartRecovery(self.journal,self.gateway,self.inspector)

    def test_clean_snapshot_still_not_authorized(self):
        r=self.reader.check()
        self.assertFalse(r.manual_reconciliation_required)
        self.assertFalse(r.live_execution_authorized)

    def test_unresolved_journal_requires_manual_recovery(self):
        self.journal.unresolved.return_value=['entry1']
        self.assertTrue(self.reader.check().manual_reconciliation_required)

    def test_open_position_requires_manual_recovery(self):
        self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','contracts':1}]
        self.assertTrue(self.reader.check().manual_reconciliation_required)

    def test_pending_plan_requires_manual_recovery(self):
        self.inspector.fetch_all.return_value=[object()]
        self.assertTrue(self.reader.check().manual_reconciliation_required)

    def test_ordinary_order_requires_manual_recovery(self):
        self.gateway.exchange.fetch_open_orders.return_value=[object()]
        self.assertTrue(self.reader.check().manual_reconciliation_required)

    def test_invalid_position_rejected(self):
        self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','contracts':float('nan')}]
        with self.assertRaises(RuntimeError):self.reader.check()

    def test_unavailable_order_query_rejected(self):
        self.gateway.exchange.has={}
        with self.assertRaises(RuntimeError):self.reader.check()

    def test_wrong_market_rejected(self):
        self.gateway.connect.return_value['id']='BTCUSDT'
        with self.assertRaises(RuntimeError):self.reader.check()


if __name__=='__main__':
    unittest.main()
