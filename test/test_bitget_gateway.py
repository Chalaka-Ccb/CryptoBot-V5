import os
import unittest
from unittest.mock import patch
from live.bitget_gateway import BitgetGateway
from live.config import LiveConfig


class FakeExchange:
    def __init__(self):
        self.now = 1_800_000_000_000
        self.market = {"symbol": "SOL/USDT:USDT", "swap": True, "linear": True, "settle": "USDT", "active": True}
    def load_markets(self):
        return {"SOL/USDT:USDT": self.market}
    def parse_timeframe(self, timeframe):
        return {"5m": 300, "15m": 900}[timeframe]
    def milliseconds(self):
        return self.now
    def fetch_ohlcv(self, symbol, timeframe, limit):
        duration = self.parse_timeframe(timeframe) * 1000
        return [[self.now - 2*duration, 100, 102, 99, 101, 10], [self.now - duration//2, 101, 103, 100, 102, 10]]
    def fetch_balance(self, params):
        return {"USDT": {"free": 80, "total": 100, "used": 20}}
    def fetch_positions(self, symbols, params):
        return []


class BitgetGatewayTests(unittest.TestCase):
    def setUp(self):
        self.gateway = BitgetGateway(LiveConfig(), FakeExchange())
    def test_market_and_closed_candles(self):
        self.gateway.connect()
        candles = self.gateway.fetch_closed_candles("5m")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].close, 101)
    def test_invalid_timeframe(self):
        with self.assertRaises(ValueError):
            self.gateway.fetch_closed_candles("1m")
    def test_private_balance(self):
        with patch.dict(os.environ, {"BITGET_API_KEY": "test", "BITGET_API_SECRET": "test", "BITGET_API_PASSPHRASE": "test"}):
            balance = self.gateway.fetch_available_balance()
        self.assertEqual(balance.free_usdt, 80)
    def test_missing_credentials(self):
        with patch.dict(os.environ, {"BITGET_API_KEY": "", "BITGET_API_SECRET": "", "BITGET_API_PASSPHRASE": ""}):
            with self.assertRaises(RuntimeError):
                self.gateway.fetch_available_balance()
    def test_reject_inactive_market(self):
        self.gateway.exchange.market["active"] = False
        with self.assertRaises(ValueError):
            self.gateway.connect()


if __name__ == "__main__":
    unittest.main()
