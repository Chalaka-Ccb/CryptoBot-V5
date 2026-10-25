from datetime import datetime, timezone, timedelta
from typing import Any
from backtesting.market_data import BacktestMarketData
import ccxt

from core.models.candle import Candle


class ExchangeDataLoader:
    def __init__(
        self,
        exchange_name: str,
        market_type: str = "swap",
    ):
        if not hasattr(ccxt, exchange_name):
            raise ValueError(
                f"Unsupported CCXT exchange: {exchange_name}"
            )

        exchange_class = getattr(ccxt, exchange_name)

        self.exchange = exchange_class({
            "enableRateLimit": True,
            "options": {
                "defaultType": market_type,
            },
        })

    def load_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 1000,
    ) -> list[Candle]:

        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        self._validate_exchange(symbol, timeframe)

        raw_candles = self.exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        candles = self._convert_candles(raw_candles)

        return self._remove_incomplete_candle(candles)

    def load_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        candles: int,
    ) -> list[Candle]:

        if candles <= 0:
            raise ValueError(
                "candles must be greater than 0"
            )

        self._validate_exchange(symbol, timeframe)

        timeframe_ms = self.exchange.parse_timeframe(
            timeframe
        ) * 1000

        batch_size = 1000

        all_raw_candles: list[list[Any]] = []

        # Start from the most recent available candle.
        latest = self.exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=1,
        )

        if not latest:
            return []

        since = latest[0][0] - (
            candles * timeframe_ms
        )

        while len(all_raw_candles) < candles:

            remaining = candles - len(all_raw_candles)

            fetch_limit = min(
                batch_size,
                remaining,
            )

            batch = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=fetch_limit,
            )

            if not batch:
                break

            all_raw_candles.extend(batch)

            last_timestamp = batch[-1][0]

            next_since = (
                last_timestamp + timeframe_ms
            )

            if next_since <= since:
                break

            since = next_since

            if len(batch) < fetch_limit:
                break

        # Remove duplicate timestamps.
        unique_candles = {}

        for raw_candle in all_raw_candles:
            unique_candles[raw_candle[0]] = raw_candle

        sorted_raw_candles = sorted(
            unique_candles.values(),
            key=lambda candle: candle[0],
        )

        candles_result = self._convert_candles(
            sorted_raw_candles
        )

        # Keep only requested number.
        candles_result = candles_result[-candles:]

        # Never backtest using an unfinished candle.
        return self._remove_incomplete_candle(
            candles_result
        )

    def _validate_exchange(
        self,
        symbol: str,
        timeframe: str,
    ) -> None:

        if not self.exchange.has.get("fetchOHLCV"):
            raise ValueError(
                f"{self.exchange.id} does not support "
                "OHLCV data"
            )

        self.exchange.load_markets()

        if symbol not in self.exchange.markets:
            raise ValueError(
                f"Symbol {symbol} is not available on "
                f"{self.exchange.id}"
            )

        supported_timeframes = (
            self.exchange.timeframes or {}
        )

        if (
            supported_timeframes
            and timeframe not in supported_timeframes
        ):
            raise ValueError(
                f"Timeframe {timeframe} is not supported "
                f"by {self.exchange.id}"
            )

    @staticmethod
    def _convert_candles(
        raw_candles: list[list[Any]],
    ) -> list[Candle]:

        candles = []

        for raw_candle in raw_candles:

            timestamp_ms = raw_candle[0]

            timestamp = datetime.fromtimestamp(
                timestamp_ms / 1000,
                tz=timezone.utc,
            )

            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=float(raw_candle[1]),
                    high=float(raw_candle[2]),
                    low=float(raw_candle[3]),
                    close=float(raw_candle[4]),
                    volume=float(raw_candle[5]),
                )
            )

        candles.sort(
            key=lambda candle: candle.timestamp
        )

        return candles

    @staticmethod
    def _remove_incomplete_candle(
        candles: list[Candle],
    ) -> list[Candle]:

        if len(candles) <= 1:
            return candles

        return candles[:-1]

    def load_market_data(
            self,
            symbol: str,
            candles: int = 2500,
    ) -> BacktestMarketData:

        candles_15m = self.load_historical_candles(
            symbol=symbol,
            timeframe="15m",
            candles=candles,
        )

        candles_5m = self.load_historical_candles(
            symbol=symbol,
            timeframe="5m",
            candles=candles * 3,
        )

        return BacktestMarketData(
            symbol=symbol,
            candles_15m=candles_15m,
            candles_5m=candles_5m,
        )
    def load_dated_5m_market_data(self, symbol, start, end, warmup_candles=250):
        """Load [start,end) in UTC, with warm-up bars before start."""
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("UTC timezone-aware dates required")
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)
        if not start < end <= datetime.now(timezone.utc):
            raise ValueError("Invalid historical interval")
        if end - start > timedelta(days=30):
            raise ValueError("Maximum test interval is 30 days")
        if warmup_candles < 200:
            raise ValueError("EMA200 requires at least 200 warmup candles")
        if any(dt.second or dt.microsecond or dt.minute % 5 for dt in (start, end)):
            raise ValueError("Dates must align to 5m candle boundaries")
        self._validate_exchange(symbol, "5m")
        step = 300000
        first = int(start.timestamp() * 1000) - warmup_candles * step
        last = int(end.timestamp() * 1000)
        raw = {}
        since = first
        while since < last:
            limit = min(1000, (last - since + step - 1) // step)
            batch = self.exchange.fetch_ohlcv(
                symbol=symbol, timeframe="5m", since=since, limit=limit
            )
            if not batch:
                raise RuntimeError(f"No candles returned from {since}")
            for item in batch:
                if first <= item[0] < last:
                    raw[item[0]] = item
            next_since = batch[-1][0] + step
            if next_since <= since:
                raise RuntimeError("Pagination stalled")
            since = next_since
        timestamps = range(first, last, step)
        missing = next((t for t in timestamps if t not in raw), None)
        if missing is not None:
            raise RuntimeError(f"Missing 5m candle at {missing}")
        return BacktestMarketData(
            symbol=symbol, candles_15m=[],
            candles_5m=self._convert_candles([raw[t] for t in timestamps])
        )
