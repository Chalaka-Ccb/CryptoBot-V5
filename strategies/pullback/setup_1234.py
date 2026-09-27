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


class Setup1234Strategy:
    """
    Larry Connors-style 1-2-3-4 pullback setup.

    Detects:
        Bar 2 low < Bar 1 low
        Bar 3 low < Bar 2 low
        Bar 4 low < Bar 3 low

    After the third consecutive lower low:
        Entry trigger = Bar 4 high + offset
        Stop loss     = Bar 4 low - buffer

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

    def generate_signal(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> TradingSignal | None:

        if index is None:
            index = len(candles) - 1

        if index < 3:
            return None

        current = candles[index]
        previous_1 = candles[index - 1]
        previous_2 = candles[index - 2]
        previous_3 = candles[index - 3]

        # ---------------------------------------------------------
        # 1. Detect three consecutive lower lows
        #
        # Bar 2 low < Bar 1 low
        # Bar 3 low < Bar 2 low
        # Bar 4 low < Bar 3 low
        # ---------------------------------------------------------

        three_lower_lows = (
            previous_2.low < previous_3.low
            and previous_1.low < previous_2.low
            and current.low < previous_1.low
        )

        if not three_lower_lows:
            return None

        # ---------------------------------------------------------
        # 2. Trend filter
        # ---------------------------------------------------------

        if not self._trend_is_valid(candles, index):
            return None

        # ---------------------------------------------------------
        # 3. Buy-stop trigger
        # ---------------------------------------------------------

        trigger_price = current.high + self.config.trigger_offset

        # ---------------------------------------------------------
        # 4. Stop loss
        # ---------------------------------------------------------

        stop_loss = current.low - self.config.stop_buffer

        if stop_loss >= trigger_price:
            return None

        # ---------------------------------------------------------
        # 5. Take-profit
        # ---------------------------------------------------------

        take_profit = self._calculate_take_profit(
            candles=candles,
            index=index,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
        )

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=EntryTiming.BREAKOUT,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=(
                "Three consecutive lower lows detected in an "
                "established bullish trend."
            ),
        )

    def _trend_is_valid(
        self,
        candles: list[Candle],
        index: int,
    ) -> bool:

        if self.config.trend_filter == PullbackTrendFilter.EMA_200:
            ema_values = calculate_ema(
                candles,
                self.config.major_ema_period,
            )

            ema = ema_values[index]

            if ema is None:
                return False

            return candles[index].close > ema

        if self.config.trend_filter == PullbackTrendFilter.EMA_21_SLOPE:
            ema_values = calculate_ema(
                candles,
                self.config.slope_ema_period,
            )

            if index < 1:
                return False

            current_ema = ema_values[index]
            previous_ema = ema_values[index - 1]

            if current_ema is None or previous_ema is None:
                return False

            return (
                candles[index].close > current_ema
                and current_ema > previous_ema
            )

        return False

    def _calculate_take_profit(
            self,
            candles: list[Candle],
            index: int,
            trigger_price: float,
            stop_loss: float,
    ) -> float | None:

        risk = trigger_price - stop_loss

        if risk <= 0:
            return None

        previous_swing_high = candles[index - 3].high

        if (
                self.config.use_previous_swing_high
                and previous_swing_high > trigger_price
        ):
            return previous_swing_high

        if self.config.risk_reward_ratio is not None:
            return (
                    trigger_price
                    + risk * self.config.risk_reward_ratio
            )

        return None