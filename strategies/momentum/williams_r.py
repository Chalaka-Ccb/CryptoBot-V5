from core.models.candle import Candle
#from core.models.signal import SignalSide, TradingSignal

from indicators.williams_r import calculate_williams_r

from strategies.momentum.config import (
    WilliamsRStrategyConfig,
)
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)

class WilliamsRStrategy:
    """
    Larry Williams %R oversold recovery strategy.

    Long setup:

        Previous %R <= oversold
        Current %R > oversold

    This represents %R crossing back upward
    out of the oversold zone.
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

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1:
            return None

        williams_r = calculate_williams_r(
            candles,
            period=self.config.period,
        )

        previous_value = williams_r[index - 1]
        current_value = williams_r[index]

        if (
            previous_value is None
            or current_value is None
        ):
            return None

        # -----------------------------------
        # Oversold → cross back above -80
        # -----------------------------------

        crossed_out_of_oversold = (
            previous_value <= self.config.oversold
            and current_value > self.config.oversold
        )

        if not crossed_out_of_oversold:
            return None

        current = candles[index]

        # -----------------------------------
        # Entry
        # -----------------------------------

        if self.config.enter_at_close:

            trigger_price = current.close
            entry_timing = EntryTiming.CURRENT_CLOSE

        else:

            trigger_price = (
                current.high
                + self.config.trigger_offset
            )
            entry_timing = EntryTiming.BREAKOUT

        # -----------------------------------
        # Stop Loss
        # -----------------------------------
        #
        # The basic signal candle is not
        # necessarily the complete oversold
        # dip, so we determine the lowest low
        # from the oversold sequence.

        stop_loss = self._find_oversold_low(
            candles,
            williams_r,
            index,
        )

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=entry_timing,
            trigger_price=trigger_price,
            stop_loss=stop_loss,
            reason=(
                "Williams %R crossed back above "
                f"{self.config.oversold} after "
                "being oversold."
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

            if value <= self.config.oversold:

                lowest_low = min(
                    lowest_low,
                    candles[index].low,
                )

                index -= 1

            else:
                break

        return lowest_low

    def should_exit_long(
            self,
            candles: list[Candle],
            index: int,
    ) -> bool:

        if index < 1:
            return False

        williams_r = calculate_williams_r(
            candles,
            period=self.config.period,
        )

        previous_value = williams_r[index - 1]
        current_value = williams_r[index]

        if (
                previous_value is None
                or current_value is None
        ):
            return False

        # %R has reached overbought territory
        # and is now turning downward.
        return (
                previous_value > self.config.overbought
                and current_value < previous_value
        )