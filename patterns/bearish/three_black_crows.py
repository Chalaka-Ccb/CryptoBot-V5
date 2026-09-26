# patterns/bearish/three_black_crows.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class ThreeBlackCrows(BasePattern):

    name = "three_black_crows"

    def detect(self, candles):

        if len(candles) < 3:
            return PatternResult.no_match(
                self.name,
                "Requires 3 candles"
            )

        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]

        sequence = [c1, c2, c3]

        # All bearish
        if not all(c.is_bearish for c in sequence):
            return PatternResult.no_match(
                self.name,
                "Not all candles are bearish"
            )

        # Each candle should close near its low
        for candle in sequence:

            if candle.range <= 0:
                return PatternResult.no_match(
                    self.name,
                    "Zero range candle"
                )

            close_position = (
                candle.close - candle.low
            ) / candle.range

            if close_position > 0.25:
                return PatternResult.no_match(
                    self.name,
                    "Candle does not close near its low"
                )

        # Opens inside previous real body
        for previous, current in zip(sequence, sequence[1:]):

            previous_body_high = max(
                previous.open,
                previous.close
            )

            previous_body_low = min(
                previous.open,
                previous.close
            )

            if current.open > previous_body_high:
                return PatternResult.no_match(
                    self.name,
                    "Current open above previous body"
                )

            if current.open < previous_body_low:
                return PatternResult.no_match(
                    self.name,
                    "Current open below previous body"
                )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=c3.low,
            reason="Three consecutive bearish candles closing near lows",
        )