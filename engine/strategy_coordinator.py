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

    def evaluate_15m(
        self,
        candles: list[Candle],
    ) -> StrategyEvaluation:

        signal = self._evaluate_strategies(
            strategies=self.strategies_15m,
            candles=candles,
        )

        return StrategyEvaluation(
            timeframe="15m",
            signal=signal,
        )

    def evaluate_5m(
        self,
        candles: list[Candle],
    ) -> StrategyEvaluation:

        signal = self._evaluate_strategies(
            strategies=self.strategies_5m,
            candles=candles,
        )

        return StrategyEvaluation(
            timeframe="5m",
            signal=signal,
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