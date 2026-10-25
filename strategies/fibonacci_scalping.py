"""1-minute Fibonacci retracement scalper.

Swing pivots are confirmed using only past candles. Break of structure is
defined as a close beyond the most recent confirmed pivot in the direction
of a higher-high/higher-low or lower-high/lower-low sequence.
"""
from dataclasses import dataclass
from core.models.candle import Candle
from core.models.signal import TradingSignal, SignalSide, EntryTiming


@dataclass
class FibonacciScalpingStrategy:
    name: str = "FibonacciScalping1m"
    pivot_width: int = 3
    lookback: int = 120
    entry_retracement: float = 0.618
    stop_buffer_pct: float = 0.0005
    min_reward_risk: float = 1.0

    def __post_init__(self):
        if self.pivot_width < 1 or self.lookback < 10:
            raise ValueError("Invalid swing parameters")
        if not 0.5 <= self.entry_retracement <= 0.618:
            raise ValueError("Entry must be inside 0.5–0.618 zone")

    def _pivots(self, candles: list[Candle], index: int):
        width = self.pivot_width
        highs, lows = [], []
        # Pivot at j is confirmed only when j+width <= current index.
        for j in range(max(width, index - self.lookback), index - width + 1):
            segment = candles[j - width:j + width + 1]
            if candles[j].high == max(c.high for c in segment):
                highs.append((j, candles[j].high))
            if candles[j].low == min(c.low for c in segment):
                lows.append((j, candles[j].low))
        return highs, lows

    def generate_signal(self, candles: list[Candle], current_index: int) -> TradingSignal | None:
        i = current_index
        if i < 2 * self.pivot_width + 3 or i >= len(candles):
            return None
        highs, lows = self._pivots(candles, i - 1)
        if len(highs) < 2 or len(lows) < 2:
            return None
        last_high, prior_high = highs[-1], highs[-2]
        last_low, prior_low = lows[-1], lows[-2]
        close, previous = candles[i].close, candles[i - 1].close
        if (last_high[1] > prior_high[1] and last_low[1] > prior_low[1]
                and previous <= last_high[1] < close
                and last_low[0] < i):
            side = SignalSide.LONG
            low, peak = last_low[1], candles[i].high
            entry = peak - (peak - low) * self.entry_retracement
            stop = low * (1 - self.stop_buffer_pct)
            target = peak
            risk, reward = entry - stop, target - entry
        elif (last_high[1] < prior_high[1] and last_low[1] < prior_low[1]
              and previous >= last_low[1] > close
              and last_high[0] < i):
            side = SignalSide.SHORT
            peak, low = last_high[1], candles[i].low
            entry = low + (peak - low) * self.entry_retracement
            stop = peak * (1 + self.stop_buffer_pct)
            target = low
            risk, reward = stop - entry, entry - target
        else:
            return None
        if risk <= 0 or reward / risk < self.min_reward_risk:
            return None
        return TradingSignal(
            strategy=self.name, side=side, candle_index=i,
            entry_timing=EntryTiming.LIMIT, trigger_price=entry,
            stop_loss=stop, take_profit=target,
            reason="Confirmed micro-structure break; 0.618 resting limit",
        )
