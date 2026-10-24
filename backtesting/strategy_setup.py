"""Strategy selection for isolated Bollinger Squeeze backtests.

Keep this improvement branch focused on Bollinger Squeeze. Other strategy
implementations are not modified.
"""

from engine.strategy_coordinator import StrategyCoordinator
from strategies.bollinger.squeeze import BollingerSqueezeStrategy


def create_strategy_coordinator() -> StrategyCoordinator:
    return StrategyCoordinator(
        strategies_15m=[],
        strategies_5m=[BollingerSqueezeStrategy()],
    )
