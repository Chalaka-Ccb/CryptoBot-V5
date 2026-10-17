import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from live.bitget_submission_gate import BitgetSubmissionGate
from live.live_order_lifecycle import OrderIntent


class SubmissionGateTests(unittest.TestCase):
    def setUp(self):
        self.exchange = Mock()
        self.gateway = SimpleNamespace(
            config=SimpleNamespace(symbol='SOL/USDT:USDT', strategy='bollinger_channel_rebound'),
            exchange=self.exchange)
        self.guard = Mock()
        self.intent = OrderIntent('safe-001', 'SOL/USDT:USDT', 'long', 1.0, 100.0, 99.0, 103.0)
        self.guard.prepare_intent.return_value = SimpleNamespace(
            intent=self.intent, checked_ordinary_orders=True,
            checked_positions=True, checked_plan_orders=True)
        self.gate = BitgetSubmissionGate(self.gateway, self.guard)

    def test_preview_is_offline_and_disabled(self):
        preview = self.gate.preview(self.intent)
        self.assertFalse(preview.execution_enabled)
        self.assertEqual(preview.margin_mode, 'isolated')
        self.assertEqual(preview.position_mode, 'one_way')
        self.guard.prepare_intent.assert_called_once_with(self.intent)
        self.exchange.assert_not_called()

    def test_guard_failure_blocks_preview(self):
        self.guard.prepare_intent.side_effect = RuntimeError('Pending plan order')
        with self.assertRaisesRegex(RuntimeError, 'Pending plan'):
            self.gate.preview(self.intent)

    def test_incomplete_checks_block_preview(self):
        self.guard.prepare_intent.return_value.checked_plan_orders = False
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            self.gate.preview(self.intent)

    def test_no_exchange_writes(self):
        for method in (self.gate.submit_order, self.gate.cancel_order, self.gate.amend_protection):
            with self.assertRaisesRegex(RuntimeError, 'WRITE LOCK'):
                method(self.intent)
        self.exchange.assert_not_called()

    def test_rejects_other_strategy(self):
        self.gateway.config.strategy = 'fffd'
        with self.assertRaisesRegex(RuntimeError, 'Unsupported strategy'):
            self.gate.preview(self.intent)


if __name__ == '__main__':
    unittest.main()
