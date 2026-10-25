"""TEMA + ADX + CMO momentum strategy.

Compatible with the shared TradingSignal / StrategyCoordinator interface.
Uses price-based stops/targets converted from leveraged ROI assumptions.
"""
from dataclasses import dataclass
from core.models.candle import Candle
from core.models.signal import EntryTiming, SignalSide, TradingSignal
from indicators.tema import calculate_tema
from indicators.cmo import calculate_cmo
from indicators.dmi import calculate_dmi


@dataclass
class TemaAdxCmoStrategy:
    name: str = "TemaAdxCmo"
    tema_period: int = 9
    adx_period: int = 14
    adx_threshold: float = 25.0
    cmo_period: int = 14
    cmo_threshold: float = 0.0
    assumed_leverage: float = 5.0
    leveraged_stop_roi: float = 0.152
    leveraged_take_profit_roi: float = 0.12
    use_reversal_exit: bool = False

    def __post_init__(self):
        if min(self.tema_period, self.adx_period, self.cmo_period) < 1:
            raise ValueError("Indicator periods must be positive")
        if self.assumed_leverage <= 0 or self.leveraged_stop_roi <= 0:
            raise ValueError("Leverage and stop ROI must be positive")
        if self.leveraged_take_profit_roi <= 0:
            raise ValueError("Take-profit ROI must be positive")
        if self.cmo_threshold < 0:
            raise ValueError("CMO threshold must be nonnegative")

    def _state(self, candles: list[Candle], index: int) -> SignalSide | None:
        if index < 0 or index >= len(candles):
            return None
        history = candles[:index + 1]
        tema = calculate_tema(history, self.tema_period)[-1]
        dmi = calculate_dmi(history, self.adx_period)[-1]
        cmo = calculate_cmo(history, self.cmo_period)[-1]
        if tema is None or dmi is None or dmi.adx is None or cmo is None:
            return None
        if dmi.adx <= self.adx_threshold:
            return None
        close = candles[index].close
        if close > tema and dmi.plus_di > dmi.minus_di and cmo > self.cmo_threshold:
            return SignalSide.LONG
        if close < tema and dmi.minus_di > dmi.plus_di and cmo < -self.cmo_threshold:
            return SignalSide.SHORT
        return None

    def generate_signal(self, candles: list[Candle], current_index: int) -> TradingSignal | None:
        if current_index < 1:
            return None
        side = self._state(candles, current_index)
        if side is None or self._state(candles, current_index - 1) == side:
            return None  # New alignment only; avoids re-entering every candle.
        price = candles[current_index].close
        stop_distance = self.leveraged_stop_roi / self.assumed_leverage
        tp_distance = self.leveraged_take_profit_roi / self.assumed_leverage
        if side == SignalSide.LONG:
            stop, tp = price * (1 - stop_distance), price * (1 + tp_distance)
        else:
            stop, tp = price * (1 + stop_distance), price * (1 - tp_distance)
        if stop <= 0 or tp <= 0:
            return None
        return TradingSignal(strategy=self.name, side=side,
                             candle_index=current_index,
                             entry_timing=EntryTiming.CURRENT_CLOSE,
                             trigger_price=price, stop_loss=stop,
                             take_profit=tp,
                             reason="New TEMA/ADX/DI/CMO alignment")

    def should_exit_long(self, candles: list[Candle], index: int) -> bool:
        return self.use_reversal_exit and self._reversed(candles, index, SignalSide.LONG)

    def should_exit_short(self, candles: list[Candle], index: int) -> bool:
        return self.use_reversal_exit and self._reversed(candles, index, SignalSide.SHORT)

    def _reversed(self, candles: list[Candle], index: int, side: SignalSide) -> bool:
        history = candles[:index + 1]
        tema = calculate_tema(history, self.tema_period)[-1]
        dmi = calculate_dmi(history, self.adx_period)[-1]
        if tema is None or dmi is None:
            return False
        if side == SignalSide.LONG:
            return candles[index].close < tema or dmi.minus_di > dmi.plus_di
        return candles[index].close > tema or dmi.plus_di > dmi.minus_di
