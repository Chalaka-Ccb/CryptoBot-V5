from dataclasses import dataclass
from enum import Enum


class PullbackTrendFilter(str, Enum):
    EMA_200 = "ema_200"
    EMA_21_SLOPE = "ema_21_slope"


@dataclass(frozen=True)
class Setup1234Config:
    trend_filter: PullbackTrendFilter = PullbackTrendFilter.EMA_200

    major_ema_period: int = 200
    slope_ema_period: int = 21

    # Buy-stop offset.
    # For crypto this can represent a price offset rather than a literal tick.
    trigger_offset: float = 0.0

    # Stop buffer below pullback low.
    stop_buffer: float = 0.0

    # Optional risk/reward target.
    risk_reward_ratio: float | None = 2.0

    # Whether the previous swing high should be considered as TP.
    use_previous_swing_high: bool = True