import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from live.config import LiveConfig
from live.live_preflight import LivePreflight


class Exchange:
    precisionMode = 4
    has = {'fetchOpenOrders': True}
    def fetch_open_orders(self, symbol):
        return []


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.exchange = Exchange()
        self.gateway = Mock()
        self.gateway.config = LiveConfig()
        self.gateway.exchange = self.exchange
        self.gateway.connect.return_value = {
            'contract': True, 'contractSize': 1.0, 'precision': {'amount': 0.01},
            'limits': {'amount': {'min': 0.01}, 'cost': {'min': 5}},
        }
        self.gateway.fetch_positions.return_value = []
        self.gateway.fetch_available_balance.return_value = SimpleNamespace(free_usdt=100, total_usdt=100)
        self.signal = TradingSignal('bollinger_channel_rebound', SignalSide.LONG, 1,
                                    EntryTiming.BREAKOUT, 100, 99, 103)
        self.checker = LivePreflight(self.gateway)

    def test_plan_does_not_submit_orders(self):
        plan = self.checker.prepare(self.signal)
        self.assertGreater(plan.contracts, 0)
        self.assertLessEqual(plan.estimated_margin_usdt, 100)
        self.assertLessEqual(plan.max_loss_before_fees_usdt, 2)
        self.assertFalse(hasattr(self.exchange, 'create_order'))

    def test_zero_balance_fails(self):
        self.gateway.fetch_available_balance.return_value = SimpleNamespace(free_usdt=0, total_usdt=0)
        with self.assertRaises(RuntimeError):
            self.checker.prepare(self.signal)

    def test_existing_position_fails(self):
        self.gateway.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts': 1}]
        with self.assertRaises(RuntimeError):
            self.checker.prepare(self.signal)

    def test_open_order_fails(self):
        self.exchange.fetch_open_orders = lambda symbol: [{'id': 'existing'}]
        with self.assertRaises(RuntimeError):
            self.checker.prepare(self.signal)

    def test_missing_precision_fails(self):
        self.gateway.connect.return_value['precision'] = {}
        with self.assertRaises(RuntimeError):
            self.checker.prepare(self.signal)

    def test_risk_limit_fails(self):
        with self.assertRaises(ValueError):
            LivePreflight(self.gateway, risk_fraction=0.06)

    def test_wrong_strategy_fails(self):
        self.signal = TradingSignal('other', SignalSide.LONG, 1, EntryTiming.BREAKOUT, 100, 99, 103)
        with self.assertRaises(ValueError):
            self.checker.prepare(self.signal)


if __name__ == '__main__':
    unittest.main()
