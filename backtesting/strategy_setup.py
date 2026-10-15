from engine.strategy_coordinator import StrategyCoordinator

# -------------------------------------------------
# Trend strategies
# -------------------------------------------------

from strategies.trend.ema_crossover import (
    EMACrossoverStrategy,
)

from strategies.trend.hilo_macd import (
    HiLoMACDStrategy,
)

# -------------------------------------------------
# Bollinger strategies
# -------------------------------------------------

from strategies.bollinger.fffd import (
    FFFDStrategy,
)

from strategies.bollinger.squeeze import (
    BollingerSqueezeStrategy,
)

from strategies.bollinger.channel_rebound import (
    ChannelReboundStrategy,
)

# -------------------------------------------------
# Breakout strategies
# -------------------------------------------------

from strategies.breakout.nr7 import (
    NR7Strategy,
)

# -------------------------------------------------
# Momentum strategies
# -------------------------------------------------

from strategies.momentum.williams_r import (
    WilliamsRStrategy,
)

# -------------------------------------------------
# Pullback strategies
# -------------------------------------------------

from strategies.pullback.setup_1234 import (
    Setup1234Strategy,
)


def create_strategy_coordinator() -> StrategyCoordinator:
    FFFD_STOP_MODE = "EXTREME"
    FFFD_MIN_BAND_PENETRATION = 0.0
    FFFD_USE_MACD_EXHAUSTION = True
    FFFD_USE_LIQUIDITY_SWEEP = False
    FFFD_MIN_REWARD_RISK = 2.0
    FFFD_USE_SHORT_EMA_FILTER = False
    FFFD_USE_LONG_EMA_FILTER = True
    FFFD_LONG_EMA_PERIOD = 200
    FFFD_LONG_EMA_SLOPE_LOOKBACK = 0
    FFFD_USE_SHORT_RSI_FILTER = True
    FFFD_SHORT_RSI_PERIOD = 14
    FFFD_SHORT_RSI_MODE = "FALLING"
    FFFD_SHORT_RSI_THRESHOLD = 60.0

    strategies_15m = [
         #EMACrossoverStrategy(),
        # HiLoMACDStrategy(),
        # FFFDStrategy(
        #     min_band_penetration=FFFD_MIN_BAND_PENETRATION,
        #     stop_mode=FFFD_STOP_MODE,
        #     use_macd_exhaustion=FFFD_USE_MACD_EXHAUSTION,
        #     use_liquidity_sweep=FFFD_USE_LIQUIDITY_SWEEP,
        #     min_reward_risk=FFFD_MIN_REWARD_RISK,
        #     use_long_ema_filter=FFFD_USE_LONG_EMA_FILTER,
        #     use_short_ema_filter=FFFD_USE_SHORT_EMA_FILTER,
        #     long_ema_period=FFFD_LONG_EMA_PERIOD,
        #     long_ema_slope_lookback=FFFD_LONG_EMA_SLOPE_LOOKBACK,
        #     use_short_rsi_filter=FFFD_USE_SHORT_RSI_FILTER,
        #     short_rsi_period=FFFD_SHORT_RSI_PERIOD,
        #     short_rsi_mode=FFFD_SHORT_RSI_MODE,
        #     short_rsi_threshold=FFFD_SHORT_RSI_THRESHOLD,
        # ),
        ChannelReboundStrategy(),
        #BollingerSqueezeStrategy(),
        #NR7Strategy(),
        #WilliamsRStrategy(),
        #Setup1234Strategy(),
    ]



    strategies_5m = [
         #EMACrossoverStrategy(),
         #HiLoMACDStrategy(),
        # FFFDStrategy(
        #     min_band_penetration=FFFD_MIN_BAND_PENETRATION,
        #     stop_mode=FFFD_STOP_MODE,
        #     use_macd_exhaustion=FFFD_USE_MACD_EXHAUSTION,
        #     use_liquidity_sweep=FFFD_USE_LIQUIDITY_SWEEP,
        #     min_reward_risk=FFFD_MIN_REWARD_RISK,
        #     use_long_ema_filter=FFFD_USE_LONG_EMA_FILTER,
        #     use_short_ema_filter=FFFD_USE_SHORT_EMA_FILTER,
        #     long_ema_period=FFFD_LONG_EMA_PERIOD,
        #     long_ema_slope_lookback=FFFD_LONG_EMA_SLOPE_LOOKBACK,
        #     use_short_rsi_filter=FFFD_USE_SHORT_RSI_FILTER,
        #     short_rsi_period=FFFD_SHORT_RSI_PERIOD,
        #     short_rsi_mode=FFFD_SHORT_RSI_MODE,
        #     short_rsi_threshold=FFFD_SHORT_RSI_THRESHOLD,
        # ),
         #BollingerSqueezeStrategy(),
         ChannelReboundStrategy(),
        # NR7Strategy(),
        #WilliamsRStrategy(),
        #Setup1234Strategy(),
    ]

    return StrategyCoordinator(
        strategies_15m=strategies_15m,
        strategies_5m=strategies_5m,
    )