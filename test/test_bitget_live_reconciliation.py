import unittest
from unittest.mock import Mock
from live.bitget_live_reconciliation import BitgetLiveReconciler


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.gateway=Mock()
        self.gateway.connect.return_value={'id':'SOLUSDT','swap':True,'linear':True}
        self.gateway.fetch_positions.return_value=[]
        self.journal=Mock()
        self.journal.get.return_value={'intent':Mock(symbol='SOL/USDT:USDT',client_id='abc'),
                                       'status':'acknowledged','exchange_order_id':'123'}
        self.orders=Mock()
        self.orders.fetch_order.return_value=Mock(client_id='abc',status='open',filled=0)
        self.orders.fetch_open_orders.return_value=[]
        self.plans=Mock()
        self.plans.fetch_all.return_value=[]
        self.reader=BitgetLiveReconciler(self.gateway,self.journal,self.orders,self.plans)

    def test_matched_order_still_not_authorized(self):
        report=self.reader.inspect('abc')
        self.assertEqual(report.exchange_order_id,'123')
        self.assertTrue(report.requires_manual_review)
        self.assertFalse(report.live_execution_authorized)

    def test_mismatched_client_id_rejected(self):
        self.orders.fetch_order.return_value.client_id='wrong'
        with self.assertRaises(RuntimeError):self.reader.inspect('abc')

    def test_missing_order_id_is_not_assumed_flat(self):
        self.journal.get.return_value['exchange_order_id']=None
        report=self.reader.inspect('abc')
        self.assertIsNone(report.order_status)
        self.assertTrue(report.requires_manual_review)

    def test_position_detected(self):
        self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','contracts':1}]
        self.assertEqual(self.reader.inspect('abc').open_positions,1)

    def test_unreliable_position_rejected(self):
        self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','contracts':float('nan')}]
        with self.assertRaises(RuntimeError):self.reader.inspect('abc')

    def test_wrong_market_rejected(self):
        self.gateway.connect.return_value['id']='BTCUSDT'
        with self.assertRaises(RuntimeError):self.reader.inspect('abc')


if __name__=='__main__':
    unittest.main()
