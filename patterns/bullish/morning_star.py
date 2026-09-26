# patterns/bullish/morning_star.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class MorningStar(BasePattern):

    name = "morning_star"

    def detect(self, candles):

        if len(candles) < 3:
            return PatternResult.no_match(
                self.name,
                "Requires 3 candles"
            )

        first = candles[-3]
        star = candles[-2]
        third = candles[-1]

        # First candle must be bearish
        if not first.is_bearish:
            return PatternResult.no_match(
                self.name,
                "First candle is not bearish"
            )

        if first.range <= 0:
            return PatternResult.no_match(self.name)

        first_body_ratio = first.body / first.range

        if first_body_ratio < self.config.large_body_range_ratio:
            return PatternResult.no_match(
                self.name,
                "First candle is not large enough"
            )

        # Star must have small body
        if star.range <= 0:
            return PatternResult.no_match(self.name)

        star_body_ratio = star.body / star.range

        if star_body_ratio > self.config.small_body_range_ratio:
            return PatternResult.no_match(
                self.name,
                "Star body is too large"
            )

        # Star body should not overlap first body
        first_body_high = max(first.open, first.close)
        first_body_low = min(first.open, first.close)

        star_body_high = max(star.open, star.close)
        star_body_low = min(star.open, star.close)

        if (
            star_body_low <= first_body_high
            and star_body_high >= first_body_low
        ):
            return PatternResult.no_match(
                self.name,
                "Star body overlaps first candle body"
            )

        # Third candle must be bullish
        if not third.is_bullish:
            return PatternResult.no_match(
                self.name,
                "Third candle is not bullish"
            )

        # Third candle must close inside first candle body
        if third.close <= first_body_low:
            return PatternResult.no_match(
                self.name,
                "Third candle does not close inside first body"
            )

        if third.close >= first_body_high:
            return PatternResult.no_match(
                self.name,
                "Third candle closes beyond first body"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=third.high,
            reason="Bearish candle, small star, bullish confirmation",
        )