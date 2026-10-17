import unittest
from unittest.mock import Mock
from decimal import Decimal
from live.bitget_trigger_history import BitgetTriggerHistoryReader


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.g = Mock()
        self.g.config.symbol = 'SOL/USDT:USDT'
        self.g.connect.return_value = {'id': 'SOLUSDT', 'swap': True, 'linear': True}
        self.api = Mock(return_value={'code': '00000', 'data': {'entrustedList': [], 'endId': None}})
        setattr(self.g.exchange, BitgetTriggerHistoryReader.METHOD, self.api)
        self.reader = BitgetTriggerHistoryReader(self.g)

    def row(self, **kw):
        x = {'orderId': 'p1', 'clientOid': 'c1', 'symbol': 'SOLUSDT',
             'status': 'executed', 'triggerPrice': '120.5', 'executeOrderId': 'o1'}
        x.update(kw)
        return x

    def test_empty_history_is_not_trade_authorization(self):
        report = self.reader.fetch()
        self.assertEqual(report.items, ())
        self.assertFalse(report.live_execution_authorized)

    def test_explicit_parent_child_match(self):
        self.api.return_value['data']['entrustedList'] = [self.row()]
        item = self.reader.find_verified(plan_order_id='p1', client_id='c1')
        self.assertEqual(item.child_order_id, 'o1')
        self.assertEqual(item.trigger_price, Decimal('120.5'))

    def test_missing_child_not_inferred(self):
        self.api.return_value['data']['entrustedList'] = [self.row(executeOrderId=None)]
        item = self.reader.find_verified(plan_order_id='p1', client_id='c1')
        self.assertIsNone(item.child_order_id)

    def test_client_mismatch_rejected(self):
        self.api.return_value['data']['entrustedList'] = [self.row()]
        with self.assertRaises(RuntimeError):
            self.reader.find_verified(plan_order_id='p1', client_id='wrong')

    def test_duplicate_plan_rejected(self):
        self.api.return_value['data']['entrustedList'] = [self.row(), self.row()]
        with self.assertRaises(RuntimeError):
            self.reader.fetch()

    def test_api_failure_rejected(self):
        self.api.return_value = {'code': '99999', 'data': {}}
        with self.assertRaises(RuntimeError):
            self.reader.fetch()

    def test_full_page_without_cursor_rejected(self):
        self.api.return_value['data']['entrustedList'] = [self.row(orderId=f'p{i}') for i in range(100)]
        with self.assertRaises(RuntimeError):
            self.reader.fetch()

    def test_bad_symbol_rejected(self):
        self.api.return_value['data']['entrustedList'] = [self.row(symbol='BTCUSDT')]
        with self.assertRaises(RuntimeError):
            self.reader.fetch()

    def test_bad_trigger_rejected(self):
        self.api.return_value['data']['entrustedList'] = [self.row(triggerPrice='nan')]
        with self.assertRaises(RuntimeError):
            self.reader.fetch()


if __name__ == '__main__':
    unittest.main()
