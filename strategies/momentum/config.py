from dataclasses import dataclass


@dataclass(frozen=True)
class WilliamsRStrategyConfig:
    period: int = 14

    oversold: float = -80.0
    overbought: float = -20.0

    # True = enter at current candle close.
    # False = use current candle high (long) / low (short) as trigger.
    enter_at_close: bool = True

    # Used when entering on breakout of signal candle.
    trigger_offset: float = 0.0

    # Guide sell trigger (%R crosses back below overbought) always
    # closes an open long. When True it also opens a short.
    enable_short: bool = True