# patterns/bullish/bullish_hikkake.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class BullishHikkake(BasePattern):

    name = "bullish_hikkake"

    def detect(self, candles):

        if len(candles) < 4:
            return PatternResult.no_match(
                self.name,
                "Requires at least 4 candles"
            )

        mother = candles[-4]
        inside = candles[-3]
        breakdown = candles[-2]
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

        # Step 2: Bearish breakdown
        if breakdown.low >= inside.low:
            return PatternResult.no_match(
                self.name,
                "No downside breakdown"
            )

        if breakdown.high >= inside.high:
            return PatternResult.no_match(
                self.name,
                "Breakdown candle already exceeds inside high"
            )

        # Step 3: Failure above inside high
        if failure.high <= inside.high:
            return PatternResult.no_match(
                self.name,
                "Downside breakdown has not failed"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=inside.high,
            reason="Inside bar followed by failed bearish breakdown",
        )