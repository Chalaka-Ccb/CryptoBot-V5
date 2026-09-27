from dataclasses import dataclass

from core.models.candle import Candle


@dataclass(frozen=True)
class WilliamsRConfig:
    period: int = 14


def calculate_williams_r(
    candles: list[Candle],
    period: int = 14,
) -> list[float | None]:
    """
    Calculate Larry Williams %R.

    Formula:

        %R = ((Highest High - Close)
              / (Highest High - Lowest Low)) * -100

    Values range from 0 to -100.
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    results: list[float | None] = []

    for index in range(len(candles)):

        if index + 1 < period:
            results.append(None)
            continue

        window = candles[
            index + 1 - period : index + 1
        ]

        highest_high = max(
            candle.high
            for candle in window
        )

        lowest_low = min(
            candle.low
            for candle in window
        )

        price_range = highest_high - lowest_low

        # Avoid division by zero when all prices
        # in the window are identical.
        if price_range == 0:
            results.append(None)
            continue

        current_close = candles[index].close

        williams_r = (
            (highest_high - current_close)
            / price_range
        ) * -100.0

        results.append(williams_r)

    return results