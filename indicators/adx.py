from core.models.candle import Candle


def calculate_adx(
    candles: list[Candle],
    period: int = 14,
) -> list[float | None]:
    """
    Average Directional Index (ADX) using Wilder smoothing.

    Steps:
        1. True Range, +DM and -DM for every candle.
        2. Wilder-smoothed TR, +DM and -DM (seeded with the sum of the
           first `period` values, then: prev - prev / period + current).
        3. +DI = 100 * smoothed(+DM) / smoothed(TR)
           -DI = 100 * smoothed(-DM) / smoothed(TR)
        4. DX  = 100 * |+DI - -DI| / (+DI + -DI)
        5. ADX = Wilder average of DX (first value is the mean of the
           first `period` DX values).

    The first ADX value is available at index 2 * period - 1.
    Earlier indexes are None.
    """

    if period <= 0:
        raise ValueError("period must be greater than 0")

    n = len(candles)
    result: list[float | None] = [None] * n

    if n < 2 * period:
        return result

    true_ranges = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):
        current = candles[i]
        previous = candles[i - 1]

        true_ranges[i] = max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )

        up_move = current.high - previous.high
        down_move = previous.low - current.low

        plus_dm[i] = (
            up_move
            if up_move > down_move and up_move > 0
            else 0.0
        )

        minus_dm[i] = (
            down_move
            if down_move > up_move and down_move > 0
            else 0.0
        )

    def dx_from(
        smoothed_tr: float,
        smoothed_plus: float,
        smoothed_minus: float,
    ) -> float:
        if smoothed_tr == 0:
            return 0.0

        plus_di = 100 * smoothed_plus / smoothed_tr
        minus_di = 100 * smoothed_minus / smoothed_tr

        denominator = plus_di + minus_di

        if denominator == 0:
            return 0.0

        return 100 * abs(plus_di - minus_di) / denominator

    # Wilder seed: sum of the first `period` values (indexes 1..period)
    smoothed_tr = sum(true_ranges[1 : period + 1])
    smoothed_plus = sum(plus_dm[1 : period + 1])
    smoothed_minus = sum(minus_dm[1 : period + 1])

    adx = 0.0
    dx_sum = 0.0
    dx_count = 0

    for i in range(period, n):

        if i > period:
            smoothed_tr = (
                smoothed_tr - smoothed_tr / period + true_ranges[i]
            )
            smoothed_plus = (
                smoothed_plus - smoothed_plus / period + plus_dm[i]
            )
            smoothed_minus = (
                smoothed_minus - smoothed_minus / period + minus_dm[i]
            )

        dx = dx_from(smoothed_tr, smoothed_plus, smoothed_minus)
        dx_count += 1

        if dx_count < period:
            dx_sum += dx

        elif dx_count == period:
            dx_sum += dx
            adx = dx_sum / period
            result[i] = adx

        else:
            adx = (adx * (period - 1) + dx) / period
            result[i] = adx

    return result