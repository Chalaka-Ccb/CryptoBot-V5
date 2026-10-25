"""Shared strategy registration for backtesting and live trading."""
from engine.strategy_coordinator import StrategyCoordinator
from strategies.supertrend_dynamic import SupertrendStrategy


def create_strategy_coordinator() -> StrategyCoordinator:
    return StrategyCoordinator(
        strategies_15m=[SupertrendStrategy()],
        strategies_5m=[],
    )
