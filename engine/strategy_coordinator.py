

from dataclasses import dataclass

from core.models.candle import Candle
from core.models.signal import TradingSignal
from indicators.hilo_activator import calculate_hilo_activator, HiLoTrend


@dataclass(frozen=True)
class StrategyEvaluation:
    timeframe: str
    signal: TradingSignal | None


class StrategyCoordinator:

    def __init__(
        self,
        strategies_15m: list,
        strategies_5m: list,
        require_15m_hilo_for_5m: bool = False,
        confirmation_hilo_period: int = 3,
    ):
        self.strategies_15m = strategies_15m
        self.strategies_5m = strategies_5m
        self.require_15m_hilo_for_5m = require_15m_hilo_for_5m
        self.confirmation_hilo_period = confirmation_hilo_period
        if confirmation_hilo_period < 1:
            raise ValueError("confirmation_hilo_period must be positive")

    def evaluate(
        self,
        candles_15m: list[Candle],
        candles_5m: list[Candle],
    ) -> StrategyEvaluation:

        # -------------------------------------------------
        # 15m has priority
        # -------------------------------------------------

        signal = self._evaluate_strategies(
            strategies=self.strategies_15m,
            candles=candles_15m,
        )

        if signal is not None:
            return StrategyEvaluation(
                timeframe="15m",
                signal=signal,
            )

        # -------------------------------------------------
        # Only check 5m when 15m has no signal
        # -------------------------------------------------

        signal = self._evaluate_strategies(
            strategies=self.strategies_5m,
            candles=candles_5m,
        )

        if signal is not None:
            return StrategyEvaluation(
                timeframe="5m",
                signal=signal,
            )

        return StrategyEvaluation(
            timeframe="none",
            signal=None,
        )

    def evaluate_5m_with_15m_confirmation(
        self,
        candles_5m: list[Candle],
        closed_candles_15m: list[Candle],
    ) -> StrategyEvaluation:
        """Evaluate 5m using only the 15m bars already closed at this time."""
        signal = self._evaluate_strategies(self.strategies_5m, candles_5m)
        if signal is None:
            return StrategyEvaluation(timeframe="none", signal=None)

        if self.require_15m_hilo_for_5m:
            if not closed_candles_15m:
                return StrategyEvaluation(timeframe="none", signal=None)
            hilo = calculate_hilo_activator(
                closed_candles_15m, period=self.confirmation_hilo_period
            )
            last = hilo[-1] if hilo else None
            if (
                last is None
                or last.trend != HiLoTrend.BULLISH
                or closed_candles_15m[-1].close <= last.line
            ):
                return StrategyEvaluation(timeframe="none", signal=None)

        return StrategyEvaluation(timeframe="5m", signal=signal)

    @staticmethod
    def _evaluate_strategies(
        strategies: list,
        candles: list[Candle],
    ) -> TradingSignal | None:

        if not candles:
            return None

        current_index = len(candles) - 1

        for strategy in strategies:

            signal = strategy.generate_signal(
                candles,
                current_index,
            )

            if signal is not None:
                return signal

        return None