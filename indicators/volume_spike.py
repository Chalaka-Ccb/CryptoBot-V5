from dataclasses import dataclass
from statistics import mean

from core.models.candle import Candle


@dataclass(frozen=True)
class VolumeSpikeResult:
    volume: float
    volume_sma: float | None
    volume_ratio: float | None
    confirmed: bool


def calculate_volume_spike(
    candles: list[Candle],
    index: int,
    period: int = 20,
    minimum_ratio: float = 1.5,
) -> VolumeSpikeResult:
    """
    Check whether the current candle has sufficient
    volume to confirm a breakout.

    Volume Ratio:
        current volume / Volume SMA(period)

    Confirmation:
        Volume Ratio >= minimum_ratio
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    if minimum_ratio <= 0:
        raise ValueError("minimum_ratio must be greater than 0")

    if index < 0 or index >= len(candles):
        raise IndexError("candle index out of range")

    current_volume = candles[index].volume

    # Not enough historical candles to calculate SMA.
    if index + 1 < period:
        return VolumeSpikeResult(
            volume=current_volume,
            volume_sma=None,
            volume_ratio=None,
            confirmed=False,
        )

    volume_window = [
        candle.volume
        for candle in candles[index + 1 - period:index + 1]
    ]

    volume_sma = mean(volume_window)

    if volume_sma <= 0:
        return VolumeSpikeResult(
            volume=current_volume,
            volume_sma=volume_sma,
            volume_ratio=None,
            confirmed=False,
        )

    volume_ratio = current_volume / volume_sma

    confirmed = volume_ratio >= minimum_ratio

    return VolumeSpikeResult(
        volume=current_volume,
        volume_sma=volume_sma,
        volume_ratio=volume_ratio,
        confirmed=confirmed,
    )