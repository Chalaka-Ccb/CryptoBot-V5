from engine.strategy_coordinator import StrategyCoordinator
from strategies.trend.hilo_macd import HiLoMACDStrategy


def create_strategy_coordinator() -> StrategyCoordinator:
    """Baseline test: HiLoMACD alone on both supported timeframes."""
    HILO_MACD_CROSS_ABOVE_ZERO = True
    HILO_MACD_CROSS_BELOW_ZERO = not HILO_MACD_CROSS_ABOVE_ZERO

    def hilo_macd():
        return HiLoMACDStrategy(
            macd_cross_below_zero=HILO_MACD_CROSS_BELOW_ZERO,
            macd_cross_above_zero=HILO_MACD_CROSS_ABOVE_ZERO,
        )

    return StrategyCoordinator(
        strategies_15m=[hilo_macd()],
        strategies_5m=[hilo_macd()],
    )
