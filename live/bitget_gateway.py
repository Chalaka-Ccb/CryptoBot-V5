"""Read-only Bitget USDT perpetual gateway for Live V1.

No order methods are exposed by this adapter. Never store API credentials in Git.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import os

from core.models.candle import Candle
from live.config import LiveConfig
from risk.validation import finite_number


@dataclass(frozen=True)
class BalanceSnapshot:
    free_usdt: float
    total_usdt: float
    used_usdt: float
    timestamp: datetime


class BitgetGateway:
    def __init__(self, config: LiveConfig, exchange=None):
        if config.exchange != "bitget":
            raise ValueError("BitgetGateway only supports Bitget")
        self.config = config
        if exchange is None:
            import ccxt
            exchange = ccxt.bitget({
                "apiKey": os.getenv("BITGET_API_KEY", ""),
                "secret": os.getenv("BITGET_API_SECRET", ""),
                "password": os.getenv("BITGET_API_PASSPHRASE", ""),
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            })
        self.exchange = exchange
        self._market = None

    def connect(self):
        markets = self.exchange.load_markets()
        market = markets.get(self.config.symbol)
        if not market or not market.get("swap") or not market.get("linear") or market.get("settle") != "USDT":
            raise ValueError("Expected an active USDT-settled linear swap market")
        if market.get("active") is False:
            raise ValueError("Bitget market is inactive")
        self._market = market
        return market

    def fetch_closed_candles(self, timeframe: str, limit: int = 250) -> list[Candle]:
        if timeframe not in ("5m", "15m"):
            raise ValueError("Only 5m and 15m are supported")
        if not 30 <= limit <= 1000:
            raise ValueError("limit must be between 30 and 1000")
        if self._market is None:
            self.connect()
        raw = self.exchange.fetch_ohlcv(self.config.symbol, timeframe=timeframe, limit=limit)
        interval_ms = self.exchange.parse_timeframe(timeframe) * 1000
        now_ms = self.exchange.milliseconds()
        candles = {}
        for record in raw:
            if len(record) < 6:
                raise ValueError("Malformed OHLCV record")
            start_ms = int(record[0])
            if start_ms + interval_ms > now_ms:
                continue  # Never evaluate an incomplete candle
            o, h, l, c, v = (finite_number(name, value) for name, value in zip(
                ("open", "high", "low", "close", "volume"), record[1:6]))
            if min(o, h, l, c) <= 0 or v < 0 or l > min(o, c) or h < max(o, c):
                raise ValueError("Invalid OHLCV values")
            candles[start_ms] = Candle(datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc), o, h, l, c, v)
        return [candles[k] for k in sorted(candles)]

    def fetch_available_balance(self) -> BalanceSnapshot:
        if self._market is None:
            self.connect()
        if not all((os.getenv("BITGET_API_KEY"), os.getenv("BITGET_API_SECRET"), os.getenv("BITGET_API_PASSPHRASE"))):
            raise RuntimeError("Set BITGET_API_KEY, BITGET_API_SECRET, and BITGET_API_PASSPHRASE locally")
        response = self.exchange.fetch_balance({"type": "swap"})
        usdt = response.get("USDT", {})
        free = finite_number("USDT free", usdt.get("free"))
        total = finite_number("USDT total", usdt.get("total"))
        used = finite_number("USDT used", usdt.get("used"))
        if min(free, total, used) < 0 or free > total or used > total:
            raise ValueError("Inconsistent USDT balance response")
        return BalanceSnapshot(free, total, used, datetime.now(timezone.utc))

    def fetch_positions(self):
        """Return raw exchange positions for later reconciliation; never submit orders."""
        if self._market is None:
            self.connect()
        return self.exchange.fetch_positions([self.config.symbol], {"type": "swap"})
