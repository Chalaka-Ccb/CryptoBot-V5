"""Supertrend entries with EMA bias and completed higher-timeframe ATR/ADX.

The existing coordinator supplies one candle timeframe per strategy. Aggregate
closed base candles into complete groups (default 4) to obtain higher-timeframe
filters without changing the coordinator or introducing future data.
"""
from dataclasses import dataclass
from math import ceil
from core.models.candle import Candle
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from indicators.atr import calculate_atr
from indicators.adx import calculate_adx
from indicators.ema import calculate_ema
from indicators.supertrend import calculate_supertrend


@dataclass
class SupertrendStrategy:
    name: str = "SupertrendDynamic"
    supertrend_period: int = 10
    supertrend_multiplier: float = 3.0
    ema_period: int = 100
    atr_period: int = 14
    adx_period: int = 14
    higher_timeframe_ratio: int = 4
    atr_quantile_window: int = 40
    atr_quantile: float = 0.40
    adx_base_threshold: float = 20.0
    adx_volatility_sensitivity: float = 10.0
    adx_min_threshold: float = 15.0
    adx_max_threshold: float = 30.0

    def __post_init__(self):
        if self.higher_timeframe_ratio < 1 or self.atr_quantile_window < 2:
            raise ValueError("Invalid higher timeframe or quantile window")
        if not 0 <= self.atr_quantile <= 1:
            raise ValueError("atr_quantile must be between 0 and 1")

    @staticmethod
    def _quantile(values: list[float], q: float) -> float:
        ordered = sorted(values)
        position = (len(ordered) - 1) * q
        lo = int(position)
        hi = min(lo + 1, len(ordered) - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)

    def _aggregate(self, candles: list[Candle]) -> list[Candle]:
        ratio = self.higher_timeframe_ratio
        # Align to UTC epoch boundaries; incomplete groups are never used.
        from datetime import timezone
        if len(candles) < 2:
            return []
        step = int((candles[1].timestamp - candles[0].timestamp).total_seconds())
        if step <= 0:
            return []
        bucket_seconds = step * ratio
        groups = {}
        for candle in candles:
            bucket = int(candle.timestamp.timestamp()) // bucket_seconds
            groups.setdefault(bucket, []).append(candle)
        result = []
        for bucket in sorted(groups):
            group = groups[bucket]
            if len(group) != ratio:
                continue
            expected = bucket * bucket_seconds
            if int(group[0].timestamp.timestamp()) != expected:
                continue
            if any(int(c.timestamp.timestamp()) != expected + j * step
                   for j, c in enumerate(group)):
                continue
            result.append(Candle(timestamp=group[0].timestamp,
                                 open=group[0].open,
                                 high=max(c.high for c in group),
                                 low=min(c.low for c in group),
                                 close=group[-1].close,
                                 volume=sum(c.volume for c in group)))
        return result

    def _filters(self, candles: list[Candle]) -> tuple[bool, float | None, float | None]:
        higher = self._aggregate(candles)
        if len(higher) < max(self.atr_period + self.atr_quantile_window - 1,
                             2 * self.adx_period):
            return False, None, None
        atr = calculate_atr(higher, self.atr_period)
        adx = calculate_adx(higher, self.adx_period)
        recent = atr[-self.atr_quantile_window:]
        if any(v is None for v in recent) or adx[-1] is None:
            return False, None, None
        threshold = self._quantile(recent, self.atr_quantile)
        current_atr = atr[-1]
        if threshold <= 0:
            return False, current_atr, adx[-1]
        relative_volatility = current_atr / threshold
        adx_threshold = max(self.adx_min_threshold, min(
            self.adx_max_threshold,
            self.adx_base_threshold + self.adx_volatility_sensitivity
            * (relative_volatility - 1.0)))
        return current_atr > threshold and adx[-1] > adx_threshold, current_atr, adx[-1]

    def generate_signal(self, candles: list[Candle],
                        current_index: int) -> TradingSignal | None:
        if current_index < max(self.ema_period, self.supertrend_period):
            return None
        history = candles[:current_index + 1]
        trend = calculate_supertrend(history, self.supertrend_period,
                                     self.supertrend_multiplier)
        current, previous = trend[-1], trend[-2]
        if current is None or previous is None or current.bullish == previous.bullish:
            return None
        ema = calculate_ema(history, self.ema_period)[-1]
        if ema is None:
            return None
        passes, _, _ = self._filters(history)
        if not passes:
            return None
        price = history[-1].close
        if current.bullish and price > ema and 0 < current.line < price:
            side = SignalSide.LONG
        elif not current.bullish and price < ema and current.line > price:
            side = SignalSide.SHORT
        else:
            return None
        return TradingSignal(strategy=self.name, side=side,
                             candle_index=current_index,
                             entry_timing=EntryTiming.CURRENT_CLOSE,
                             trigger_price=price, stop_loss=current.line,
                             take_profit=None,
                             reason="Supertrend flip + EMA + dynamic HTF ATR/ADX")

    def trailing_stop(self, candles: list[Candle], index: int) -> float | None:
        trend = calculate_supertrend(candles[:index + 1],
                                     self.supertrend_period,
                                     self.supertrend_multiplier)
        return trend[-1].line if trend and trend[-1] else None

    def should_exit_long(self, candles: list[Candle], index: int) -> bool:
        trend = calculate_supertrend(candles[:index + 1],
                                     self.supertrend_period,
                                     self.supertrend_multiplier)
        return bool(trend[-1] and not trend[-1].bullish)

    def should_exit_short(self, candles: list[Candle], index: int) -> bool:
        trend = calculate_supertrend(candles[:index + 1],
                                     self.supertrend_period,
                                     self.supertrend_multiplier)
        return bool(trend[-1] and trend[-1].bullish)
