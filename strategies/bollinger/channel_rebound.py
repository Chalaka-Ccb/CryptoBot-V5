from core.models.candle import Candle
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)

from indicators.adx import calculate_adx
from indicators.bollinger_bands import calculate_bollinger_bands
from indicators.rsi import calculate_rsi

from strategies.bollinger.config import BollingerConfig


class ChannelReboundStrategy:
    """
    Bollinger Band channel rebound strategy (guide section 4.1).

    Concept:
        In ranging or mild trending regimes, the outer Bollinger Bands
        act as dynamic support and resistance. Mean-reversion trades are
        taken when price reaches an outer band AND a momentum oscillator
        (RSI / IFR) confirms oversold / overbought conditions.

    Regime filter:
        ADX below `adx_threshold` (excludes strong trends only, so
        ranging and mild trending markets pass).

    Long:
        - ADX below threshold
        - Low touches / pierces the lower band (within tolerance)
        - RSI oversold (<= oversold level) on this candle or the
          previous one
        - Bullish confirmation: close > open and close back above
          the lower band
        - Stop below the lower band or the candle low, whichever is
          lower, minus buffer
        - Target upper band

    Short:
        - ADX below threshold
        - High touches / pierces the upper band (within tolerance)
        - RSI overbought (>= overbought level) on this candle or the
          previous one
        - Bearish confirmation: close < open and close back below
          the upper band
        - Stop above the upper band or the candle high, whichever is
          higher, plus buffer
        - Target lower band

    Entry:
        Breakout-style stop entry beyond the signal candle
        (long above its high, short below its low).

    Optional config fields (defaults used if missing from the config):
        rsi_period = 14
        rsi_oversold = 30
        rsi_overbought = 70
    """

    name = "bollinger_channel_rebound"

    def __init__(self, config: BollingerConfig | None = None):
        self.config = config or BollingerConfig()
        self._cache_key: tuple[int, int] | None = None
        self._bands = []
        self._adx = []
        self._rsi = []

    def _indicators(self, candles: list[Candle]):
        """
        Compute indicators once per candle list instead of on every
        call. The cache is rebuilt whenever the list object or its
        length changes (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._bands = calculate_bollinger_bands(
                candles,
                period=self.config.period,
                std_multiplier=self.config.std_multiplier,
            )
            self._adx = calculate_adx(
                candles,
                period=self.config.adx_period,
            )
            self._rsi = calculate_rsi(
                candles,
                period=getattr(self.config, "rsi_period", 14),
            )
            self._cache_key = key

        return self._bands, self._adx, self._rsi

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1 or index >= len(candles):
            return None

        bands, adx_values, rsi_values = self._indicators(candles)

        current_band = bands[index]
        adx = adx_values[index]
        rsi = rsi_values[index]
        previous_rsi = rsi_values[index - 1]

        if current_band is None or adx is None or rsi is None:
            return None

        # -----------------------------------
        # Regime filter (ranging / mild trend)
        # -----------------------------------

        if adx >= self.config.adx_threshold:
            return None

        current = candles[index]

        oversold = getattr(self.config, "rsi_oversold", 30)
        overbought = getattr(self.config, "rsi_overbought", 70)

        recent_rsi_low = (
            min(rsi, previous_rsi)
            if previous_rsi is not None
            else rsi
        )
        recent_rsi_high = (
            max(rsi, previous_rsi)
            if previous_rsi is not None
            else rsi
        )

        # -----------------------------------
        # Bullish rebound
        # -----------------------------------

        lower_tolerance = (
            current_band.lower
            * self.config.band_touch_tolerance
        )

        touched_lower_band = (
            current.low
            <= current_band.lower + lower_tolerance
        )

        rsi_oversold = recent_rsi_low <= oversold

        bullish_confirmation = (
            current.close > current.open
            and current.close > current_band.lower
        )

        if (
            touched_lower_band
            and rsi_oversold
            and bullish_confirmation
        ):

            stop_loss = (
                min(current_band.lower, current.low)
                * (1 - self.config.stop_buffer_percent)
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                entry_timing=EntryTiming.BREAKOUT,
                trigger_price=current.high,
                stop_loss=stop_loss,
                take_profit=current_band.upper,
                reason=(
                    "ADX below threshold (range or mild trend). "
                    "Price touched lower Bollinger Band, RSI "
                    "confirmed oversold, and a bullish candle "
                    "closed back above the band."
                ),
            )

        # -----------------------------------
        # Bearish rebound
        # -----------------------------------

        upper_tolerance = (
            current_band.upper
            * self.config.band_touch_tolerance
        )

        touched_upper_band = (
            current.high
            >= current_band.upper - upper_tolerance
        )

        rsi_overbought = recent_rsi_high >= overbought

        bearish_confirmation = (
            current.close < current.open
            and current.close < current_band.upper
        )

        if (
            touched_upper_band
            and rsi_overbought
            and bearish_confirmation
        ):

            stop_loss = (
                max(current_band.upper, current.high)
                * (1 + self.config.stop_buffer_percent)
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                entry_timing=EntryTiming.BREAKOUT,
                trigger_price=current.low,
                stop_loss=stop_loss,
                take_profit=current_band.lower,
                reason=(
                    "ADX below threshold (range or mild trend). "
                    "Price touched upper Bollinger Band, RSI "
                    "confirmed overbought, and a bearish candle "
                    "closed back below the band."
                ),
            )

        return None