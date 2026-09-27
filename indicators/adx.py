from core.models.candle import Candle


def calculate_adx(
    candles: list[Candle],
    period: int = 14,
) -> list[float | None]:

    if period <= 0:
        raise ValueError("period must be greater than 0")

    if len(candles) < period + 1:
        return [None] * len(candles)

    true_ranges: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []

    for i in range(len(candles)):

        if i == 0:
            true_ranges.append(
                candles[i].high - candles[i].low
            )
            plus_dm.append(0.0)
            minus_dm.append(0.0)
            continue

        current = candles[i]
        previous = candles[i - 1]

        true_range = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )

        up_move = current.high - previous.high
        down_move = previous.low - current.low

        plus = (
            up_move
            if up_move > down_move and up_move > 0
            else 0.0
        )

        minus = (
            down_move
            if down_move > up_move and down_move > 0
            else 0.0
        )

        true_ranges.append(true_range)
        plus_dm.append(plus)
        minus_dm.append(minus)

    adx_values: list[float | None] = [
        None
    ] * len(candles)

    for i in range(period, len(candles)):

        tr = sum(
            true_ranges[i - period + 1 : i + 1]
        )

        plus = sum(
            plus_dm[i - period + 1 : i + 1]
        )

        minus = sum(
            minus_dm[i - period + 1 : i + 1]
        )

        if tr == 0:
            continue

        plus_di = 100 * plus / tr
        minus_di = 100 * minus / tr

        denominator = plus_di + minus_di

        if denominator == 0:
            continue

        dx = (
            100
            * abs(plus_di - minus_di)
            / denominator
        )

        adx_values[i] = dx

    return adx_values