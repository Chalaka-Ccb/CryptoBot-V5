from core.models.candle import Candle
from core.models.signal import (
    EntryTiming,
    SignalSide,
    TradingSignal,
)
from indicators.ema import calculate_ema
from indicators.volume import calculate_volume_sma
from strategies.trend.config import MovingAverageCrossoverConfig


class EMACrossoverStrategy:
    """
    EMA 8 / EMA 21 moving-average crossover strategy.

    LONG ENTRY
        Previous EMA 8 <= EMA 21
        Current EMA 8 > EMA 21
        Current volume > Volume SMA 20

    ENTRY
        Current candle close

    STOP
        EMA 21 or recent swing low

    EXIT
        EMA 8 crosses back below EMA 21
    """

    name = "ema_8_21_crossover"

    def __init__(
        self,
        config: MovingAverageCrossoverConfig | None = None,
    ):
        self.config = config or MovingAverageCrossoverConfig()

    def generate_signal(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> TradingSignal | None:

        if index is None:
            index = len(candles) - 1

        if index < 1:
            return None

        # ---------------------------------------------------------
        # Calculate EMA 8 and EMA 21
        # ---------------------------------------------------------

        fast_ema = calculate_ema(
            candles,
            self.config.fast_period,
        )

        slow_ema = calculate_ema(
            candles,
            self.config.slow_period,
        )

        previous_fast = fast_ema[index - 1]
        previous_slow = slow_ema[index - 1]

        current_fast = fast_ema[index]
        current_slow = slow_ema[index]

        if (
            previous_fast is None
            or previous_slow is None
            or current_fast is None
            or current_slow is None
        ):
            return None

        # ---------------------------------------------------------
        # Golden Cross
        #
        # EMA8(t-1) <= EMA21(t-1)
        # EMA8(t)   >  EMA21(t)
        # ---------------------------------------------------------

        crossed_above = (
            previous_fast <= previous_slow
            and current_fast > current_slow
        )

        if not crossed_above:
            return None

        # ---------------------------------------------------------
        # Volume confirmation
        # ---------------------------------------------------------

        volume_sma = calculate_volume_sma(
            candles,
            self.config.volume_period,
        )

        current_volume_sma = volume_sma[index]

        if current_volume_sma is None:
            return None

        if candles[index].volume <= current_volume_sma:
            return None

        # ---------------------------------------------------------
        # Entry = current candle close
        # ---------------------------------------------------------

        entry_price = candles[index].close

        # ---------------------------------------------------------
        # Stop loss
        # ---------------------------------------------------------

        stop_loss = self._calculate_stop_loss(
            candles=candles,
            index=index,
            ema21=current_slow,
        )

        if stop_loss >= entry_price:
            return None

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=EntryTiming.CURRENT_CLOSE,
            trigger_price=entry_price,
            stop_loss=stop_loss,
            take_profit=None,
            reason=(
                "EMA 8 crossed above EMA 21 with volume "
                "above Volume SMA 20."
            ),
        )

    def _calculate_stop_loss(
        self,
        candles: list[Candle],
        index: int,
        ema21: float,
    ) -> float:

        if self.config.stop_mode == "ema21":
            return ema21 - self.config.stop_buffer

        if self.config.stop_mode == "recent_swing_low":
            lookback = min(
                self.config.swing_lookback,
                index + 1,
            )

            recent_low = min(
                candle.low
                for candle in candles[
                    index - lookback + 1:index + 1
                ]
            )

            return recent_low - self.config.stop_buffer

        raise ValueError(
            f"Unsupported stop_mode: {self.config.stop_mode}"
        )

    def should_exit_long(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> bool:

        if index is None:
            index = len(candles) - 1

        if index < 1:
            return False

        fast_ema = calculate_ema(
            candles,
            self.config.fast_period,
        )

        slow_ema = calculate_ema(
            candles,
            self.config.slow_period,
        )

        previous_fast = fast_ema[index - 1]
        previous_slow = slow_ema[index - 1]

        current_fast = fast_ema[index]
        current_slow = slow_ema[index]

        if (
            previous_fast is None
            or previous_slow is None
            or current_fast is None
            or current_slow is None
        ):
            return False

        # EMA 8 crosses back below EMA 21.
        return (
            previous_fast >= previous_slow
            and current_fast < current_slow
        )