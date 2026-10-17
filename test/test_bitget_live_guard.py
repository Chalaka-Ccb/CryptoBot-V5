import unittest
from unittest.mock import Mock
from live.bitget_live_guard import BitgetLiveGuard
from live.live_order_lifecycle import OrderIntent


def intent():
    return OrderIntent('cbv5-guard-001', 'SOL/USDT:USDT', 'long', 1, 100, 99, 103)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.orders = Mock(unsafe=True)
        self.plans = Mock(unsafe=True)
        self.guard = BitgetLiveGuard(Mock(), self.orders, self.plans)

    def test_flat_passes_both_inspectors(self):
        result = self.guard.prepare_intent(intent())
        self.assertTrue(result.checked_plan_orders)
        self.orders.assert_flat_for_new_entry.assert_called_once()
        self.plans.assert_no_pending_plans.assert_called_once()

    def test_ordinary_orders_block_plans_check(self):
        self.orders.assert_flat_for_new_entry.side_effect = RuntimeError('ordinary order')
        with self.assertRaises(RuntimeError):
            self.guard.prepare_intent(intent())
        self.plans.assert_no_pending_plans.assert_not_called()

    def test_plan_orders_block(self):
        self.plans.assert_no_pending_plans.side_effect = RuntimeError('plan order')
        with self.assertRaises(RuntimeError):
            self.guard.prepare_intent(intent())

    def test_bad_intent_rejected(self):
        with self.assertRaises(TypeError):
            self.guard.prepare_intent(object())

    def test_live_write_always_disabled(self):
        with self.assertRaisesRegex(RuntimeError, 'DISABLED'):
            self.guard.submit_order()


if __name__ == '__main__':
    unittest.main()
