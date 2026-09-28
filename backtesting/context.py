from dataclasses import dataclass

from core.models.candle import Candle


@dataclass(frozen=True)
class BacktestContext:
    candles_15m: list[Candle]
    candles_5m: list[Candle]


def build_context(
    candles_15m: list[Candle],
    candles_5m: list[Candle],
    current_timestamp,
) -> BacktestContext:

    available_15m = [
        candle
        for candle in candles_15m
        if candle.timestamp <= current_timestamp
    ]

    available_5m = [
        candle
        for candle in candles_5m
        if candle.timestamp <= current_timestamp
    ]

    return BacktestContext(
        candles_15m=available_15m,
        candles_5m=available_5m,
    )