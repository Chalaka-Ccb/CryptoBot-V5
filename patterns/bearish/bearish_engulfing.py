# patterns/bearish/bearish_engulfing.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class BearishEngulfing(BasePattern):

    name = "bearish_engulfing"

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

        previous_body_high = max(
            previous.open,
            previous.close
        )

        previous_body_low = min(
            previous.open,
            previous.close
        )

        current_body_high = max(
            current.open,
            current.close
        )

        current_body_low = min(
            current.open,
            current.close
        )

        if current_body_high < previous_body_high:
            return PatternResult.no_match(
                self.name,
                "Current body does not engulf previous body"
            )

        if current_body_low > previous_body_low:
            return PatternResult.no_match(
                self.name,
                "Current body does not engulf previous body"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=current.low,
            reason="Bearish body completely engulfs previous bullish body",
        )