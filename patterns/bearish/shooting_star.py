# patterns/bearish/shooting_star.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class ShootingStar(BasePattern):

    name = "shooting_star"

    def detect(self, candles):

        if not candles:
            return PatternResult.no_match(self.name)

        candle = candles[-1]

        if candle.range <= 0 or candle.body <= 0:
            return PatternResult.no_match(self.name)

        if candle.upper_wick < (
            candle.body * self.config.long_wick_body_ratio
        ):
            return PatternResult.no_match(
                self.name,
                "Upper wick is not sufficiently long"
            )

        if candle.lower_wick > (
            candle.body * self.config.small_opposite_wick_body_ratio
        ):
            return PatternResult.no_match(
                self.name,
                "Lower wick is too large"
            )

        body_bottom_distance = min(
            candle.open,
            candle.close
        ) - candle.low

        if body_bottom_distance > candle.range * 0.25:
            return PatternResult.no_match(
                self.name,
                "Body is not near the bottom"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=candle.low,
            reason="Small bottom-positioned body with long upper wick",
        )