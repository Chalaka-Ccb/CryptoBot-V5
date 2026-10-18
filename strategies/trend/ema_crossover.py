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
    EMA 8 / EMA 21 moving-average crossover strategy
    (guide section 6.1, Moving Average Crossover Mechanics).

    The periods come from the config; the guide gives fast / slow
    pairs only as examples (e.g. EMA 9 / SMA 21).

    LONG ENTRY
        Previous EMA fast <= EMA slow
        Current  EMA fast >  EMA slow
        Candle close confirmation: close > EMA slow (guide: the
        crossover candle must close beyond the intersection level)
        Volume > volume SMA of the PRECEDING `volume_period` candles
        (the signal candle itself is excluded, guide section 5.1)

    SHORT ENTRY (mirror, `enable_short`, default True)
        Previous EMA fast >= EMA slow
        Current  EMA fast <  EMA slow
        close < EMA slow, same volume rule

    ENTRY
        Current candle close (strategy-own; the guide executes on
        the open of the next candle, which is practically the same
        price on 24/7 crypto markets).

    STOP (strategy-own, the guide gives none for this setup)
        "ema21": EMA slow -/+ stop_buffer
        "recent_swing_low": lowest low (long) or highest high
        (short) of the last `swing_lookback` candles -/+ stop_buffer

    TAKE PROFIT
        None. The engine applies the guide's default (1:3).

    EXIT
        Long:  EMA fast crosses back below EMA slow.
        Short: EMA fast crosses back above EMA slow.

    The higher-timeframe trend filter and the SMA 200 macro filter
    are applied by the engine, not by this class.

    Optional config field (default used if missing):
        enable_short = True
    """

    name = "ema_8_21_crossover"

    _STOP_MODES = ("ema21", "recent_swing_low")

    def __init__(
        self,
        config: MovingAverageCrossoverConfig | None = None,
    ):
        self.config = config or MovingAverageCrossoverConfig()

        if self.config.stop_mode not in self._STOP_MODES:
            raise ValueError(
                f"Unsupported stop_mode: {self.config.stop_mode}"
            )

        self._cache_key: tuple[int, int] | None = None
        self._fast_ema: list[float | None] = []
        self._slow_ema: list[float | None] = []
        self._volume_sma: list[float | None] = []

    def _indicators(self, candles: list[Candle]):
        """
        Compute indicators once per candle list instead of on every
        call. Rebuilt when the list object or its length changes
        (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._fast_ema = calculate_ema(
                candles,
                self.config.fast_period,
            )
            self._slow_ema = calculate_ema(
                candles,
                self.config.slow_period,
            )
            self._volume_sma = calculate_volume_sma(
                candles,
                self.config.volume_period,
            )
            self._cache_key = key

        return self._fast_ema, self._slow_ema, self._volume_sma

    def generate_signal(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> TradingSignal | None:

        if index is None:
            index = len(candles) - 1

        if index < 1 or index >= len(candles):
            return None

        # ---------------------------------------------------------
        # Fast / slow EMA and volume average
        # ---------------------------------------------------------

        fast_ema, slow_ema, volume_sma = self._indicators(candles)

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
        # Crossover
        # ---------------------------------------------------------

        crossed_above = (
            previous_fast <= previous_slow
            and current_fast > current_slow
        )

        shorts_enabled = getattr(self.config, "enable_short", True)

        crossed_below = (
            shorts_enabled
            and previous_fast >= previous_slow
            and current_fast < current_slow
        )

        if not crossed_above and not crossed_below:
            return None

        # ---------------------------------------------------------
        # Volume confirmation (preceding average, excludes this candle)
        # ---------------------------------------------------------

        preceding_volume_sma = volume_sma[index - 1]

        if preceding_volume_sma is None:
            return None

        current = candles[index]

        if current.volume <= preceding_volume_sma:
            return None

        # ---------------------------------------------------------
        # Candle close confirmation + entry = current candle close
        # ---------------------------------------------------------

        entry_price = current.close

        if crossed_above:

            if current.close <= current_slow:
                return None

            stop_loss = self._calculate_stop_loss(
                candles=candles,
                index=index,
                ema21=current_slow,
                side=SignalSide.LONG,
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
                diagnostics={"fast_ema": current_fast, "slow_ema": current_slow,
                             "previous_fast_ema": previous_fast, "previous_slow_ema": previous_slow,
                             "volume": current.volume, "previous_volume_sma": preceding_volume_sma,
                             "stop_mode": self.config.stop_mode},
                reason=(
                    "Fast EMA crossed above slow EMA, the candle "
                    "closed above the slow EMA, and volume was "
                    "above the preceding volume average."
                ),
            )

        if current.close >= current_slow:
            return None

        stop_loss = self._calculate_stop_loss(
            candles=candles,
            index=index,
            ema21=current_slow,
            side=SignalSide.SHORT,
        )

        if stop_loss <= entry_price:
            return None

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.SHORT,
            candle_index=index,
            entry_timing=EntryTiming.CURRENT_CLOSE,
            trigger_price=entry_price,
            stop_loss=stop_loss,
            take_profit=None,
            reason=(
                "Fast EMA crossed below slow EMA, the candle "
                "closed below the slow EMA, and volume was "
                "above the preceding volume average."
            ),
        )

    def _calculate_stop_loss(
        self,
        candles: list[Candle],
        index: int,
        ema21: float,
        side: SignalSide = SignalSide.LONG,
    ) -> float:

        if self.config.stop_mode == "ema21":
            if side == SignalSide.LONG:
                return ema21 - self.config.stop_buffer
            return ema21 + self.config.stop_buffer

        if self.config.stop_mode == "recent_swing_low":
            lookback = max(
                1,
                min(self.config.swing_lookback, index + 1),
            )

            window = candles[index - lookback + 1 : index + 1]

            if side == SignalSide.LONG:
                return (
                    min(candle.low for candle in window)
                    - self.config.stop_buffer
                )

            return (
                max(candle.high for candle in window)
                + self.config.stop_buffer
            )

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

        if index < 1 or index >= len(candles):
            return False

        fast_ema, slow_ema, _ = self._indicators(candles)

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

        # Fast EMA crosses back below slow EMA.
        return (
            previous_fast >= previous_slow
            and current_fast < current_slow
        )

    def should_exit_short(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> bool:

        if index is None:
            index = len(candles) - 1

        if index < 1 or index >= len(candles):
            return False

        fast_ema, slow_ema, _ = self._indicators(candles)

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

        # Fast EMA crosses back above slow EMA.
        return (
            previous_fast <= previous_slow
            and current_fast > current_slow
        )