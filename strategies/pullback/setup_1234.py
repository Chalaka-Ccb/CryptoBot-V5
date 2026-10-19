from core.models.candle import Candle
from core.models.signal import (
    EntryTiming,
    SignalSide,
    TradingSignal,
)
from indicators.ema import calculate_ema
from strategies.pullback.config import (
    PullbackTrendFilter,
    Setup1234Config,
)


def _sma(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be greater than 0")

    result: list[float | None] = [None] * len(values)

    if len(values) < period:
        return result

    window_sum = sum(values[:period])
    result[period - 1] = window_sum / period

    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        result[i] = window_sum / period

    return result


class Setup1234Strategy:
    """
    Setup 1-2-3-4 Reversal Model (guide section 6.1).

    Bullish reversal:
        Point 1: major structural low, the lowest low of the last
                 `swing_lookback` candles ending at Point 3.
        Point 2: peak of the bounce after Point 1 (highest high
                 since Point 1).
        Point 3: secondary pullback that fails to breach Point 1,
                 i.e. a pivot low with L3 > L1. It is confirmed
                 `pivot_strength` candles later, which is when the
                 signal is produced (once per structure).
        Point 4: buy stop slightly above Point 2 (H2 + offset). The
                 setup is invalid if price already traded through
                 the trigger before the signal candle closed.

    Bearish reversal (mirror, `enable_short`):
        Point 1: highest high, Point 2: lowest low since Point 1,
        Point 3: pivot high with H3 < H1, Point 4: sell stop slightly
        below Point 2.

    Trend filter:
        Longs need price above the filter, shorts below it
        (guide default: 200 SMA). Use PullbackTrendFilter.NONE if
        the engine applies the macro filter.

    Stop loss (strategy-own, the guide gives none for this setup):
        Beyond Point 3 (the pullback extreme) +/- stop_buffer.

    Take profit:
        entry +/- risk * risk_reward_ratio (guide default 1:3).
        None if risk_reward_ratio is None.

    The Trading Engine is responsible for:
        - creating the actual pending order
        - position sizing
        - order expiration/cancellation
        - execution
        - trade management
    """

    name = "setup_1234"

    def __init__(
        self,
        config: Setup1234Config | None = None,
    ):
        self.config = config or Setup1234Config()

        if self.config.pivot_strength < 1:
            raise ValueError("pivot_strength must be at least 1")

        if self.config.swing_lookback <= self.config.pivot_strength:
            raise ValueError(
                "swing_lookback must be greater than pivot_strength"
            )

        self._cache_key: tuple[int, int] | None = None
        self._trend_values: list[float | None] = []

    # ---------------------------------------------------------
    # Trend filter
    # ---------------------------------------------------------

    def _ensure_trend_values(self, candles: list[Candle]) -> None:
        """
        Compute the trend average once per candle list instead of on
        every call. Rebuilt when the list object or its length
        changes (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key == self._cache_key:
            return

        trend_filter = self.config.trend_filter

        if trend_filter == PullbackTrendFilter.SMA_200:
            self._trend_values = _sma(
                [c.close for c in candles],
                self.config.major_ema_period,
            )
        elif trend_filter == PullbackTrendFilter.EMA_200:
            self._trend_values = calculate_ema(
                candles,
                self.config.major_ema_period,
            )
        elif trend_filter == PullbackTrendFilter.EMA_21_SLOPE:
            self._trend_values = calculate_ema(
                candles,
                self.config.slope_ema_period,
            )
        else:
            self._trend_values = []

        self._cache_key = key

    def _trend_allows(
        self,
        candles: list[Candle],
        index: int,
        side: SignalSide,
    ) -> bool:

        trend_filter = self.config.trend_filter

        if trend_filter == PullbackTrendFilter.NONE:
            return True

        close = candles[index].close
        current_value = self._trend_values[index]

        if current_value is None:
            return False

        if trend_filter == PullbackTrendFilter.EMA_21_SLOPE:

            if index < 1:
                return False

            previous_value = self._trend_values[index - 1]

            if previous_value is None:
                return False

            if side == SignalSide.LONG:
                return (
                    close > current_value
                    and current_value > previous_value
                )

            return (
                close < current_value
                and current_value < previous_value
            )

        # SMA_200 / EMA_200
        if side == SignalSide.LONG:
            return close > current_value

        return close < current_value

    # ---------------------------------------------------------
    # Signal generation
    # ---------------------------------------------------------

    def generate_signal(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> TradingSignal | None:

        if index is None:
            index = len(candles) - 1

        if index < 0 or index >= len(candles):
            return None

        strength = self.config.pivot_strength
        lookback = self.config.swing_lookback

        # Point 3 candidate is confirmed `strength` candles later.
        point_3 = index - strength
        window_start = point_3 - lookback + 1

        if window_start < 0:
            return None

        self._ensure_trend_values(candles)

        # Baseline experiment: short signals only.
        if self.config.enable_short:
            return self._bearish_signal(
                candles,
                index,
                point_3,
                window_start,
            )

        return None

    def _bullish_signal(
        self,
        candles: list[Candle],
        index: int,
        point_3: int,
        window_start: int,
    ) -> TradingSignal | None:

        strength = self.config.pivot_strength
        low_3 = candles[point_3].low

        # Point 3 must be a pivot low.
        for j in range(1, strength + 1):
            if (
                low_3 >= candles[point_3 - j].low
                or low_3 >= candles[point_3 + j].low
            ):
                return None

        # Point 1: lowest low of the window ending at Point 3.
        point_1 = min(
            range(window_start, point_3 + 1),
            key=lambda i: candles[i].low,
        )

        # Point 3 must fail to breach Point 1 (L3 > L1).
        if low_3 <= candles[point_1].low:
            return None

        # Point 2: highest high since Point 1, must precede Point 3.
        point_2 = max(
            range(point_1 + 1, index + 1),
            key=lambda i: candles[i].high,
        )

        if point_2 >= point_3:
            return None

        trigger_price = (
            candles[point_2].high + self.config.trigger_offset
        )

        # Invalid if the buy stop was already hit before now.
        if any(
            candles[i].high >= trigger_price
            for i in range(point_3 + 1, index + 1)
        ):
            return None

        if not self._trend_allows(candles, index, SignalSide.LONG):
            return None

        stop_loss = low_3 - self.config.stop_buffer

        if stop_loss >= trigger_price:
            return None

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=EntryTiming.BREAKOUT,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
            take_profit=self._take_profit(
                trigger_price,
                stop_loss,
                SignalSide.LONG,
            ),
            diagnostics={"point_1_index": point_1, "point_2_index": point_2,
                         "point_3_index": point_3, "pivot_strength": strength,
                         "trend_filter": str(self.config.trend_filter),
                         "trend_value": self._trend_values[index] if self._trend_values else None,
                         "point_1_high": candles[point_1].high, "point_1_low": candles[point_1].low,
                         "point_2_high": candles[point_2].high, "point_2_low": candles[point_2].low,
                         "point_3_high": candles[point_3].high, "point_3_low": candles[point_3].low},
            reason=(
                "Bullish 1-2-3-4 reversal: higher low at Point 3 "
                "above the Point 1 low; buy stop above the "
                "Point 2 high."
            ),
        )

    def _bearish_signal(
        self,
        candles: list[Candle],
        index: int,
        point_3: int,
        window_start: int,
    ) -> TradingSignal | None:

        strength = self.config.pivot_strength
        high_3 = candles[point_3].high

        # Point 3 must be a pivot high.
        for j in range(1, strength + 1):
            if (
                high_3 <= candles[point_3 - j].high
                or high_3 <= candles[point_3 + j].high
            ):
                return None

        # Point 1: highest high of the window ending at Point 3.
        point_1 = max(
            range(window_start, point_3 + 1),
            key=lambda i: candles[i].high,
        )

        # Point 3 must fail to breach Point 1 (H3 < H1).
        if high_3 >= candles[point_1].high:
            return None

        # Point 2: lowest low since Point 1, must precede Point 3.
        point_2 = min(
            range(point_1 + 1, index + 1),
            key=lambda i: candles[i].low,
        )

        if point_2 >= point_3:
            return None

        trigger_price = (
            candles[point_2].low - self.config.trigger_offset
        )

        # Invalid if the sell stop was already hit before now.
        if any(
            candles[i].low <= trigger_price
            for i in range(point_3 + 1, index + 1)
        ):
            return None

        if not self._trend_allows(candles, index, SignalSide.SHORT):
            return None

        stop_loss = high_3 + self.config.stop_buffer

        if stop_loss <= trigger_price:
            return None

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.SHORT,
            candle_index=index,
            entry_timing=EntryTiming.BREAKOUT,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
            take_profit=self._take_profit(
                trigger_price,
                stop_loss,
                SignalSide.SHORT,
            ),
            diagnostics={"point_1_index": point_1, "point_2_index": point_2,
                         "point_3_index": point_3, "pivot_strength": strength,
                         "trend_filter": str(self.config.trend_filter),
                         "trend_value": self._trend_values[index] if self._trend_values else None,
                         "point_1_high": candles[point_1].high, "point_1_low": candles[point_1].low,
                         "point_2_high": candles[point_2].high, "point_2_low": candles[point_2].low,
                         "point_3_high": candles[point_3].high, "point_3_low": candles[point_3].low},
            reason=(
                "Bearish 1-2-3-4 reversal: lower high at Point 3 "
                "below the Point 1 high; sell stop below the "
                "Point 2 low."
            ),
        )

    def _take_profit(
        self,
        trigger_price: float,
        stop_loss: float,
        side: SignalSide,
    ) -> float | None:

        ratio = self.config.risk_reward_ratio

        if ratio is None:
            return None

        risk = abs(trigger_price - stop_loss)

        if risk <= 0:
            return None

        if side == SignalSide.LONG:
            return trigger_price + risk * ratio

        return trigger_price - risk * ratio