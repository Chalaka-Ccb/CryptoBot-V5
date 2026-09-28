from engine.strategy_coordinator import StrategyCoordinator

from strategies.trend.ema_crossover import (
    EMACrossoverStrategy,
)

from strategies.trend.hilo_macd import (
    HiLoMACDStrategy,
)


def create_strategy_coordinator() -> StrategyCoordinator:

    strategies_15m = [
        EMACrossoverStrategy(),
        HiLoMACDStrategy(),
    ]

    strategies_5m = [
        EMACrossoverStrategy(),
        HiLoMACDStrategy(),
    ]

    return StrategyCoordinator(
        strategies_15m=strategies_15m,
        strategies_5m=strategies_5m,
    )