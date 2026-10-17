import unittest
from types import SimpleNamespace
from live.bitget_order_adapter import BitgetOrderAdapter
from live.live_order_lifecycle import OrderIntent


def order(**changes):
    data = dict(id='123', clientOrderId='cbv5-001', symbol='SOL/USDT:USDT', status='open',
                amount=2, filled=0.5, remaining=1.5, side='buy', reduceOnly=False)
    data.update(changes)
    return data


class FakeExchange:
    has = {'fetchOrder': True, 'fetchOpenOrders': True}
    def __init__(self):
        self.orders = []
        self.single = order()
    def fetch_order(self, order_id, symbol):
        return self.single
    def fetch_open_orders(self, symbol):
        return self.orders


class FakeGateway:
    def __init__(self):
        self.config = SimpleNamespace(symbol='SOL/USDT:USDT')
        self.exchange = FakeExchange()
        self._market = {'symbol': 'SOL/USDT:USDT'}
        self.positions = []
    def fetch_positions(self):
        return self.positions


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.gateway = FakeGateway()
        self.adapter = BitgetOrderAdapter(self.gateway)

    def test_normalize_partial(self):
        snap = self.adapter.normalize_order(order())
        self.assertEqual(snap.filled, 0.5)
        self.assertEqual(snap.remaining, 1.5)

    def test_fetch_order(self):
        self.assertEqual(self.adapter.fetch_order('123').order_id, '123')

    def test_wrong_id_rejected(self):
        with self.assertRaises(RuntimeError):
            self.adapter.fetch_order('different')

    def test_unknown_status_rejected(self):
        with self.assertRaises(RuntimeError):
            self.adapter.normalize_order(order(status='mystery'))

    def test_bad_quantity_rejected(self):
        with self.assertRaises(RuntimeError):
            self.adapter.normalize_order(order(remaining=2))

    def test_open_orders_rejected(self):
        self.gateway.exchange.orders = [order()]
        with self.assertRaises(RuntimeError):
            self.adapter.assert_flat_for_new_entry()

    def test_position_rejected(self):
        self.gateway.positions = [{'symbol': 'SOL/USDT:USDT', 'contracts': 1}]
        with self.assertRaises(RuntimeError):
            self.adapter.assert_flat_for_new_entry()

    def test_flat(self):
        self.assertTrue(self.adapter.assert_flat_for_new_entry())

    def test_intent_validation(self):
        intent = OrderIntent('cbv5-001', 'SOL/USDT:USDT', 'long', 2, 100, 99, 103)
        self.assertIs(self.adapter.validate_intent(intent), intent)

    def test_live_submission_disabled(self):
        with self.assertRaisesRegex(RuntimeError, 'DISABLED'):
            self.adapter.submit_order()

    def test_unsupported_fetch_order(self):
        self.gateway.exchange.has = {'fetchOrder': False, 'fetchOpenOrders': True}
        with self.assertRaises(RuntimeError):
            self.adapter.fetch_order('123')


if __name__ == '__main__':
    unittest.main()
