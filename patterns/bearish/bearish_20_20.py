# patterns/bearish/bearish_20_20.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class Bearish2020(BasePattern):

    name = "bearish_20_20"

    def detect(self, candles):

        if not candles:
            return PatternResult.no_match(self.name)

        candle = candles[-1]

        if candle.range <= 0:
            return PatternResult.no_match(self.name)

        if not candle.is_bearish:
            return PatternResult.no_match(
                self.name,
                "Candle is not bearish"
            )

        top_20_boundary = candle.high - (
            candle.range * self.config.twenty_percent
        )

        bottom_20_boundary = candle.low + (
            candle.range * self.config.twenty_percent
        )

        if candle.open < top_20_boundary:
            return PatternResult.no_match(
                self.name,
                "Open is not in top 20%"
            )

        if candle.close > bottom_20_boundary:
            return PatternResult.no_match(
                self.name,
                "Close is not in bottom 20%"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=candle.low,
            reason="Bearish candle opening in top 20% and closing in bottom 20%",
        )