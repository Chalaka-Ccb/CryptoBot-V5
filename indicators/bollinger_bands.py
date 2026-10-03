from dataclasses import dataclass
from math import sqrt
from statistics import mean

from core.models.candle import Candle


@dataclass(frozen=True)
class BollingerBands:
    middle: float
    upper: float
    lower: float
    standard_deviation: float
    bandwidth: float


def calculate_bollinger_bands(
    candles: list[Candle],
    period: int = 20,
    std_multiplier: float = 2.0,
) -> list[BollingerBands | None]:
    """
    Calculate Bollinger Bands for each candle.

    Middle Band:
        SMA(period)

    Upper Band:
        SMA + std_multiplier * standard deviation

    Lower Band:
        SMA - std_multiplier * standard deviation

    Standard deviation is the population standard deviation (divides
    by N), matching the reference guide.

    Bandwidth:
        (Upper - Lower) / Middle
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    if std_multiplier <= 0:
        raise ValueError("std_multiplier must be greater than 0")

    results: list[BollingerBands | None] = []

    closes = [c.close for c in candles]

    for i in range(len(candles)):
        if i + 1 < period:
            results.append(None)
            continue

        window = closes[i + 1 - period : i + 1]

        middle = mean(window)

        variance = sum(
            (price - middle) ** 2
            for price in window
        ) / period

        standard_deviation = sqrt(variance)

        upper = middle + (
            std_multiplier * standard_deviation
        )

        lower = middle - (
            std_multiplier * standard_deviation
        )

        bandwidth = (
            (upper - lower) / middle
            if middle != 0
            else 0.0
        )

        results.append(
            BollingerBands(
                middle=middle,
                upper=upper,
                lower=lower,
                standard_deviation=standard_deviation,
                bandwidth=bandwidth,
            )
        )

    return results