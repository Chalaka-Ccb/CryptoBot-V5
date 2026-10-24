from core.models.candle import Candle
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from indicators.hilo_activator import (
    HiLoTrend,
    calculate_hilo_activator,
)
from indicators.macd import calculate_macd
from indicators.ema import calculate_ema
from indicators.atr import calculate_atr


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
        macd_cross_above_zero: bool = False,
        use_ema_trend_filter: bool = False,
        ema_trend_period: int = 200,
        use_atr_volatility_filter: bool = False,
        atr_period: int = 14,
        atr_sma_period: int = 50,
        use_hilo_trailing_stop: bool = True,
        use_macd_histogram_strength_filter: bool = False,
        histogram_strength_lookback: int = 20,
        histogram_strength_ratio: float = 0.5,
        use_macd_histogram_turn: bool = False,
    ):
        if macd_cross_lookback < 1:
            raise ValueError("macd_cross_lookback must be at least 1")

        self.hilo_period = hilo_period

        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

        self.macd_cross_lookback = macd_cross_lookback
        if macd_cross_below_zero and macd_cross_above_zero:
            raise ValueError("Choose either below-zero or above-zero MACD crossover filtering")
        self.macd_cross_below_zero = macd_cross_below_zero
        self.macd_cross_above_zero = macd_cross_above_zero

        if ema_trend_period < 1:
            raise ValueError("ema_trend_period must be positive")
        self.use_ema_trend_filter = use_ema_trend_filter
        self.ema_trend_period = ema_trend_period
        self._ema_trend = []

        if atr_period < 1 or atr_sma_period < 1:
            raise ValueError("ATR periods must be positive")
        if histogram_strength_lookback < 1 or histogram_strength_ratio < 0:
            raise ValueError("Histogram strength parameters must be non-negative, with lookback >= 1")
        self.use_macd_histogram_turn = use_macd_histogram_turn
        self.use_macd_histogram_strength_filter = use_macd_histogram_strength_filter
        self.histogram_strength_lookback = histogram_strength_lookback
        self.histogram_strength_ratio = histogram_strength_ratio
        self.use_hilo_trailing_stop = use_hilo_trailing_stop
        self.use_atr_volatility_filter = use_atr_volatility_filter
        self.atr_period = atr_period
        self.atr_sma_period = atr_sma_period
        self._atr = []
        self._atr_sma = []

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
            self._ema_trend = (calculate_ema(candles, self.ema_trend_period)
                               if self.use_ema_trend_filter else [])
            if self.use_atr_volatility_filter:
                self._atr = calculate_atr(candles, period=self.atr_period)
                self._atr_sma = [None] * len(candles)
                for j in range(self.atr_period - 1 + self.atr_sma_period - 1, len(candles)):
                    window = self._atr[j - self.atr_sma_period + 1:j + 1]
                    self._atr_sma[j] = sum(window) / self.atr_sma_period
            else:
                self._atr, self._atr_sma = [], []
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
        if self.macd_cross_above_zero and current.macd_line <= 0:
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

        # Stage 3: allow longs only when price is above its trend EMA.
        if self.use_ema_trend_filter:
            trend_ema = self._ema_trend[i]
            if trend_ema is None or candles[i].close <= trend_ema:
                return False

        # Stage 4: reject signals in below-average volatility.
        if self.use_atr_volatility_filter:
            atr = self._atr[i]
            atr_average = self._atr_sma[i]
            if atr is None or atr_average is None or atr < atr_average:
                return False

        # Stage 7: require positive crossover momentum relative to recent MACD activity.
        if self.use_macd_histogram_strength_filter:
            start = i - self.histogram_strength_lookback
            if start < 0:
                return False
            history = self._macd[start:i]
            if any(item is None for item in history):
                return False
            mean_abs_histogram = sum(abs(item.histogram) for item in history) / len(history)
            if current_macd.histogram <= 0 or current_macd.histogram < self.histogram_strength_ratio * mean_abs_histogram:
                return False

        # Alternative Stage 10 trigger: histogram turns upward from a
        # negative pullback, while MACD remains above the zero axis.
        # This replaces the bullish crossover trigger, rather than
        # requiring an impossible positive histogram simultaneously.
        if self.use_macd_histogram_turn:
            if i < 2 or macd[i - 1] is None or macd[i - 2] is None:
                return False
            previous_hist = macd[i - 1].histogram
            older_hist = macd[i - 2].histogram
            return (
                self.macd_cross_above_zero
                and current_macd.macd_line > 0
                and previous_hist < 0
                and previous_hist <= older_hist
                and current_macd.histogram > previous_hist
            )

        # The MACD cross must still be intact.
        if current_macd.macd_line <= current_macd.signal_line:
            return False

        first = max(1, i - self.macd_cross_lookback + 1)

        return any(
            self._macd_crossed_up(macd, j)
            for j in range(first, i + 1)
        )

    def diagnostic_row(self, candles: list[Candle], index: int) -> dict:
        """Read-only snapshot of every entry gate on a completed candle."""
        hilo, macd = self._indicators(candles)
        candle = candles[index]
        h = hilo[index]
        m = macd[index]
        prev = macd[index - 1] if index >= 1 else None
        older = macd[index - 2] if index >= 2 else None
        ema = self._ema_trend[index] if self.use_ema_trend_filter else None
        atr = self._atr[index] if self.use_atr_volatility_filter else None
        atr_avg = self._atr_sma[index] if self.use_atr_volatility_filter else None
        gates = {
            "hilo_bullish": h is not None and h.trend == HiLoTrend.BULLISH,
            "close_above_hilo": h is not None and candle.close > h.line,
            "ema_pass": not self.use_ema_trend_filter or (ema is not None and candle.close > ema),
            "atr_pass": not self.use_atr_volatility_filter or (atr is not None and atr_avg is not None and atr >= atr_avg),
        }
        if self.use_macd_histogram_turn:
            gates["histogram_turn_pass"] = (
                m is not None and prev is not None and older is not None
                and self.macd_cross_above_zero and m.macd_line > 0
                and prev.histogram < 0 and prev.histogram <= older.histogram
                and m.histogram > prev.histogram
            )
        else:
            gates["macd_cross_pass"] = m is not None and m.macd_line > m.signal_line and any(
                self._macd_crossed_up(macd, j)
                for j in range(max(1, index - self.macd_cross_lookback + 1), index + 1)
            )
        if self.use_macd_histogram_strength_filter:
            start = index - self.histogram_strength_lookback
            history = macd[start:index] if start >= 0 else []
            valid = len(history) == self.histogram_strength_lookback and all(x is not None for x in history)
            avg = sum(abs(x.histogram) for x in history) / len(history) if valid else None
            gates["histogram_strength_pass"] = (
                m is not None and avg is not None and m.histogram > 0
                and m.histogram >= self.histogram_strength_ratio * avg
            )
        condition = self._entry_condition(candles, hilo, macd, index)
        previous_condition = self._entry_condition(candles, hilo, macd, index - 1) if index > 0 else False
        row = {
            "timestamp": candle.timestamp.isoformat(),
            "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close,
            "hilo_trend": h.trend.value if h else None,
            "hilo_line": h.line if h else None,
            "hilo_bullish_line": h.bullish_line if h else None,
            "hilo_bearish_line": h.bearish_line if h else None,
            "ema": ema, "atr": atr, "atr_sma": atr_avg,
            "macd_line": m.macd_line if m else None,
            "macd_signal": m.signal_line if m else None,
            "histogram": m.histogram if m else None,
            "histogram_prev": prev.histogram if prev else None,
            "histogram_prev2": older.histogram if older else None,
            "previous_high": candles[index - 1].high if index > 0 else None,
            "condition_pass": condition,
            "previous_condition_pass": previous_condition,
            "signal_candidate": condition and not previous_condition and h is not None and h.line < candle.close,
        }
        row.update(gates)
        row["failed_filters"] = "|".join(name for name, passed in gates.items() if not passed)
        return row

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
            diagnostics={"hilo_line": current_hilo.line, "hilo_trend": str(current_hilo.trend),
                         "macd_line": macd[index].macd_line,
                         "macd_signal": macd[index].signal_line,
                         "macd_histogram": macd[index].histogram,
                         "cross_lookback": self.macd_cross_lookback,
                         "cross_below_zero": self.macd_cross_below_zero,
                         "cross_above_zero": self.macd_cross_above_zero,
                         "trend_ema": self._ema_trend[index] if self.use_ema_trend_filter else None,
                         "atr": self._atr[index] if self.use_atr_volatility_filter else None,
                         "atr_sma": self._atr_sma[index] if self.use_atr_volatility_filter else None,
                         "histogram_strength_ratio": self.histogram_strength_ratio if self.use_macd_histogram_strength_filter else None,
                         "histogram_turn": self.use_macd_histogram_turn},
            reason=(
                "Price closed above the Hi-Lo Activator while the "
                + ("MACD histogram turned upward after a negative pullback. "
                   if self.use_macd_histogram_turn else
                   "MACD line crossed above its signal line with the configured zero-line filter. ")
                + "Entry scheduled for next candle open."
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
        if not self.use_hilo_trailing_stop:
            return None
        if index < 0 or index >= len(candles):
            return None
        hilo, _ = self._indicators(candles)
        current_hilo = hilo[index]
        return current_hilo.line if current_hilo is not None else None
