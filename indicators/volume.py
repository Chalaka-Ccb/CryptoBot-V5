from statistics import mean

from core.models.candle import Candle


def calculate_volume_sma(
    candles: list[Candle],
    period: int = 20,
) -> list[float | None]:

    if period <= 0:
        raise ValueError("period must be greater than 0")

    volumes = [c.volume for c in candles]

    result: list[float | None] = []

    for i in range(len(candles)):

        if i + 1 < period:
            result.append(None)
            continue

        window = volumes[i + 1 - period : i + 1]

        result.append(mean(window))

    return result