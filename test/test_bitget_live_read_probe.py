import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from live.bitget_live_read_probe import BitgetLiveReadProbe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Mock()
        self.gateway.connect.return_value = dict(id='SOLUSDT', swap=True, linear=True)
        self.gateway.fetch_positions.return_value = []
        self.gateway.exchange.has = {'fetchOpenOrders':True}
        self.gateway.exchange.fetch_open_orders.return_value = []
        self.inspector = Mock()
        self.inspector.fetch_all.return_value = []
        self.probe = BitgetLiveReadProbe(self.gateway, self.inspector)

    def test_empty_account(self):
        r = self.probe.run()
        self.assertEqual(r.open_positions, 0)
        self.assertFalse(r.live_execution_authorized)
        self.assertFalse(r.account_mode_verified)

    def test_existing_position_count(self):
        self.gateway.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts':2.0}]
        self.assertEqual(self.probe.run().open_positions, 1)

    def test_existing_orders_count(self):
        self.gateway.exchange.fetch_open_orders.return_value = [{}]
        self.assertEqual(self.probe.run().ordinary_open_orders, 1)

    def test_existing_plans_count(self):
        self.inspector.fetch_all.return_value = [object()]
        self.assertEqual(self.probe.run().pending_plan_orders, 1)

    def test_invalid_position_fails(self):
        self.gateway.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts':None}]
        with self.assertRaises(RuntimeError): self.probe.run()

    def test_failed_plan_query_fails(self):
        self.inspector.fetch_all.side_effect = RuntimeError('API unavailable')
        with self.assertRaises(RuntimeError): self.probe.run()

    def test_missing_open_order_support_fails(self):
        self.gateway.exchange.has = {'fetchOpenOrders':False}
        with self.assertRaises(RuntimeError): self.probe.run()


if __name__ == '__main__':
    unittest.main()
