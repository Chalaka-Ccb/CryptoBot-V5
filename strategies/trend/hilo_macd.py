from core.models.candle import Candle
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from indicators.hilo_activator import (
    HiLoTrend,
    calculate_hilo_activator,
)
from indicators.macd import calculate_macd


class HiLoMACDStrategy:
    """
    Hi-Lo Activator + MACD trend filter.

    Long setup:

        1. Previous Hi-Lo state is bearish.
        2. Current close breaks above previous Hi-Lo line.
        3. MACD Line > Signal Line.
        4. Enter on next candle open.

    Dynamic stop:

        Current Hi-Lo line.

    Exit:

        Candle closes below current Hi-Lo line.
    """

    name = "hilo_macd"

    def __init__(
        self,
        hilo_period: int = 3,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
    ):
        self.hilo_period = hilo_period

        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1:
            return None

        hilo = calculate_hilo_activator(
            candles,
            period=self.hilo_period,
        )

        macd = calculate_macd(
            candles,
            fast_period=self.macd_fast,
            slow_period=self.macd_slow,
            signal_period=self.macd_signal,
        )

        previous_hilo = hilo[index - 1]
        current_hilo = hilo[index]

        current_macd = macd[index]

        if (
            previous_hilo is None
            or current_hilo is None
            or current_macd is None
        ):
            return None

        # -----------------------------------
        # MACD trend filter
        # -----------------------------------

        macd_bullish = (
            current_macd.macd_line
            > current_macd.signal_line
        )

        if not macd_bullish:
            return None

        # -----------------------------------
        # Hi-Lo bullish flip
        # -----------------------------------

        bullish_flip = (
            previous_hilo.trend
            == HiLoTrend.BEARISH
            and candles[index].close
            > previous_hilo.line
        )

        if not bullish_flip:
            return None

        # -----------------------------------
        # Long signal
        # -----------------------------------
        #
        # Entry is next candle OPEN.
        #
        # We therefore don't pretend that
        # the current close is the entry price.

        return TradingSignal(
            strategy=self.name,
            side=SignalSide.LONG,
            candle_index=index,
            entry_timing=EntryTiming.NEXT_OPEN,
            trigger_price=candles[index].close,
            stop_loss=current_hilo.line,
            reason=(
                "MACD bullish filter confirmed and "
                "price crossed above the previous "
                "bearish Hi-Lo Activator line. "
                "Entry scheduled for next candle open."
            ),

        )

    def should_exit_long(
        self,
        candles: list[Candle],
        index: int,
    ) -> bool:

        if index < 1:
            return False

        hilo = calculate_hilo_activator(
            candles,
            period=self.hilo_period,
        )

        current_hilo = hilo[index]

        if current_hilo is None:
            return False

        return (
            candles[index].close
            < current_hilo.line
        )

    def trailing_stop(
        self,
        candles: list[Candle],
        index: int,
    ) -> float | None:

        hilo = calculate_hilo_activator(
            candles,
            period=self.hilo_period,
        )

        current_hilo = hilo[index]

        if current_hilo is None:
            return None

        return current_hilo.line