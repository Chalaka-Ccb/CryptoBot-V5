from dataclasses import dataclass
from enum import Enum

from core.models.candle import Candle


class HiLoTrend(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass(frozen=True)
class HiLoValue:
    line: float
    trend: HiLoTrend
    bullish_line: float
    bearish_line: float


def _sma(
    values: list[float],
    period: int,
    index: int,
) -> float | None:

    if index + 1 < period:
        return None

    window = values[
        index + 1 - period : index + 1
    ]

    return sum(window) / period


def calculate_hilo_activator(
    candles: list[Candle],
    period: int = 3,
) -> list[HiLoValue | None]:

    if period <= 0:
        raise ValueError("period must be greater than 0")

    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]

    results: list[HiLoValue | None] = [
        None
    ] * len(candles)

    previous_line: float | None = None
    previous_trend: HiLoTrend | None = None

    for i in range(len(candles)):

        low_sma = _sma(
            lows,
            period,
            i,
        )

        high_sma = _sma(
            highs,
            period,
            i,
        )

        if low_sma is None or high_sma is None:
            continue

        # Initial state.
        if previous_line is None:
            if candles[i].close >= low_sma:
                trend = HiLoTrend.BULLISH
                line = low_sma
            else:
                trend = HiLoTrend.BEARISH
                line = high_sma

        else:

            # Current candle crosses above previous
            # bearish Hi-Lo line.
            if (
                previous_trend == HiLoTrend.BEARISH
                and candles[i].close > previous_line
            ):
                trend = HiLoTrend.BULLISH
                line = low_sma

            # Current candle crosses below previous
            # bullish Hi-Lo line.
            elif (
                previous_trend == HiLoTrend.BULLISH
                and candles[i].close < previous_line
            ):
                trend = HiLoTrend.BEARISH
                line = high_sma

            # Remain bullish.
            elif previous_trend == HiLoTrend.BULLISH:
                trend = HiLoTrend.BULLISH
                line = low_sma

            # Remain bearish.
            else:
                trend = HiLoTrend.BEARISH
                line = high_sma

        results[i] = HiLoValue(
            line=line,
            trend=trend,
            bullish_line=low_sma,
            bearish_line=high_sma,
        )

        previous_line = line
        previous_trend = trend

    return results