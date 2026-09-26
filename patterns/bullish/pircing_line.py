# patterns/bullish/piercing_line.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class PiercingLine(BasePattern):

    name = "piercing_line"

    def detect(self, candles):

        if len(candles) < 2:
            return PatternResult.no_match(
                self.name,
                "Requires 2 candles"
            )

        previous = candles[-2]
        current = candles[-1]

        if not previous.is_bearish:
            return PatternResult.no_match(
                self.name,
                "Previous candle is not bearish"
            )

        if not current.is_bullish:
            return PatternResult.no_match(
                self.name,
                "Current candle is not bullish"
            )

        # Gap down
        if current.open >= previous.low:
            return PatternResult.no_match(
                self.name,
                "No gap below previous low"
            )

        # Close above previous body midpoint
        if current.close <= previous.midpoint:
            return PatternResult.no_match(
                self.name,
                "Close does not exceed previous midpoint"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=current.high,
            reason="Bullish candle gaps down and closes above previous midpoint",
        )