# patterns/bullish/hammer.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class Hammer(BasePattern):

    name = "hammer"

    def detect(self, candles):

        if not candles:
            return PatternResult.no_match(self.name)

        candle = candles[-1]

        if candle.range <= 0 or candle.body <= 0:
            return PatternResult.no_match(self.name)

        # Long lower wick
        if candle.lower_wick < (
            candle.body * self.config.long_wick_body_ratio
        ):
            return PatternResult.no_match(
                self.name,
                "Lower wick is not sufficiently long"
            )

        # Small upper wick
        if candle.upper_wick > (
            candle.body * self.config.small_opposite_wick_body_ratio
        ):
            return PatternResult.no_match(
                self.name,
                "Upper wick is too large"
            )

        # Body near top of range
        body_top_distance = candle.high - max(
            candle.open,
            candle.close
        )

        if body_top_distance > candle.range * 0.25:
            return PatternResult.no_match(
                self.name,
                "Body is not near the top"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=candle.high,
            reason="Small top-positioned body with long lower wick",
        )