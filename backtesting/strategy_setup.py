from engine.strategy_coordinator import StrategyCoordinator
from strategies.trend.hilo_macd import HiLoMACDStrategy


def create_strategy_coordinator() -> StrategyCoordinator:
    """Baseline test: HiLoMACD alone on both supported timeframes."""
    HILO_MACD_CROSS_ABOVE_ZERO = True
    HILO_MACD_USE_EMA_FILTER = True
    HILO_MACD_EMA_PERIOD = 200
    HILO_MACD_USE_ATR_FILTER = True
    HILO_MACD_ATR_PERIOD = 14
    HILO_MACD_ATR_SMA_PERIOD = 50
    HILO_MACD_USE_TRAILING_STOP = False
    HILO_MACD_CROSS_BELOW_ZERO = not HILO_MACD_CROSS_ABOVE_ZERO

    def hilo_macd():
        return HiLoMACDStrategy(
            macd_cross_below_zero=HILO_MACD_CROSS_BELOW_ZERO,
            macd_cross_above_zero=HILO_MACD_CROSS_ABOVE_ZERO,
            use_ema_trend_filter=HILO_MACD_USE_EMA_FILTER,
            ema_trend_period=HILO_MACD_EMA_PERIOD,
            use_atr_volatility_filter=HILO_MACD_USE_ATR_FILTER,
            atr_period=HILO_MACD_ATR_PERIOD,
            atr_sma_period=HILO_MACD_ATR_SMA_PERIOD,
            use_hilo_trailing_stop=HILO_MACD_USE_TRAILING_STOP,
        )

    return StrategyCoordinator(
        strategies_15m=[hilo_macd()],
        strategies_5m=[hilo_macd()],
    )
