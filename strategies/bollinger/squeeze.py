from core.models.candle import Candle
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)

from indicators.bollinger_bands import calculate_bollinger_bands
from indicators.volume import calculate_volume_sma

from strategies.bollinger.config import BollingerConfig


class BollingerSqueezeStrategy:
    """
    Bollinger Squeeze (guide section 4.1).

    Concept:
        Prolonged low volatility contracts the bands into a narrow
        neck (bandwidth = (upper - lower) / SMA, far below its
        historical level), signalling an explosive directional
        volatility expansion.

    Squeeze detection:
        The previous candle's bandwidth is the lowest bandwidth of
        the last `squeeze_lookback` candles. No signal is produced
        while the squeeze is still building (cash / reserve is kept).

    Trigger (all required):
        - The candle closes outside the NARROWED band envelope, i.e.
          the previous candle's bands (before the breakout candle
          widened them).
        - Volume surge: current volume > volume SMA of the PRECEDING
          `squeeze_volume_period` candles (the breakout candle itself
          is excluded from the average, as in guide section 5.1).
        - Additional confirmation (not in the guide): bandwidth is
          expanding versus the previous candle.

    Long:
        Close above the previous upper band.
        Entry: breakout above the signal candle high.
        Stop: middle band (SMA 20).

    Short:
        Close below the previous lower band.
        Entry: breakout below the signal candle low.
        Stop: middle band (SMA 20).

    No take profit is set; the engine applies the guide's default
    target (1:3 risk-reward).
    """

    name = "bollinger_squeeze"

    def __init__(self, config: BollingerConfig | None = None):
        self.config = config or BollingerConfig()
        self._cache_key: tuple[int, int] | None = None
        self._bands = []
        self._volume_sma = []

    def _indicators(self, candles: list[Candle]):
        """
        Compute indicators once per candle list instead of on every
        call. Rebuilt when the list object or its length changes
        (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._bands = calculate_bollinger_bands(
                candles,
                period=self.config.period,
                std_multiplier=self.config.std_multiplier,
            )
            self._volume_sma = calculate_volume_sma(
                candles,
                period=self.config.squeeze_volume_period,
            )
            self._cache_key = key

        return self._bands, self._volume_sma

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        lookback = self.config.squeeze_lookback

        if index < max(lookback, 1) or index >= len(candles):
            return None

        bands, volume_sma = self._indicators(candles)

        current_band = bands[index]
        previous_band = bands[index - 1]

        if current_band is None or previous_band is None:
            return None

        # Average volume of the preceding period (excludes the
        # breakout candle).
        preceding_volume_sma = volume_sma[index - 1]

        if preceding_volume_sma is None:
            return None

        # -----------------------------------
        # Check squeeze
        # -----------------------------------

        historical_bandwidths = [
            bands[i].bandwidth
            for i in range(index - lookback, index)
            if bands[i] is not None
        ]

        if not historical_bandwidths:
            return None

        minimum_bandwidth = min(historical_bandwidths)

        was_squeeze = (
            previous_band.bandwidth <= minimum_bandwidth
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
            current.volume > preceding_volume_sma
        )

        if not high_volume:
            return None

        # -----------------------------------
        # Bullish breakout (outside the narrowed envelope)
        # -----------------------------------

        bullish_breakout = (
            current.close > previous_band.upper
        )

        if bullish_breakout:

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                entry_timing=EntryTiming.BREAKOUT,
                trigger_price=current.high,
                stop_loss=current_band.middle,
                diagnostics={"previous_bandwidth": previous_band.bandwidth,
                             "current_bandwidth": current_band.bandwidth,
                             "minimum_bandwidth": minimum_bandwidth,
                             "volume": current.volume, "preceding_volume_sma": preceding_volume_sma,
                             "previous_upper_band": previous_band.upper,
                             "previous_lower_band": previous_band.lower,
                             "current_middle_band": current_band.middle},
                reason=(
                    "Bollinger squeeze followed by "
                    "bullish close above the narrowed upper band "
                    "with band expansion and above-average volume."
                ),
            )

        # -----------------------------------
        # Bearish breakout (outside the narrowed envelope)
        # -----------------------------------

        bearish_breakout = (
            current.close < previous_band.lower
        )

        if bearish_breakout:

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                entry_timing=EntryTiming.BREAKOUT,
                trigger_price=current.low,
                stop_loss=current_band.middle,
                diagnostics={"previous_bandwidth": previous_band.bandwidth,
                             "current_bandwidth": current_band.bandwidth,
                             "minimum_bandwidth": minimum_bandwidth,
                             "volume": current.volume, "preceding_volume_sma": preceding_volume_sma,
                             "previous_upper_band": previous_band.upper,
                             "previous_lower_band": previous_band.lower,
                             "current_middle_band": current_band.middle},
                reason=(
                    "Bollinger squeeze followed by "
                    "bearish close below the narrowed lower band "
                    "with band expansion and above-average volume."
                ),
            )

        return None