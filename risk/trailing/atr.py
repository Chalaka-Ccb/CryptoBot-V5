from core.models.candle import Candle
from core.models.signal import SignalSide
from indicators.atr import calculate_atr


def calculate_atr_trailing_stop(
    candles: list[Candle],
    index: int,
    entry_price: float,
    current_stop: float,
    side: SignalSide,
    atr_period: int = 14,
    atr_multiplier: float = 2.0,
    highest_price_since_entry: float | None = None,
    lowest_price_since_entry: float | None = None,
) -> float:

    if entry_price <= 0:
        raise ValueError(
            "entry_price must be greater than 0"
        )

    if atr_multiplier <= 0:
        raise ValueError(
            "atr_multiplier must be greater than 0"
        )

    if index < 0 or index >= len(candles):
        raise IndexError(
            "candle index out of range"
        )

    atr_values = calculate_atr(
        candles,
        atr_period,
    )

    atr = atr_values[index]

    if atr is None:
        return current_stop

    current_candle = candles[index]

    if side == SignalSide.LONG:

        if highest_price_since_entry is None:
            highest_price_since_entry = max(
                entry_price,
                current_candle.high,
            )

        trailing_stop = (
            highest_price_since_entry
            - atr_multiplier * atr
        )

        # Never move a long stop downward.
        return max(
            current_stop,
            trailing_stop,
        )

    if side == SignalSide.SHORT:

        if lowest_price_since_entry is None:
            lowest_price_since_entry = min(
                entry_price,
                current_candle.low,
            )

        trailing_stop = (
            lowest_price_since_entry
            + atr_multiplier * atr
        )

        # Never move a short stop upward.
        return min(
            current_stop,
            trailing_stop,
        )

    raise ValueError(
        f"Unsupported signal side: {side}"
    )