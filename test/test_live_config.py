import unittest
from live.config import LiveConfig
from risk.limits import QuantityLimits, RiskLimits
from risk.validation import finite_number


class LiveConfigTests(unittest.TestCase):
    def test_defaults_are_paper_only(self):
        config = LiveConfig()
        self.assertEqual(config.mode, "paper")
        self.assertEqual(config.symbol, "SOL/USDT:USDT")
        self.assertEqual(config.risk_limits().leverage, 5.0)

    def test_requested_maximums_are_configurable(self):
        config = LiveConfig(risk_percentage=0.05, leverage=15)
        self.assertEqual(config.risk_percentage, 0.05)
        self.assertEqual(config.leverage, 15)

    def test_rejects_excessive_risk_and_leverage(self):
        for kwargs in ({"risk_percentage": 0.051}, {"leverage": 16}, {"leverage": 0}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    LiveConfig(**kwargs)

    def test_single_symbol_and_strategy(self):
        for kwargs in ({"symbol": "BTC/USDT:USDT"}, {"strategy": "fffd"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    LiveConfig(**kwargs)

    def test_numeric_and_exchange_quantity_validation(self):
        with self.assertRaises(ValueError):
            finite_number("balance", float("nan"))
        with self.assertRaises(ValueError):
            QuantityLimits(minimum=2, maximum=1)
        with self.assertRaises(ValueError):
            RiskLimits(margin_reserve=-1)


if __name__ == "__main__":
    unittest.main()
