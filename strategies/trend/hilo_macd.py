from core.models.candle import Candle
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from indicators.hilo_activator import (
    HiLoTrend,
    calculate_hilo_activator,
)
from indicators.macd import calculate_macd


class HiLoMACDStrategy:
    """
    Hi-Lo Activator + MACD system (guide section 5.2).

    Long trigger:

        1. Price closes above the Hi-Lo Activator (Hi-Lo state is
           bullish and the close is above its line).
        2. MACD line crosses above the MACD signal line
           (previous MACD <= signal, current MACD > signal)
           beneath the zero axis (MACD line < 0 at the cross).
        3. Both must hold together: the MACD cross happened on the
           signal candle (`macd_cross_lookback=1`, the guide's
           "while"), or within the last `macd_cross_lookback`
           candles if you want to allow a Hi-Lo move shortly after
           the cross. The MACD must still be above its signal line.
        4. Enter on next candle open.

        The signal is produced once, on the first candle where all
        conditions hold.

    Dynamic stop:

        Current Hi-Lo line.

    Exit (guide exit trigger):

        Candle closes below the current Hi-Lo line.

    The guide defines only the long trigger for this system, so no
    short signal is produced. No take profit is set; the engine
    applies the guide's default target (1:3).
    """

    name = "hilo_macd"

    def __init__(
        self,
        hilo_period: int = 3,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        macd_cross_lookback: int = 1,
        macd_cross_below_zero: bool = True,
    ):
        if macd_cross_lookback < 1:
            raise ValueError("macd_cross_lookback must be at least 1")

        self.hilo_period = hilo_period

        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

        self.macd_cross_lookback = macd_cross_lookback
        self.macd_cross_below_zero = macd_cross_below_zero

        self._cache_key: tuple[int, int] | None = None
        self._hilo = []
        self._macd = []

    def _indicators(self, candles: list[Candle]):
        """
        Compute indicators once per candle list instead of on every
        call. Rebuilt when the list object or its length changes
        (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._hilo = calculate_hilo_activator(
                candles,
                period=self.hilo_period,
            )
            self._macd = calculate_macd(
                candles,
                fast_period=self.macd_fast,
                slow_period=self.macd_slow,
                signal_period=self.macd_signal,
            )
            self._cache_key = key

        return self._hilo, self._macd

    def _macd_crossed_up(self, macd, i: int) -> bool:
        """
        MACD line crossed above the signal line on candle i
        (beneath the zero axis when `macd_cross_below_zero`).
        """

        if i < 1:
            return False

        previous = macd[i - 1]
        current = macd[i]

        if previous is None or current is None:
            return False

        crossed = (
            previous.macd_line <= previous.signal_line
            and current.macd_line > current.signal_line
        )

        if not crossed:
            return False

        if self.macd_cross_below_zero and current.macd_line >= 0:
            return False

        return True

    def _entry_condition(
        self,
        candles: list[Candle],
        hilo,
        macd,
        i: int,
    ) -> bool:

        if i < 1:
            return False

        current_hilo = hilo[i]
        current_macd = macd[i]

        if current_hilo is None or current_macd is None:
            return False

        # Price closes above the Hi-Lo Activator: the indicator is in
        # its bullish state and the close is above its line.
        if current_hilo.trend != HiLoTrend.BULLISH:
            return False

        if candles[i].close <= current_hilo.line:
            return False

        # The MACD cross must still be intact.
        if current_macd.macd_line <= current_macd.signal_line:
            return False

        first = max(1, i - self.macd_cross_lookback + 1)

        return any(
            self._macd_crossed_up(macd, j)
            for j in range(first, i + 1)
        )

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1 or index >= len(candles):
            return None

        hilo, macd = self._indicators(candles)

        if not self._entry_condition(candles, hilo, macd, index):
            return None

        # Signal only on the first candle where the setup holds.
        if self._entry_condition(candles, hilo, macd, index - 1):
            return None

        current_hilo = hilo[index]
        close = candles[index].close

        stop_loss = current_hilo.line

        # Guard against a stop on the wrong side of the entry.
        if stop_loss >= close:
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
            trigger_price=close,
            stop_loss=stop_loss,
            reason=(
                "Price closed above the Hi-Lo Activator while the "
                "MACD line crossed above its signal line beneath "
                "the zero axis. Entry scheduled for next candle "
                "open."
            ),
        )

    def should_exit_long(
        self,
        candles: list[Candle],
        index: int,
    ) -> bool:

        if index < 1 or index >= len(candles):
            return False

        hilo, _ = self._indicators(candles)

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

        if index < 0 or index >= len(candles):
            return None

        hilo, _ = self._indicators(candles)

        current_hilo = hilo[index]

        if current_hilo is None:
            return None

        return current_hilo.line