from core.models.candle import Candle
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)
from indicators.bollinger_bands import calculate_bollinger_bands
from strategies.bollinger.config import BollingerConfig


# The guide (section 4.1, Step 3) enters immediately on the close of
# candle (t). If your EntryTiming enum has a CLOSE member it is used;
# otherwise this falls back to BREAKOUT with trigger_price = close.
# Replace with the exact member name from core/models/signal.py.
IMMEDIATE_ENTRY = getattr(EntryTiming, "CLOSE", EntryTiming.BREAKOUT)


class FFFDStrategy:
    """
    Fechou Fora - Fechou Dentro (Closed Outside - Closed Inside)

    Statistical mean-reversion counter-trend setup (guide section 4.1).

    Bullish:
        Step 1: Candle (t-1) closes strictly below the lower band.
        Step 2: Candle (t) closes back inside (close >= lower band).
        Step 3: Enter immediately on the close of candle (t).
        Step 4: Stop beyond the low wick that extended outside the
                band (candle t-1 low, or candle t low if it is lower),
                minus stop buffer.
        Step 5: Take profit at the middle band (SMA 20).

    Bearish:
        Step 1: Candle (t-1) closes strictly above the upper band.
        Step 2: Candle (t) closes back inside (close <= upper band).
        Step 3: Enter immediately on the close of candle (t).
        Step 4: Stop beyond the high wick that extended outside the
                band (candle t-1 high, or candle t high if it is
                higher), plus stop buffer.
        Step 5: Take profit at the middle band (SMA 20).

    Macro filters (SMA 200, volume vs. volume MA) and the 1:3
    risk-reward check are applied by the Signal Resolver / Risk
    Manager, not by this class.
    """

    name = "fffd"

    def __init__(self, config: BollingerConfig | None = None):
        self.config = config or BollingerConfig()
        self._cache_key: tuple[int, int] | None = None
        self._bands = []

    def _get_bands(self, candles: list[Candle]):
        """
        Compute Bollinger Bands once per candle list instead of on
        every call. Rebuilt when the list object or its length
        changes (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._bands = calculate_bollinger_bands(
                candles,
                period=self.config.period,
                std_multiplier=self.config.std_multiplier,
            )
            self._cache_key = key

        return self._bands

    def generate_signal(
        self,
        candles: list[Candle],
        index: int,
    ) -> TradingSignal | None:

        if index < 1 or index >= len(candles):
            return None

        bands = self._get_bands(candles)

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
            current.close >= current_band.lower
        )

        if outside_lower and closed_inside_lower:

            stop_loss = (
                min(previous.low, current.low)
                * (1 - self.config.stop_buffer_percent)
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                entry_timing=IMMEDIATE_ENTRY,
                trigger_price=current.close,
                stop_loss=stop_loss,
                take_profit=current_band.middle,
                reason=(
                    "Previous candle closed below the lower "
                    "Bollinger Band and the current candle closed "
                    "back inside. Entry on close, stop beyond the "
                    "outside wick, target at the middle band."
                ),
            )

        # -----------------------------------
        # Bearish FFFD
        # -----------------------------------

        outside_upper = (
            previous.close > previous_band.upper
        )

        closed_inside_upper = (
            current.close <= current_band.upper
        )

        if outside_upper and closed_inside_upper:

            stop_loss = (
                max(previous.high, current.high)
                * (1 + self.config.stop_buffer_percent)
            )

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                entry_timing=IMMEDIATE_ENTRY,
                trigger_price=current.close,
                stop_loss=stop_loss,
                take_profit=current_band.middle,
                reason=(
                    "Previous candle closed above the upper "
                    "Bollinger Band and the current candle closed "
                    "back inside. Entry on close, stop beyond the "
                    "outside wick, target at the middle band."
                ),
            )

        return None