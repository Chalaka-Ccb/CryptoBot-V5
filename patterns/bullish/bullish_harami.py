# patterns/bullish/bullish_harami.py

from patterns.base import BasePattern
from core.models.pattern import PatternResult


class BullishHarami(BasePattern):

    name = "bullish_harami"

    def detect(self, candles):

        if len(candles) < 2:
            return PatternResult.no_match(
                self.name,
                "Requires 2 candles"
            )

        mother = candles[-2]
        baby = candles[-1]

        if not mother.is_bearish:
            return PatternResult.no_match(
                self.name,
                "Mother candle is not bearish"
            )

        if not baby.is_bullish:
            return PatternResult.no_match(
                self.name,
                "Baby candle is not bullish"
            )

        mother_body_high = max(
            mother.open,
            mother.close
        )

        mother_body_low = min(
            mother.open,
            mother.close
        )

        baby_body_high = max(
            baby.open,
            baby.close
        )

        baby_body_low = min(
            baby.open,
            baby.close
        )

        # Baby body must be completely inside mother body
        if baby_body_high > mother_body_high:
            return PatternResult.no_match(
                self.name,
                "Baby body exceeds mother body"
            )

        if baby_body_low < mother_body_low:
            return PatternResult.no_match(
                self.name,
                "Baby body exceeds mother body"
            )

        return PatternResult(
            detected=True,
            pattern=self.name,
            candle_index=len(candles) - 1,
            entry_price=baby.high,
            reason="Bullish candle contained inside bearish mother body",
        )