from dataclasses import dataclass


@dataclass(frozen=True)
class MovingAverageCrossoverConfig:
    fast_period: int = 8
    slow_period: int = 21

    volume_period: int = 20

    # "ema21", "recent_swing_low", or "atr"
    stop_mode: str = "atr"

    # Number of previous candles used to identify recent swing low.
    swing_lookback: int = 5

    stop_buffer: float = 0.0
    atr_period: int = 14
    atr_multiplier: float = 1.5
    # Optional trend-strength entry filter.
    use_adx_filter: bool = False
    adx_period: int = 14
    min_adx: float = 25.0

    # Independent long/short macro-trend entry filters.
    ema_trend_period: int = 200
    use_long_ema_filter: bool = False
    use_short_ema_filter: bool = False
