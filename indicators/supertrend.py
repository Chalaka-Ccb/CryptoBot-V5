"""Supertrend with Wilder ATR; no future candle access."""
from dataclasses import dataclass
from core.models.candle import Candle
from indicators.atr import calculate_atr


@dataclass(frozen=True)
class SupertrendValue:
    line: float
    bullish: bool


def calculate_supertrend(candles: list[Candle], period: int = 10,
                         multiplier: float = 3.0) -> list[SupertrendValue | None]:
    if period <= 0 or multiplier <= 0:
        raise ValueError("period and multiplier must be positive")
    atr = calculate_atr(candles, period)
    result: list[SupertrendValue | None] = [None] * len(candles)
    upper = lower = 0.0
    bullish = True
    for i, candle in enumerate(candles):
        if atr[i] is None:
            continue
        mid = (candle.high + candle.low) / 2
        basic_upper = mid + multiplier * atr[i]
        basic_lower = mid - multiplier * atr[i]
        if i == period - 1:
            upper, lower = basic_upper, basic_lower
            bullish = candle.close >= mid
        else:
            previous = candles[i - 1].close
            upper = basic_upper if basic_upper < upper or previous > upper else upper
            lower = basic_lower if basic_lower > lower or previous < lower else lower
            if bullish and candle.close < lower:
                bullish = False
            elif not bullish and candle.close > upper:
                bullish = True
        result[i] = SupertrendValue(lower if bullish else upper, bullish)
    return result
