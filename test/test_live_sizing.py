import unittest
from live.config import LiveConfig
from live.models import Balance
from live.sizing import size_trade
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from risk.limits import QuantityLimits

class SizingTests(unittest.TestCase):
    def test_12x_cap_and_5_percent_risk(self):
        signal = TradingSignal(strategy="bollinger_channel_rebound", side=SignalSide.LONG,
            candle_index=25, entry_timing=EntryTiming.BREAKOUT,
            trigger_price=100, stop_loss=99, take_profit=103)
        plan = size_trade(signal, "5m", 100, Balance(1000, 1000),
            QuantityLimits(step=0.001, minimum=0.001), LiveConfig())
        self.assertAlmostEqual(plan.qty, 50.0)
        self.assertLessEqual(plan.qty * 100, 12000)
        self.assertEqual(plan.tp, 103)

    def test_wrong_strategy_rejected(self):
        signal = TradingSignal("fffd", SignalSide.LONG, 20, EntryTiming.BREAKOUT, 100, 99, 103)
        with self.assertRaises(ValueError):
            size_trade(signal, "5m", 100, Balance(1000, 1000), QuantityLimits(), LiveConfig())

if __name__ == "__main__":
    unittest.main()
