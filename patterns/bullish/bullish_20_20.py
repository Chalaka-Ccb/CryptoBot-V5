# patterns/bullish/bullish_20_20.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class Bullish2020(BasePattern):

    name = "bullish_20_20"

    def detect(self, candles):

        if not candles:
            return PatternResult.no_match(self.name)

        candle = candles[-1]

        if candle.range <= 0:
            return PatternResult.no_match(self.name)

        if not candle.is_bullish:
            return PatternResult.no_match(
                self.name,
                "Candle is not bullish"
            )

        bottom_20_boundary = candle.low + (
            candle.range * self.config.twenty_percent
        )

        top_20_boundary = candle.high - (
            candle.range * self.config.twenty_percent
        )

        # Open must be inside bottom 20%
        if candle.open > bottom_20_boundary:
            return PatternResult.no_match(
                self.name,
                "Open is not in bottom 20%"
            )

        # Close must be inside top 20%
        if candle.close < top_20_boundary:
            return PatternResult.no_match(
                self.name,
                "Close is not in top 20%"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=candle.high,
            reason="Bullish candle opening in bottom 20% and closing in top 20%",
        )