# patterns/bearish/bearish_hikkake.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class BearishHikkake(BasePattern):

    name = "bearish_hikkake"

    def detect(self, candles):

        if len(candles) < 4:
            return PatternResult.no_match(
                self.name,
                "Requires at least 4 candles"
            )

        # We search backwards for:
        #
        # mother
        # inside
        # false breakout
        # failure

        mother = candles[-4]
        inside = candles[-3]
        breakout = candles[-2]
        failure = candles[-1]

        # Step 1: Inside bar
        if inside.high > mother.high:
            return PatternResult.no_match(
                self.name,
                "No inside bar high containment"
            )

        if inside.low < mother.low:
            return PatternResult.no_match(
                self.name,
                "No inside bar low containment"
            )

        # Step 2: Bullish false breakout
        if breakout.high <= inside.high:
            return PatternResult.no_match(
                self.name,
                "No upside breakout"
            )

        if breakout.low <= inside.low:
            return PatternResult.no_match(
                self.name,
                "Breakout candle already violates inside low"
            )

        # Step 3: Failure below inside-bar low
        if failure.low >= inside.low:
            return PatternResult.no_match(
                self.name,
                "Upside breakout has not failed"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=inside.low,
            reason="Inside bar followed by failed bullish breakout",
        )