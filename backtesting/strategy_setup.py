from engine.strategy_coordinator import StrategyCoordinator
from strategies.trend.hilo_macd import HiLoMACDStrategy


def create_strategy_coordinator() -> StrategyCoordinator:
    """Baseline test: HiLoMACD alone on both supported timeframes."""
    return StrategyCoordinator(
        strategies_15m=[HiLoMACDStrategy()],
        strategies_5m=[HiLoMACDStrategy()],
    )
