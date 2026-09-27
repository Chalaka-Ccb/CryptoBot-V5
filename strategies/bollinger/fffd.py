from core.models.candle import Candle
from core.models.signal import SignalSide, TradingSignal
from indicators.bollinger_bands import calculate_bollinger_bands
from strategies.bollinger.config import BollingerConfig


class FFFDStrategy:
    """
    Fechou Fora - Fechou Dentro

    Bullish:
        Previous candle closes below lower BB.
        Current candle closes back above lower BB.
        Trigger = current candle high + offset.

    Bearish:
        Previous candle closes above upper BB.
        Current candle closes back below upper BB.
        Trigger = current candle low - offset.
    """

    name = "fffd"

    def __init__(self, config: BollingerConfig | None = None):
        self.config = config or BollingerConfig()

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1:
            return None

        bands = calculate_bollinger_bands(
            candles,
            period=self.config.period,
            std_multiplier=self.config.std_multiplier,
        )

        previous_band = bands[index - 1]
        current_band = bands[index]

        if previous_band is None or current_band is None:
            return None

        previous = candles[index - 1]
        current = candles[index]

        # -----------------------------------
        # Bullish FFFD
        # -----------------------------------

        outside_lower = (
            previous.close < previous_band.lower
        )

        closed_inside_lower = (
            current.close > current_band.lower
        )

        if outside_lower and closed_inside_lower:

            trigger = (
                current.high
                + self.config.fffd_trigger_offset
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                trigger_price=trigger,
                stop_loss=current.low,
                reason=(
                    "Previous candle closed below "
                    "lower Bollinger Band and current "
                    "candle closed back inside."
                ),
            )

        # -----------------------------------
        # Bearish FFFD
        # -----------------------------------

        outside_upper = (
            previous.close > previous_band.upper
        )

        closed_inside_upper = (
            current.close < current_band.upper
        )

        if outside_upper and closed_inside_upper:

            trigger = (
                current.low
                - self.config.fffd_trigger_offset
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                trigger_price=trigger,
                stop_loss=current.high,
                reason=(
                    "Previous candle closed above "
                    "upper Bollinger Band and current "
                    "candle closed back inside."
                ),
            )

        return None