from dataclasses import dataclass

from core.models.candle import Candle


@dataclass(frozen=True)
class ATRValue:
    value: float


def calculate_true_range(
    candles: list[Candle],
) -> list[float]:
    if not candles:
        return []

    true_ranges: list[float] = []

    for index, candle in enumerate(candles):

        if index == 0:
            true_range = candle.high - candle.low

        else:
            previous_close = candles[index - 1].close

            true_range = max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )

        true_ranges.append(true_range)

    return true_ranges


def calculate_atr(
    candles: list[Candle],
    period: int = 14,
) -> list[float | None]:

    if period <= 0:
        raise ValueError(
            "period must be greater than 0"
        )

    true_ranges = calculate_true_range(candles)

    result: list[float | None] = [
        None
    ] * len(candles)

    if len(candles) < period:
        return result

    # Initial ATR = SMA of True Range.
    initial_atr = (
        sum(true_ranges[:period])
        / period
    )

    result[period - 1] = initial_atr

    # Wilder-style smoothing.
    previous_atr = initial_atr

    for index in range(period, len(candles)):
        current_atr = (
            (
                previous_atr * (period - 1)
            )
            + true_ranges[index]
        ) / period

        result[index] = current_atr
        previous_atr = current_atr

    return result