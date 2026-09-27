from core.models.candle import Candle
from core.models.signal import SignalSide, TradingSignal

from indicators.bollinger_bands import calculate_bollinger_bands
from indicators.volume import calculate_volume_sma

from strategies.bollinger.config import BollingerConfig


class BollingerSqueezeStrategy:
    """
    Detects low-volatility Bollinger Band squeezes
    followed by a volatility expansion breakout.
    """

    name = "bollinger_squeeze"

    def __init__(self, config: BollingerConfig | None = None):
        self.config = config or BollingerConfig()

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        lookback = self.config.squeeze_lookback

        if index < lookback:
            return None

        bands = calculate_bollinger_bands(
            candles,
            period=self.config.period,
            std_multiplier=self.config.std_multiplier,
        )

        volume_sma = calculate_volume_sma(
            candles,
            period=self.config.squeeze_volume_period,
        )

        current_band = bands[index]

        if current_band is None:
            return None

        current_volume_sma = volume_sma[index]

        if current_volume_sma is None:
            return None

        # -----------------------------------
        # Check squeeze
        # -----------------------------------

        historical_bandwidths = []

        start = index - lookback

        for i in range(start, index):
            if bands[i] is not None:
                historical_bandwidths.append(
                    bands[i].bandwidth
                )

        if not historical_bandwidths:
            return None

        minimum_bandwidth = min(
            historical_bandwidths
        )

        previous_band = bands[index - 1]

        if previous_band is None:
            return None

        was_squeeze = (
            previous_band.bandwidth
            <= minimum_bandwidth
        )

        # -----------------------------------
        # Require expansion
        # -----------------------------------

        bandwidth_expanding = (
            current_band.bandwidth
            > previous_band.bandwidth
        )

        if not was_squeeze or not bandwidth_expanding:
            return None

        current = candles[index]

        # -----------------------------------
        # Volume confirmation
        # -----------------------------------

        high_volume = (
            current.volume > current_volume_sma
        )

        if not high_volume:
            return None

        # -----------------------------------
        # Bullish breakout
        # -----------------------------------

        bullish_breakout = (
            current.close > current_band.upper
        )

        if bullish_breakout:

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                trigger_price=current.high,
                stop_loss=current_band.middle,
                reason=(
                    "Bollinger squeeze followed by "
                    "bullish upper-band breakout with "
                    "band expansion and above-average volume."
                ),
            )

        # -----------------------------------
        # Bearish breakout
        # -----------------------------------

        bearish_breakout = (
            current.close < current_band.lower
        )

        if bearish_breakout:

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                trigger_price=current.low,
                stop_loss=current_band.middle,
                reason=(
                    "Bollinger squeeze followed by "
                    "bearish lower-band breakout with "
                    "band expansion and above-average volume."
                ),
            )

        return None