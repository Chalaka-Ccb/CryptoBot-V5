from core.models.candle import Candle
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)
from indicators.atr import calculate_atr
from indicators.ema import calculate_ema
from indicators.volume_spike import calculate_volume_spike
from indicators.williams_r import calculate_williams_r

from strategies.momentum.config import (
    WilliamsRStrategyConfig,
)


class WilliamsRStrategy:
    """
    Larry Williams %R strategy (guide section 5.2) - LONG ONLY,
    filtered by EMA 200.

    Long condition:
        (%R[t-1] < oversold) AND (%R[t] > oversold)
        AND (close[t] > EMA200[t])
        AND (EMA200[t] > EMA200[t-5])
        AND (volume[t] >= 1.2 * volume SMA(20)[t])

    Zones (%R is bounded between 0 and -100):
        Overbought: -20 to 0
        Oversold:   -80 to -100

    Buy trigger (long):
        %R enters the oversold zone (< oversold) and crosses back
        above it:

            previous %R < oversold  AND  current %R > oversold

    Sell trigger (exit only):
        %R enters the overbought zone (> overbought) and crosses
        back below it:

            previous %R > overbought  AND  current %R < overbought

        - Closes an open long (`should_exit_long`).
        - No short signals are generated.

    Entry:
        At the close of the signal candle (`enter_at_close=True`) or
        as a breakout of the signal candle high plus
        `trigger_offset`.

    Stop loss (ATR method from the guide):
        Long: entry price - 1.5 * ATR(14) on the signal candle.
        (`_find_oversold_low` is retained for structural-stop
        comparisons but is not used for the stop.)

    No take profit is set; the engine applies the guide's default
    target (1:3 risk-reward).
    """

    name = "williams_r"

    def __init__(
        self,
        config: WilliamsRStrategyConfig | None = None,
    ):
        self.config = (
            config
            or WilliamsRStrategyConfig()
        )
        self._cache_key: tuple[int, int] | None = None
        self._williams_r: list[float | None] = []

    # -----------------------------------
    # Helpers
    # -----------------------------------

    def _get_williams_r(
        self,
        candles: list[Candle],
    ) -> list[float | None]:
        """
        Compute %R once per candle list instead of on every call.
        Rebuilt when the list object or its length changes (live
        data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._williams_r = calculate_williams_r(
                candles,
                period=self.config.period,
            )
            self._cache_key = key

        return self._williams_r

    def _crossed_out_of_oversold(
        self,
        previous_value: float,
        current_value: float,
    ) -> bool:
        return (
            previous_value < self.config.oversold
            and current_value > self.config.oversold
        )

    def _crossed_out_of_overbought(
        self,
        previous_value: float,
        current_value: float,
    ) -> bool:
        return (
            previous_value > self.config.overbought
            and current_value < self.config.overbought
        )

    def _entry(
        self,
        current: Candle,
    ) -> tuple[float, EntryTiming]:

        if self.config.enter_at_close:
            return current.close, EntryTiming.CURRENT_CLOSE

        return (
            current.high + self.config.trigger_offset,
            EntryTiming.BREAKOUT,
        )

    # -----------------------------------
    # Signal generation
    # -----------------------------------

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1 or index >= len(candles):
            return None

        # Only historical candles available at this index.
        historical_candles = candles[:index + 1]

        current = candles[index]

        # -----------------------------------
        # 1. EMA 200 trend + slope confirmation
        # -----------------------------------

        ema_values = calculate_ema(
            historical_candles,
            period=200,
        )

        slope_lookback = 5

        # Need enough candles for EMA 200
        # and five additional candles for slope.
        if index < 199 + slope_lookback:
            return None

        current_ema = ema_values[index]
        previous_ema = ema_values[index - slope_lookback]

        if current_ema is None or previous_ema is None:
            return None

        # Condition 1: Price above EMA 200.
        if current.close <= current_ema:
            return None

        # Condition 2: EMA 200 must be rising.
        if current_ema <= previous_ema:
            return None

        # -----------------------------------
        # 2. Williams %R recovery
        # -----------------------------------

        williams_r = calculate_williams_r(
            historical_candles,
            period=self.config.period,
        )

        previous_value = williams_r[index - 1]
        current_value = williams_r[index]

        if (
            previous_value is None
            or current_value is None
        ):
            return None

        if not self._crossed_out_of_oversold(
            previous_value,
            current_value,
        ):
            return None

        # -----------------------------------
        # 3. Volume confirmation
        # -----------------------------------

        volume_result = calculate_volume_spike(
            candles=historical_candles,
            index=index,
            period=20,
            minimum_ratio=1.2,
        )

        if not volume_result.confirmed:
            return None

        # -----------------------------------
        # 4. LONG entry
        # -----------------------------------

        trigger_price, entry_timing = self._entry(current)

        # -----------------------------------
        # ATR-based stop-loss
        # -----------------------------------

        atr_values = calculate_atr(
            historical_candles,
            period=14,
        )

        current_atr = atr_values[index]

        if current_atr is None or current_atr <= 0:
            return None

        atr_multiplier = 1.5

        stop_loss = (
            trigger_price
            - atr_multiplier * current_atr
        )

        # Reject invalid stop-loss.
        if stop_loss <= 0 or stop_loss >= trigger_price:
            return None

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=entry_timing,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
            reason=(
                "Williams %R recovered above "
                f"{self.config.oversold}; "
                "price above EMA 200; "
                f"volume ratio {volume_result.volume_ratio:.2f} "
                "confirmed >= 1.2."
            ),
        )

    def _find_oversold_low(
        self,
        candles: list[Candle],
        williams_r: list[float | None],
        current_index: int,
    ) -> float:

        lowest_low = candles[current_index].low

        index = current_index - 1

        while index >= 0:

            value = williams_r[index]

            if value is None:
                break

            if value < self.config.oversold:

                lowest_low = min(
                    lowest_low,
                    candles[index].low,
                )

                index -= 1

            else:
                break

        return lowest_low

    # -----------------------------------
    # Exits
    # -----------------------------------

    def should_exit_long(
        self,
        candles: list[Candle],
        index: int,
    ) -> bool:
        """
        Guide sell trigger: %R was overbought and has crossed back
        below the overbought level.
        """

        if index < 1 or index >= len(candles):
            return False

        williams_r = self._get_williams_r(candles)

        previous_value = williams_r[index - 1]
        current_value = williams_r[index]

        if (
            previous_value is None
            or current_value is None
        ):
            return False

        return self._crossed_out_of_overbought(
            previous_value,
            current_value,
        )

    def should_exit_short(
        self,
        candles: list[Candle],
        index: int,
    ) -> bool:
        """
        Mirror of the long exit: %R was oversold and has crossed
        back above the oversold level. Kept for engine interface
        compatibility; never used since no shorts are opened.
        """

        if index < 1 or index >= len(candles):
            return False

        williams_r = self._get_williams_r(candles)

        previous_value = williams_r[index - 1]
        current_value = williams_r[index]

        if (
            previous_value is None
            or current_value is None
        ):
            return False

        return self._crossed_out_of_oversold(
            previous_value,
            current_value,
        )