from dataclasses import dataclass
from enum import Enum


class PullbackTrendFilter(str, Enum):
    # Guide section 2.1 (3): price vs. 200-day SMA.
    SMA_200 = "sma_200"
    EMA_200 = "ema_200"
    EMA_21_SLOPE = "ema_21_slope"
    # No strategy-level filter (use when the engine applies the
    # macro trend filter itself).
    NONE = "none"


@dataclass(frozen=True)
class Setup1234Config:
    # Higher-timeframe trend filter. Guide default is the 200 SMA.
    trend_filter: PullbackTrendFilter = PullbackTrendFilter.SMA_200

    # Period used by SMA_200 / EMA_200.
    major_ema_period: int = 200
    slope_ema_period: int = 21

    # Point 1 search window: Point 1 is the lowest low (bullish) or
    # highest high (bearish) of the last `swing_lookback` candles
    # ending at Point 3. Must be greater than `pivot_strength`.
    swing_lookback: int = 20

    # Point 3 is a pivot (lowest low / highest high versus the
    # `pivot_strength` candles on each side). The signal is produced
    # `pivot_strength` candles after Point 3, when it is confirmed.
    pivot_strength: int = 2

    # Buy-stop / sell-stop offset beyond Point 2.
    # For crypto this can represent a price offset rather than a literal tick.
    trigger_offset: float = 0.0

    # Stop buffer beyond Point 3.
    stop_buffer: float = 0.0

    # Risk/reward target. Guide default is 1:3. None = no TP, the
    # engine applies its own default.
    risk_reward_ratio: float | None = 3.0

    # Legacy field from the previous consecutive-lower-lows version.
    # Not used by the guide's 1-2-3-4 reversal model; kept so existing
    # code that builds this config does not break.
    use_previous_swing_high: bool = True

    # Guide describes the bearish mirror (lower high at Point 3).
    enable_short: bool = True