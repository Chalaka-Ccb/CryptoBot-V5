

from dataclasses import dataclass

from core.models.candle import Candle
from core.models.signal import TradingSignal


@dataclass(frozen=True)
class StrategyEvaluation:
    timeframe: str
    signal: TradingSignal | None


class StrategyCoordinator:

    def __init__(
        self,
        strategies_15m: list,
        strategies_5m: list,
    ):
        self.strategies_15m = strategies_15m
        self.strategies_5m = strategies_5m

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