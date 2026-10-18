import unittest
from live.config import LiveConfig
from risk.limits import QuantityLimits, RiskLimits
from risk.validation import finite_number


class LiveConfigTests(unittest.TestCase):
    def test_defaults_are_demo_and_sonic(self):
        config = LiveConfig()
        self.assertTrue(config.demo)
        self.assertEqual(config.symbol, "SONIC/USDT:USDT")
        self.assertEqual(config.leverage, 12)
        self.assertEqual(config.risk_percentage, 0.05)
        with self.assertRaises(RuntimeError):
            config.require_trading_confirmation()

    def test_requested_maximums_are_configurable(self):
        config = LiveConfig(risk_percentage=0.02, leverage=5)
        self.assertEqual(config.risk_percentage, 0.02)
        self.assertEqual(config.leverage, 5)

    def test_rejects_excessive_risk_and_leverage(self):
        for kwargs in ({"risk_percentage": 0.051}, {"leverage": 16}, {"leverage": 0}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    LiveConfig(**kwargs)

    def test_single_symbol(self):
        with self.assertRaises(ValueError):
            LiveConfig(symbol="BTC/USDT:USDT")

    def test_numeric_and_exchange_quantity_validation(self):
        with self.assertRaises(ValueError):
            finite_number("balance", float("nan"))
        with self.assertRaises(ValueError):
            QuantityLimits(minimum=2, maximum=1)
        with self.assertRaises(ValueError):
            RiskLimits(margin_reserve=-1)


if __name__ == "__main__":
    unittest.main()
