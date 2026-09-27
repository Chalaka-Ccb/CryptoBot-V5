from core.models.candle import Candle
from core.models.signal import SignalSide

from indicators.ema import calculate_ema


def calculate_ema9_trailing_stop(
    candles: list[Candle],
    index: int,
    current_stop: float,
    side: SignalSide,
    period: int = 9,
) -> float:

    if index < 0 or index >= len(candles):
        raise IndexError(
            "candle index out of range"
        )

    if index < 1:
        return current_stop

    ema_values = calculate_ema(
        candles,
        period,
    )

    current_ema = ema_values[index]

    if current_ema is None:
        return current_stop

    previous_candle = candles[index - 1]

    if side == SignalSide.LONG:

        candidate_stop = max(
            current_ema,
            previous_candle.low,
        )

        return max(
            current_stop,
            candidate_stop,
        )

    if side == SignalSide.SHORT:

        candidate_stop = min(
            current_ema,
            previous_candle.high,
        )

        return min(
            current_stop,
            candidate_stop,
        )

    raise ValueError(
        f"Unsupported signal side: {side}"
    )


def should_exit_ema9(
    candles: list[Candle],
    index: int,
    side: SignalSide,
    period: int = 9,
) -> bool:

    if index < 0 or index >= len(candles):
        return False

    ema_values = calculate_ema(
        candles,
        period,
    )

    ema = ema_values[index]

    if ema is None:
        return False

    close = candles[index].close

    if side == SignalSide.LONG:
        return close < ema

    if side == SignalSide.SHORT:
        return close > ema

    return False