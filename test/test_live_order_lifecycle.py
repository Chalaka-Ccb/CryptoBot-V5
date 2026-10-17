import unittest
from live.live_order_lifecycle import OfflineOrderLifecycle, OrderIntent, OrderState


def intent(client_id='cbv5-test-001'):
    return OrderIntent(client_id, 'SOL/USDT:USDT', 'long', 2.0, 100, 99, 103)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.life = OfflineOrderLifecycle()
        self.life.plan(intent())

    def test_no_exchange_order_submission_methods(self):
        self.assertFalse(hasattr(self.life, 'create_order'))
        self.assertEqual(self.life.state, OrderState.PENDING)

    def test_ack_is_not_fill(self):
        self.life.acknowledge('cbv5-test-001', 'bitget-123')
        self.assertEqual(self.life.filled, 0)
        self.assertEqual(self.life.state, OrderState.PENDING)

    def test_partial_fill_requires_protection(self):
        self.life.report_fill('cbv5-test-001', 1)
        self.assertEqual(self.life.state, OrderState.PARTIAL)
        self.life.report_protection('cbv5-test-001', 1, stop_confirmed=True, target_confirmed=True)
        self.assertEqual(self.life.state, OrderState.PROTECTED)
        self.life.report_fill('cbv5-test-001', 2)
        self.assertEqual(self.life.state, OrderState.FILLED_UNPROTECTED)

    def test_incomplete_protection_halts(self):
        self.life.report_fill('cbv5-test-001', 2)
        with self.assertRaises(RuntimeError):
            self.life.report_protection('cbv5-test-001', 1, stop_confirmed=True, target_confirmed=True)
        self.assertEqual(self.life.state, OrderState.HALTED)

    def test_nonmonotonic_fill_halts(self):
        self.life.report_fill('cbv5-test-001', 1)
        with self.assertRaises(RuntimeError):
            self.life.report_fill('cbv5-test-001', 0.5)
        self.assertEqual(self.life.state, OrderState.HALTED)

    def test_duplicate_id_rejected(self):
        self.life.cancel_unfilled('cbv5-test-001', exchange_confirmed=True)
        self.life.state = OrderState.READY  # offline manual reset only
        with self.assertRaises(RuntimeError):
            self.life.plan(intent())

    def test_cancel_requires_confirmation(self):
        with self.assertRaises(RuntimeError):
            self.life.cancel_unfilled('cbv5-test-001', exchange_confirmed=False)
        self.assertEqual(self.life.state, OrderState.HALTED)

    def test_ack_conflict_halts(self):
        self.life.acknowledge('cbv5-test-001', 'one')
        with self.assertRaises(RuntimeError):
            self.life.acknowledge('cbv5-test-001', 'two')
        self.assertEqual(self.life.state, OrderState.HALTED)

    def test_invalid_intent(self):
        with self.assertRaises(ValueError):
            OrderIntent('bad', 'SOL/USDT:USDT', 'long', 1, 100, 101, 103)


if __name__ == '__main__':
    unittest.main()
