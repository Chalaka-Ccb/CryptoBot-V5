from core.models.candle import Candle
from core.models.signal import (
    EntryTiming,
    SignalSide,
    TradingSignal,
)
from strategies.breakout.config import NR7Config


class NR7Strategy:
    """
    Narrow Range 7 breakout strategy.

    Detects when the current candle has the smallest range
    among the previous 7 candles, including itself.

    When NR7 is detected:

        LONG
            Trigger = NR7 high + offset
            Stop    = NR7 low - buffer

        SHORT
            Trigger = NR7 low - offset
            Stop    = NR7 high + buffer

    The Trading Engine is responsible for:
        - placing both pending orders
        - OCO behavior
        - cancelling the opposite order after one triggers
        - position sizing
        - execution
        - order expiry
    """

    name = "nr7"

    def __init__(
        self,
        config: NR7Config | None = None,
    ):
        self.config = config or NR7Config()

    def generate_signals(
        self,
        candles: list[Candle],
        index: int | None = None,
    ) -> list[TradingSignal]:

        if index is None:
            index = len(candles) - 1

        if index < self.config.lookback - 1:
            return []

        current = candles[index]

        # ---------------------------------------------------------
        # Calculate the ranges for the 7-bar window.
        # ---------------------------------------------------------

        window_start = index - self.config.lookback + 1

        ranges = [
            candle.high - candle.low
            for candle in candles[window_start:index + 1]
        ]

        current_range = current.high - current.low
        minimum_range = min(ranges)

        # ---------------------------------------------------------
        # Current candle must be the minimum range.
        # ---------------------------------------------------------

        if current_range != minimum_range:
            return []

        # ---------------------------------------------------------
        # Create LONG breakout setup.
        # ---------------------------------------------------------

        long_trigger = (
            current.high
            + self.config.trigger_offset
        )

        long_stop = (
            current.low
            - self.config.stop_buffer
        )

        long_signal = TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=EntryTiming.BREAKOUT,
            trigger_price=long_trigger,
            stop_loss=long_stop,
            take_profit=None,
            reason=(
                "NR7 detected. Buy-stop above NR7 candle high."
            ),
        )

        # ---------------------------------------------------------
        # Create SHORT breakout setup.
        # ---------------------------------------------------------

        short_trigger = (
            current.low
            - self.config.trigger_offset
        )

        short_stop = (
            current.high
            + self.config.stop_buffer
        )

        short_signal = TradingSignal(
            strategy=self.name,
            side=SignalSide.SHORT,
            candle_index=index,
            entry_timing=EntryTiming.BREAKOUT,
            trigger_price=short_trigger,
            stop_loss=short_stop,
            take_profit=None,
            reason=(
                "NR7 detected. Sell-stop below NR7 candle low."
            ),
        )

        return [
            long_signal,
            short_signal,
        ]