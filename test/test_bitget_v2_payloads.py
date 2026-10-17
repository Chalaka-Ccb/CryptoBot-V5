import unittest
from live.live_order_lifecycle import OrderIntent
from live.bitget_v2_payloads import BitgetV2PayloadBuilder


class PayloadTests(unittest.TestCase):
    def build(self, side):
        intent = OrderIntent('test-6t', 'SOL/USDT:USDT', side, 0.5, 100,
                             99 if side == 'long' else 101,
                             103 if side == 'long' else 97)
        return BitgetV2PayloadBuilder().build(intent)

    def test_long_entry_plan(self):
        b = self.build('long')
        self.assertEqual(b.entry.body['planType'], 'normal_plan')
        self.assertEqual(b.entry.body['side'], 'buy')
        self.assertEqual(b.entry.body['orderType'], 'market')
        self.assertNotIn('tradeSide', b.entry.body)
        self.assertFalse(b.executable)

    def test_short_entry_plan(self):
        b = self.build('short')
        self.assertEqual(b.entry.body['side'], 'sell')
        self.assertEqual(b.stop.body['holdSide'], 'short')

    def test_stop_and_target_endpoints(self):
        b = self.build('long')
        self.assertEqual(b.stop.endpoint, '/api/v2/mix/order/place-tpsl-order')
        self.assertEqual(b.target.body['planType'], 'profit_plan')
        self.assertEqual(b.stop.body['planType'], 'loss_plan')
        self.assertNotIn('side', b.stop.body)
        self.assertNotEqual(b.stop.body['clientOid'], b.target.body['clientOid'])

    def test_unique_client_ids(self):
        b = self.build('long')
        ids = [b.entry.body['clientOid'],b.stop.body['clientOid'],b.target.body['clientOid']]
        self.assertEqual(len(set(ids)),3)


if __name__ == '__main__':
    unittest.main()
