from core.models.candle import Candle


def calculate_ema(
    candles: list[Candle],
    period: int,
) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be greater than 0")

    closes = [candle.close for candle in candles]

    result: list[float | None] = [None] * len(candles)

    if len(closes) < period:
        return result

    # Initial EMA value = SMA
    initial_ema = sum(closes[:period]) / period
    result[period - 1] = initial_ema

    multiplier = 2 / (period + 1)
    previous_ema = initial_ema

    for index in range(period, len(closes)):
        current_ema = (
            (closes[index] - previous_ema) * multiplier
            + previous_ema
        )

        result[index] = current_ema
        previous_ema = current_ema

    return result