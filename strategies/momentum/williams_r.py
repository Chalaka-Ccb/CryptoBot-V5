# from core.models.candle import Candle
# #from core.models.signal import SignalSide, TradingSignal
#
# from indicators.williams_r import calculate_williams_r
#
# from strategies.momentum.config import (
#     WilliamsRStrategyConfig,
# )
# from core.models.signal import (
#     TradingSignal,
#     SignalSide,
#     EntryTiming,
# )
#
# class WilliamsRStrategy:
#     """
#     Larry Williams %R oversold recovery strategy.
#
#     Long setup:
#
#         Previous %R <= oversold
#         Current %R > oversold
#
#     This represents %R crossing back upward
#     out of the oversold zone.
#     """
#
#     name = "williams_r"
#
#     def __init__(
#         self,
#         config: WilliamsRStrategyConfig | None = None,
#     ):
#         self.config = (
#             config
#             or WilliamsRStrategyConfig()
#         )
#
#     def generate_signal(
#         self,
#         candles: list[Candle],
#         index: int,
#     ) -> TradingSignal | None:
#
#         if index < 1:
#             return None
#
#         williams_r = calculate_williams_r(
#             candles,
#             period=self.config.period,
#         )
#
#         previous_value = williams_r[index - 1]
#         current_value = williams_r[index]
#
#         if (
#             previous_value is None
#             or current_value is None
#         ):
#             return None
#
#         # -----------------------------------
#         # Oversold → cross back above -80
#         # -----------------------------------
#
#         crossed_out_of_oversold = (
#             previous_value <= self.config.oversold
#             and current_value > self.config.oversold
#         )
#
#         if not crossed_out_of_oversold:
#             return None
#
#         current = candles[index]
#
#         # -----------------------------------
#         # Entry
#         # -----------------------------------
#
#         if self.config.enter_at_close:
#
#             trigger_price = current.close
#             entry_timing = EntryTiming.CURRENT_CLOSE
#
#         else:
#
#             trigger_price = (
#                 current.high
#                 + self.config.trigger_offset
#             )
#             entry_timing = EntryTiming.BREAKOUT
#
#         # -----------------------------------
#         # Stop Loss
#         # -----------------------------------
#         #
#         # The basic signal candle is not
#         # necessarily the complete oversold
#         # dip, so we determine the lowest low
#         # from the oversold sequence.
#
#         stop_loss = self._find_oversold_low(
#             candles,
#             williams_r,
#             index,
#         )
#
#         return TradingSignal(
#             strategy=self.name,
#             side=SignalSide.LONG,
#             candle_index=index,
#             entry_timing=entry_timing,
#             trigger_price=trigger_price,
#             stop_loss=stop_loss,
#             reason=(
#                 "Williams %R crossed back above "
#                 f"{self.config.oversold} after "
#                 "being oversold."
#             ),
#         )
#
#     def _find_oversold_low(
#         self,
#         candles: list[Candle],
#         williams_r: list[float | None],
#         current_index: int,
#     ) -> float:
#
#         lowest_low = candles[current_index].low
#
#         index = current_index - 1
#
#         while index >= 0:
#
#             value = williams_r[index]
#
#             if value is None:
#                 break
#
#             if value <= self.config.oversold:
#
#                 lowest_low = min(
#                     lowest_low,
#                     candles[index].low,
#                 )
#
#                 index -= 1
#
#             else:
#                 break
#
#         return lowest_low
#
#     def should_exit_long(
#             self,
#             candles: list[Candle],
#             index: int,
#     ) -> bool:
#
#         if index < 1:
#             return False
#
#         williams_r = calculate_williams_r(
#             candles,
#             period=self.config.period,
#         )
#
#         previous_value = williams_r[index - 1]
#         current_value = williams_r[index]
#
#         if (
#                 previous_value is None
#                 or current_value is None
#         ):
#             return False
#
#         # %R has reached overbought territory
#         # and is now turning downward.
#         return (
#                 previous_value > self.config.overbought
#                 and current_value < previous_value
#         )


from core.models.candle import Candle
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)

from indicators.williams_r import calculate_williams_r

from strategies.momentum.config import (
    WilliamsRStrategyConfig,
)


class WilliamsRStrategy:
    """
    Larry Williams %R strategy (guide section 5.2).

    Zones (%R is bounded between 0 and -100):
        Overbought: -20 to 0
        Oversold:   -80 to -100

    Buy trigger (long):
        %R enters the oversold zone (< oversold) and crosses back
        above it:

            previous %R < oversold  AND  current %R > oversold

    Sell trigger:
        %R enters the overbought zone (> overbought) and crosses
        back below it:

            previous %R > overbought  AND  current %R < overbought

        - Closes an open long (`should_exit_long`).
        - Opens a short when `enable_short` is True.

    Entry:
        At the close of the signal candle (`enter_at_close=True`) or
        as a breakout of the signal candle high / low plus
        `trigger_offset`.

    Stop loss (strategy-own, the guide gives none for %R):
        Long:  lowest low of the oversold sequence plus the signal
               candle.
        Short: highest high of the overbought sequence plus the
               signal candle.

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
        side: SignalSide,
    ) -> tuple[float, EntryTiming]:

        if self.config.enter_at_close:
            return current.close, EntryTiming.CURRENT_CLOSE

        if side == SignalSide.LONG:
            return (
                current.high + self.config.trigger_offset,
                EntryTiming.BREAKOUT,
            )

        return (
            current.low - self.config.trigger_offset,
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

        williams_r = self._get_williams_r(candles)

        previous_value = williams_r[index - 1]
        current_value = williams_r[index]

        if (
            previous_value is None
            or current_value is None
        ):
            return None

        current = candles[index]

        # -----------------------------------
        # Oversold -> cross back above -80 (long)
        # -----------------------------------

        if self._crossed_out_of_oversold(
            previous_value,
            current_value,
        ):

            trigger_price, entry_timing = self._entry(
                current,
                SignalSide.LONG,
            )

            # The signal candle is not necessarily the complete
            # oversold dip, so use the lowest low of the whole
            # oversold sequence.
            stop_loss = self._find_oversold_low(
                candles,
                williams_r,
                index,
            )

            # Guard against zero / negative risk distance.
            if stop_loss >= trigger_price:
                return None

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

        # -----------------------------------
        # Overbought -> cross back below -20 (short)
        # -----------------------------------

        # if (
        #     self.config.enable_short
        #     and self._crossed_out_of_overbought(
        #         previous_value,
        #         current_value,
        #     )
        # ):

            trigger_price, entry_timing = self._entry(
                current,
                SignalSide.SHORT,
            )

            stop_loss = self._find_overbought_high(
                candles,
                williams_r,
                index,
            )

            if stop_loss <= trigger_price:
                return None

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                entry_timing=entry_timing,
                trigger_price=trigger_price,
                stop_loss=stop_loss,
                reason=(
                    "Williams %R crossed back below "
                    f"{self.config.overbought} after "
                    "being overbought."
                ),
            )

        return None

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

    def _find_overbought_high(
        self,
        candles: list[Candle],
        williams_r: list[float | None],
        current_index: int,
    ) -> float:

        highest_high = candles[current_index].high

        index = current_index - 1

        while index >= 0:

            value = williams_r[index]

            if value is None:
                break

            if value > self.config.overbought:

                highest_high = max(
                    highest_high,
                    candles[index].high,
                )

                index -= 1

            else:
                break

        return highest_high

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
        back above the oversold level.
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