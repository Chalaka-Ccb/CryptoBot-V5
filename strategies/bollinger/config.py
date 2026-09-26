from dataclasses import dataclass


@dataclass(frozen=True)
class BollingerConfig:
    # Bollinger Bands
    period: int = 20
    std_multiplier: float = 2.0

    # FFFD
    fffd_execution_window: int = 2
    fffd_trigger_offset: float = 0.01

    # Squeeze
    squeeze_lookback: int = 20
    squeeze_volume_period: int = 20

    # Channel rebound
    adx_period: int = 14
    adx_threshold: float = 20.0
    band_touch_tolerance: float = 0.002

    # Stop loss
    stop_buffer_percent: float = 0.001