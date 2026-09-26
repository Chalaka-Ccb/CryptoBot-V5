# patterns/config.py

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternConfig:

    # Wick thresholds
    marubozu_max_wick_ratio: float = 0.05

    # Hanging Man / Shooting Star
    long_wick_body_ratio: float = 2.0
    small_opposite_wick_body_ratio: float = 0.25

    # Body classification
    large_body_range_ratio: float = 0.60
    small_body_range_ratio: float = 0.30

    # 20/20
    twenty_percent: float = 0.20