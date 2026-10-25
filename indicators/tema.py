"""Triple exponential moving average (TEMA)."""
from core.models.candle import Candle


def _ema(values: list[float | None], period: int) -> list[float | None]:
    result = [None] * len(values)
    valid = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(valid) < period:
        return result
    seed_index = valid[period - 1][0]
    previous = sum(v for _, v in valid[:period]) / period
    result[seed_index] = previous
    weight = 2.0 / (period + 1)
    for i, value in valid[period:]:
        previous = weight * value + (1 - weight) * previous
        result[i] = previous
    return result


def calculate_tema(candles: list[Candle], period: int = 9) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    first = _ema([c.close for c in candles], period)
    second = _ema(first, period)
    third = _ema(second, period)
    return [
        3 * a - 3 * b + c if a is not None and b is not None and c is not None else None
        for a, b, c in zip(first, second, third)
    ]
