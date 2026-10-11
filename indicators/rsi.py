from core.models.candle import Candle


def calculate_rsi(
    candles: list[Candle],
    period: int = 14,
) -> list[float | None]:
    """
    Relative Strength Index (IFR / RSI) with Wilder smoothing.

        RSI = 100 - (100 / (1 + RS))
        RS  = Average Gain over N periods / Average Loss over N periods

    The first average is the simple mean of the first `period` price
    changes. After that:

        avg = (previous_avg * (period - 1) + current_value) / period

    The first RSI value is available at index `period`.
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    n = len(candles)
    result: list[float | None] = [None] * n

    if n < period + 1:
        return result

    closes = [c.close for c in candles]

    gains = [0.0] * n
    losses = [0.0] * n

    for i in range(1, n):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains[i] = change
        elif change < 0:
            losses[i] = -change

    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period

    result[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result[i] = _rsi_value(avg_gain, avg_loss)

    return result


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        # No losses: fully overbought. No movement at all: neutral.
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))