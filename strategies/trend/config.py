from dataclasses import dataclass


@dataclass(frozen=True)
class MovingAverageCrossoverConfig:
    fast_period: int = 8
    slow_period: int = 21

    volume_period: int = 20

    # "ema21" or "recent_swing_low"
    stop_mode: str = "ema21"

    # Number of previous candles used to identify recent swing low.
    swing_lookback: int = 5

    stop_buffer: float = 0.0