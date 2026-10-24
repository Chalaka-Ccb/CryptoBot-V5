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
    HILO_MACD_USE_TRAILING_STOP = True
    HILO_MACD_FAST = 12
    HILO_MACD_SLOW = 26
    HILO_MACD_SIGNAL = 9
    HILO_MACD_USE_HISTOGRAM_STRENGTH = False
    HILO_MACD_USE_HISTOGRAM_TURN = True
    HILO_MACD_REQUIRE_15M_HILO_FOR_5M = True
    HILO_MACD_CONFIRMATION_HILO_PERIOD = 3
    HILO_MACD_HISTOGRAM_LOOKBACK = 20
    HILO_MACD_HISTOGRAM_RATIO = 0.2
    HILO_MACD_CROSS_BELOW_ZERO = not HILO_MACD_CROSS_ABOVE_ZERO

    def hilo_macd():
        return HiLoMACDStrategy(
            macd_fast=HILO_MACD_FAST,
            use_macd_histogram_turn=HILO_MACD_USE_HISTOGRAM_TURN,
            macd_slow=HILO_MACD_SLOW,
            macd_signal=HILO_MACD_SIGNAL,
            use_macd_histogram_strength_filter=HILO_MACD_USE_HISTOGRAM_STRENGTH,
            histogram_strength_lookback=HILO_MACD_HISTOGRAM_LOOKBACK,
            histogram_strength_ratio=HILO_MACD_HISTOGRAM_RATIO,
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
        require_15m_hilo_for_5m=HILO_MACD_REQUIRE_15M_HILO_FOR_5M,
        confirmation_hilo_period=HILO_MACD_CONFIRMATION_HILO_PERIOD,
    )
