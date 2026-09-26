# patterns/bearish/bearish_marubozu.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class BearishMarubozu(BasePattern):

    name = "bearish_marubozu"

    def detect(self, candles):

        if not candles:
            return PatternResult.no_match(self.name)

        candle = candles[-1]

        if candle.range <= 0:
            return PatternResult.no_match(
                self.name,
                "Zero candle range"
            )

        if not candle.is_bearish:
            return PatternResult.no_match(
                self.name,
                "Candle is not bearish"
            )

        body_ratio = candle.body / candle.range

        if body_ratio < self.config.large_body_range_ratio:
            return PatternResult.no_match(
                self.name,
                "Body is not large enough"
            )

        upper_wick_ratio = candle.upper_wick / candle.range
        lower_wick_ratio = candle.lower_wick / candle.range

        if upper_wick_ratio > self.config.marubozu_max_wick_ratio:
            return PatternResult.no_match(
                self.name,
                "Upper wick too large"
            )

        if lower_wick_ratio > self.config.marubozu_max_wick_ratio:
            return PatternResult.no_match(
                self.name,
                "Lower wick too large"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=candle.low,
            reason="Large bearish candle with minimal shadows",
        )