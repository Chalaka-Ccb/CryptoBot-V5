from core.models.candle import Candle
from core.models.signal import SignalSide


def calculate_swing_trailing_stop(
    candles: list[Candle],
    index: int,
    current_stop: float,
    side: SignalSide,
    lookback: int = 3,
) -> float:

    if lookback <= 0:
        raise ValueError(
            "lookback must be greater than 0"
        )

    if index < 0 or index >= len(candles):
        raise IndexError(
            "candle index out of range"
        )

    if index + 1 < lookback:
        return current_stop

    window = candles[
        index - lookback + 1:index + 1
    ]

    if side == SignalSide.LONG:

        swing_low = min(
            candle.low
            for candle in window
        )

        # Long stop can only move upward.
        return max(
            current_stop,
            swing_low,
        )

    if side == SignalSide.SHORT:

        swing_high = max(
            candle.high
            for candle in window
        )

        # Short stop can only move downward.
        return min(
            current_stop,
            swing_high,
        )

    raise ValueError(
        f"Unsupported signal side: {side}"
    )