"""Register new strategies here for both backtesting and live trading.

Strategies must expose generate_signal(candles, current_index) and return
a TradingSignal or None. Optional exits/trailing stops are supported by
the existing backtest runner.

15m strategies take priority over 5m strategies.
"""
from engine.strategy_coordinator import StrategyCoordinator


def create_strategy_coordinator() -> StrategyCoordinator:
    strategies_15m = []
    strategies_5m = []

    return StrategyCoordinator(
        strategies_15m=strategies_15m,
        strategies_5m=strategies_5m,
    )
