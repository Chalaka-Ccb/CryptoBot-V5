# patterns/bearish/dark_cloud_cover.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class DarkCloudCover(BasePattern):

    name = "dark_cloud_cover"

    def detect(self, candles):

        if len(candles) < 2:
            return PatternResult.no_match(
                self.name,
                "Requires 2 candles"
            )

        previous = candles[-2]
        current = candles[-1]

        if not previous.is_bullish:
            return PatternResult.no_match(
                self.name,
                "Previous candle is not bullish"
            )

        if not current.is_bearish:
            return PatternResult.no_match(
                self.name,
                "Current candle is not bearish"
            )

        if current.open <= previous.high:
            return PatternResult.no_match(
                self.name,
                "No gap above previous high"
            )

        if current.close >= previous.midpoint:
            return PatternResult.no_match(
                self.name,
                "Close does not penetrate previous midpoint"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=current.low,
            reason="Bearish candle gaps above previous high and closes below midpoint",
        )