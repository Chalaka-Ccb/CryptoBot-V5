import unittest
from live.ledger import closed_trade_record


class LedgerTests(unittest.TestCase):
    def test_closed_long_after_fees(self):
        saved = {"side": "long", "qty": 1, "entry_ts": 100000, "timeframe": "5m"}
        fills = [
            {"side": "buy", "amount": 1, "price": 100, "timestamp": 101000,
             "fee": {"cost": 0.06, "currency": "USDT"}},
            {"side": "sell", "amount": 1, "price": 103, "timestamp": 102000,
             "fee": {"cost": 0.06, "currency": "USDT"}},
        ]
        result = closed_trade_record(saved, fills)
        self.assertAlmostEqual(result["gross_pnl"], 3)
        self.assertAlmostEqual(result["net_pnl"], 2.88)

    def test_missing_exit_is_not_profit(self):
        saved = {"side": "short", "qty": 2, "entry_ts": 100000}
        self.assertIsNone(closed_trade_record(saved, []))

    def test_missing_fee_is_not_estimated(self):
        saved = {"side": "long", "qty": 1, "entry_ts": 100000}
        fills = [{"side": "buy", "amount": 1, "price": 100, "timestamp": 101000},
                 {"side": "sell", "amount": 1, "price": 103, "timestamp": 102000}]
        self.assertIsNone(closed_trade_record(saved, fills))


if __name__ == "__main__":
    unittest.main()
