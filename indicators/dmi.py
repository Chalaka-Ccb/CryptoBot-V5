"""Wilder directional movement indicators and ADX."""
from dataclasses import dataclass
from core.models.candle import Candle


@dataclass(frozen=True)
class DMIValue:
    plus_di: float
    minus_di: float
    adx: float | None


def calculate_dmi(candles: list[Candle], period: int = 14) -> list[DMIValue | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[DMIValue | None] = [None] * len(candles)
    if len(candles) <= period:
        return result
    tr = [0.0] * len(candles)
    plus = [0.0] * len(candles)
    minus = [0.0] * len(candles)
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i - 1]
        tr[i] = max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        up, down = c.high - p.high, p.low - c.low
        plus[i] = up if up > down and up > 0 else 0.0
        minus[i] = down if down > up and down > 0 else 0.0
    smooth_tr = sum(tr[1:period + 1])
    smooth_plus = sum(plus[1:period + 1])
    smooth_minus = sum(minus[1:period + 1])
    dx_values: list[float] = []
    adx: float | None = None
    for i in range(period, len(candles)):
        if i > period:
            smooth_tr = smooth_tr - smooth_tr / period + tr[i]
            smooth_plus = smooth_plus - smooth_plus / period + plus[i]
            smooth_minus = smooth_minus - smooth_minus / period + minus[i]
        pdi = 100 * smooth_plus / smooth_tr if smooth_tr else 0.0
        mdi = 100 * smooth_minus / smooth_tr if smooth_tr else 0.0
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0
        dx_values.append(dx)
        if len(dx_values) == period:
            adx = sum(dx_values) / period
        elif len(dx_values) > period:
            adx = (adx * (period - 1) + dx) / period
        result[i] = DMIValue(pdi, mdi, adx)
    return result
