from core.models.candle import Candle
from core.models.signal import SignalSide, TradingSignal

from indicators.adx import calculate_adx
from indicators.bollinger_bands import calculate_bollinger_bands

from strategies.bollinger.config import BollingerConfig


class ChannelReboundStrategy:
    """
    Bollinger Band channel rebound strategy.

    Designed for ranging markets.

    Long:
        - ADX below threshold
        - Price touches/pierces lower band
        - Bullish confirmation
        - Stop below lower band
        - Target upper band

    Short:
        - ADX below threshold
        - Price touches/pierces upper band
        - Bearish confirmation
        - Stop above upper band
        - Target lower band
    """

    name = "bollinger_channel_rebound"

    def __init__(self, config: BollingerConfig | None = None):
        self.config = config or BollingerConfig()

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < self.config.adx_period:
            return None

        bands = calculate_bollinger_bands(
            candles,
            period=self.config.period,
            std_multiplier=self.config.std_multiplier,
        )

        adx_values = calculate_adx(
            candles,
            period=self.config.adx_period,
        )

        current_band = bands[index]
        adx = adx_values[index]

        if current_band is None or adx is None:
            return None

        # -----------------------------------
        # Regime filter
        # -----------------------------------

        if adx >= self.config.adx_threshold:
            return None

        current = candles[index]

        tolerance = (
            current_band.lower
            * self.config.band_touch_tolerance
        )

        # -----------------------------------
        # Bullish rebound
        # -----------------------------------

        touched_lower_band = (
            current.low
            <= current_band.lower + tolerance
        )

        bullish_confirmation = (
            current.close > current.open
            and current.close > current_band.lower
        )

        if (
            touched_lower_band
            and bullish_confirmation
        ):

            stop_loss = (
                current_band.lower
                * (1 - self.config.stop_buffer_percent)
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                trigger_price=current.high,
                stop_loss=stop_loss,
                take_profit=current_band.upper,
                reason=(
                    "Ranging market with ADX below threshold. "
                    "Price touched lower Bollinger Band and "
                    "formed bullish confirmation."
                ),
            )

        # -----------------------------------
        # Bearish rebound
        # -----------------------------------

        tolerance = (
            current_band.upper
            * self.config.band_touch_tolerance
        )

        touched_upper_band = (
            current.high
            >= current_band.upper - tolerance
        )

        bearish_confirmation = (
            current.close < current.open
            and current.close < current_band.upper
        )

        if (
            touched_upper_band
            and bearish_confirmation
        ):

            stop_loss = (
                current_band.upper
                * (1 + self.config.stop_buffer_percent)
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                trigger_price=current.low,
                stop_loss=stop_loss,
                take_profit=current_band.lower,
                reason=(
                    "Ranging market with ADX below threshold. "
                    "Price touched upper Bollinger Band and "
                    "formed bearish confirmation."
                ),
            )

        return None