from dataclasses import dataclass

from core.models.candle import Candle


@dataclass(frozen=True)
class MACDValue:
    macd_line: float
    signal_line: float
    histogram: float


def _ema(
    values: list[float],
    period: int,
) -> list[float | None]:

    if period <= 0:
        raise ValueError("period must be greater than 0")

    result: list[float | None] = [None] * len(values)

    if len(values) < period:
        return result

    # Initial EMA uses SMA.
    initial_sma = sum(values[:period]) / period
    result[period - 1] = initial_sma

    multiplier = 2 / (period + 1)

    previous_ema = initial_sma

    for i in range(period, len(values)):
        current_ema = (
            (values[i] - previous_ema) * multiplier
            + previous_ema
        )

        result[i] = current_ema
        previous_ema = current_ema

    return result


def calculate_macd(
    candles: list[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> list[MACDValue | None]:

    if fast_period >= slow_period:
        raise ValueError(
            "fast_period must be smaller than slow_period"
        )

    closes = [candle.close for candle in candles]

    fast_ema = _ema(closes, fast_period)
    slow_ema = _ema(closes, slow_period)

    macd_lines: list[float | None] = [
        None
    ] * len(candles)

    for i in range(len(candles)):
        if (
            fast_ema[i] is not None
            and slow_ema[i] is not None
        ):
            macd_lines[i] = (
                fast_ema[i] - slow_ema[i]
            )

    valid_macd = [
        value
        for value in macd_lines
        if value is not None
    ]

    signal_values = _ema(
        valid_macd,
        signal_period,
    )

    results: list[MACDValue | None] = [
        None
    ] * len(candles)

    signal_index = 0

    for i in range(len(candles)):

        if macd_lines[i] is None:
            continue

        signal = signal_values[signal_index]
        signal_index += 1

        if signal is None:
            continue

        macd_line = macd_lines[i]

        results[i] = MACDValue(
            macd_line=macd_line,
            signal_line=signal,
            histogram=macd_line - signal,
        )

    return results