from dataclasses import dataclass

from core.models.candle import Candle


@dataclass(frozen=True)
class BacktestMarketData:
    symbol: str
    candles_15m: list[Candle]
    candles_5m: list[Candle]
    candles_1m: list[Candle] | None = None

    @property
    def start_time(self):
        times = []

        if self.candles_15m:
            times.append(self.candles_15m[0].timestamp)

        if self.candles_5m:
            times.append(self.candles_5m[0].timestamp)

        if self.candles_1m:
            times.append(self.candles_1m[0].timestamp)
        return min(times) if times else None

    @property
    def end_time(self):
        times = []

        if self.candles_15m:
            times.append(self.candles_15m[-1].timestamp)

        if self.candles_5m:
            times.append(self.candles_5m[-1].timestamp)

        if self.candles_1m:
            times.append(self.candles_1m[-1].timestamp)
        return max(times) if times else None