"""Chande Momentum Oscillator, using rolling sums of close changes."""
from core.models.candle import Candle


def calculate_cmo(candles: list[Candle], period: int = 14) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[float | None] = [None] * len(candles)
    for i in range(period, len(candles)):
        changes = [candles[j].close - candles[j - 1].close
                   for j in range(i - period + 1, i + 1)]
        up = sum(max(change, 0.0) for change in changes)
        down = sum(max(-change, 0.0) for change in changes)
        result[i] = 100.0 * (up - down) / (up + down) if up + down else 0.0
    return result
