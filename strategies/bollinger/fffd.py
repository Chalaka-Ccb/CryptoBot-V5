from core.models.candle import Candle
from core.models.signal import (
    TradingSignal,
    SignalSide,
    EntryTiming,
)
from indicators.bollinger_bands import calculate_bollinger_bands
from strategies.bollinger.config import BollingerConfig
from indicators.atr import calculate_atr
from indicators.macd import calculate_macd
from indicators.ema import calculate_ema
class FFFDStrategy:

    name = "fffd"

    def __init__(
            self,
            config: BollingerConfig | None = None,
            min_band_penetration: float = 0.0,
            stop_mode: str = "EXTREME",
            use_macd_exhaustion: bool = False,
            use_liquidity_sweep: bool = False,
            liquidity_lookback: int = 10,
            min_reward_risk: float = 0.0,
            use_long_ema_filter: bool = False,
            long_ema_period: int = 200,
            long_ema_slope_lookback: int = 0,
    ):
        if not 0 <= min_band_penetration < 1:
            raise ValueError("Invalid band penetration")

        allowed_modes = {
            "EXTREME",
            "CANDLE_1",
            "CANDLE_2",
        }

        if stop_mode not in allowed_modes:
            raise ValueError(
                f"Unsupported stop mode: {stop_mode}"
            )
        if liquidity_lookback < 2:
            raise ValueError(
                "liquidity_lookback must be at least 2"
            )
        if min_reward_risk < 0:
            raise ValueError(
                "min_reward_risk cannot be negative"
            )
        if long_ema_period <= 0:
            raise ValueError("long_ema_period must be positive")

        if long_ema_slope_lookback < 0:
            raise ValueError(
                "long_ema_slope_lookback cannot be negative"
            )

        self.use_long_ema_filter = use_long_ema_filter
        self.long_ema_period = long_ema_period
        self.long_ema_slope_lookback = long_ema_slope_lookback
        self.min_reward_risk = min_reward_risk
        self.use_liquidity_sweep = use_liquidity_sweep
        self.liquidity_lookback = liquidity_lookback
        self.config = config or BollingerConfig()
        self.min_band_penetration = min_band_penetration
        self.stop_mode = stop_mode
        self.use_macd_exhaustion = use_macd_exhaustion
        self._cache_key: tuple[int, int] | None = None
        self._bands = []
        self._macd_cache_key: tuple[int, int] | None = None
        self._macd_values = []
        self._ema_cache_key = None
        self._ema_values = []
        # Keep input references alive: live polling creates fresh lists and
        # Python can otherwise reuse an id for different candle contents.
        self._bands_input = None
        self._macd_input = None
        self._ema_input = None

    def _long_ema_confirmed(
            self,
            candles: list[Candle],
            index: int,
    ) -> bool:

        if not self.use_long_ema_filter:
            return True

        if index < (
                self.long_ema_period - 1
                + self.long_ema_slope_lookback
        ):
            return False

        ema_values = calculate_ema(
            candles,
            period=self.long_ema_period,
        )

        current_ema = ema_values[index]

        if current_ema is None:
            return False

        # LONG only when price is above EMA.
        if candles[index].close <= current_ema:
            return False

        if self.long_ema_slope_lookback > 0:
            previous_index = (
                    index - self.long_ema_slope_lookback
            )

            previous_ema = ema_values[previous_index]

            if previous_ema is None:
                return False

            if current_ema <= previous_ema:
                return False

        return True

    def _liquidity_sweep_confirmed(
            self,
            candles: list[Candle],
            index: int,
            side: SignalSide,
    ) -> bool:

        if not self.use_liquidity_sweep:
            return True

        # index - 1 is the outside-band candle.
        # Historical reference candles must end
        # before that candle.
        sweep_index = index - 1
        start = sweep_index - self.liquidity_lookback

        if start < 0:
            return False

        previous_candles = candles[start:sweep_index]

        sweep_candle = candles[sweep_index]
        confirmation_candle = candles[index]

        if side == SignalSide.LONG:
            liquidity_level = min(
                candle.low for candle in previous_candles
            )

            return (
                    sweep_candle.low < liquidity_level
                    and confirmation_candle.close > liquidity_level
            )

        if side == SignalSide.SHORT:
            liquidity_level = max(
                candle.high for candle in previous_candles
            )

            return (
                    sweep_candle.high > liquidity_level
                    and confirmation_candle.close < liquidity_level
            )

        return False

    def _get_long_ema(
            self,
            candles: list[Candle],
    ) -> list[float | None]:

        key = (id(candles), len(candles))

        if key != self._ema_cache_key:
            self._ema_input = candles
            self._ema_values = calculate_ema(
                candles,
                period=self.long_ema_period,
            )
            self._ema_cache_key = key

        return self._ema_values

    def _reward_risk_confirmed(
            self,
            entry_price: float,
            stop_loss: float,
            take_profit: float,
            side: SignalSide,
    ) -> bool:

        if side == SignalSide.LONG:
            risk = entry_price - stop_loss
            reward = take_profit - entry_price

        elif side == SignalSide.SHORT:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit

        else:
            return False

        # Always reject invalid stop or target geometry.
        if risk <= 0 or reward <= 0:
            return False

        reward_risk = reward / risk

        return reward_risk >= self.min_reward_risk

    def _calculate_stop_loss(
            self,
            previous: Candle,
            current: Candle,
            side: SignalSide,
    ) -> float:

        if side == SignalSide.LONG:
            if self.stop_mode == "CANDLE_1":
                base = previous.low
            elif self.stop_mode == "CANDLE_2":
                base = current.low
            else:
                base = min(previous.low, current.low)

            return base * (
                    1 - self.config.stop_buffer_percent
            )

        if side == SignalSide.SHORT:
            if self.stop_mode == "CANDLE_1":
                base = previous.high
            elif self.stop_mode == "CANDLE_2":
                base = current.high
            else:
                base = max(previous.high, current.high)

            return base * (
                    1 + self.config.stop_buffer_percent
            )

        raise ValueError(f"Unsupported side: {side}")

    def _get_macd(self, candles: list[Candle]):
        key = (id(candles), len(candles))

        if key != self._macd_cache_key:
            self._macd_input = candles
            self._macd_values = calculate_macd(candles)
            self._macd_cache_key = key

        return self._macd_values

    def _macd_exhaustion_confirmed(
            self,
            candles: list[Candle],
            index: int,
            side: SignalSide,
    ) -> bool:

        if not self.use_macd_exhaustion:
            return True

        if index < 1:
            return False

        macd = self._get_macd(candles)

        previous = macd[index - 1]
        current = macd[index]

        if previous is None or current is None:
            return False

        previous_hist = previous.histogram
        current_hist = current.histogram

        if side == SignalSide.LONG:
            return (
                    previous_hist < 0
                    and current_hist < 0
                    and current_hist > previous_hist
            )

        if side == SignalSide.SHORT:
            return (
                    previous_hist > 0
                    and current_hist > 0
                    and current_hist < previous_hist
            )

        return False

    def _get_bands(self, candles: list[Candle]):
        """
        Compute Bollinger Bands once per candle list instead of on
        every call. Rebuilt when the list object or its length
        changes (live data appending candles).
        """

        key = (id(candles), len(candles))

        if key != self._cache_key:
            self._bands_input = candles
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
                previous.close
                < previous_band.lower
                * (1 - self.min_band_penetration)
        )

        closed_inside_lower = (
            current.close >= current_band.lower
        )

        # The middle-band target must still be ahead of the entry.

        if (
                outside_lower
                and closed_inside_lower
                and current.close < current_band.middle
                and self._macd_exhaustion_confirmed(
            candles,
            index,
            SignalSide.LONG,
        )
                and self._liquidity_sweep_confirmed(
            candles,
            index,
            SignalSide.LONG,
        )
                and self._long_ema_confirmed(
            candles,
            index,
        )
        ):

            stop_loss = self._calculate_stop_loss(
                previous,
                current,
                SignalSide.LONG,
            )

            if not self._reward_risk_confirmed(
                    entry_price=current.close,
                    stop_loss=stop_loss,
                    take_profit=current_band.middle,
                    side=SignalSide.LONG,
            ):
                return None

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.LONG,
                candle_index=index,
                entry_timing=EntryTiming.CURRENT_CLOSE,
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
                previous.close
                > previous_band.upper
                * (1 + self.min_band_penetration)
        )

        closed_inside_upper = (
            current.close <= current_band.upper
        )

        # The middle-band target must still be ahead of the entry.

        if (
                outside_upper
                and closed_inside_upper
                and current.close > current_band.middle
                and self._macd_exhaustion_confirmed(
            candles,
            index,
            SignalSide.SHORT,
        )
                and self._liquidity_sweep_confirmed(
            candles,
            index,
            SignalSide.SHORT,
        )
        ):
            stop_loss = self._calculate_stop_loss(
                previous,
                current,
                SignalSide.SHORT,
            )

            if not self._reward_risk_confirmed(
                    entry_price=current.close,
                    stop_loss=stop_loss,
                    take_profit=current_band.middle,
                    side=SignalSide.SHORT,
            ):
                return None

            return TradingSignal(
                strategy=self.name,
                side=SignalSide.SHORT,
                candle_index=index,
                entry_timing=EntryTiming.CURRENT_CLOSE,
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
