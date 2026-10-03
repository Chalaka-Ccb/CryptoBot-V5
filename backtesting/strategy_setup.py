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

    # -------------------------------------------------
    # 15m strategies
    #
    # 15m has priority over 5m.
    # The order here determines which strategy gets
    # the first opportunity when multiple strategies
    # produce a signal on the same candle.
    # -------------------------------------------------

    strategies_15m = [
        EMACrossoverStrategy(),
        HiLoMACDStrategy(),
        FFFDStrategy(),
        BollingerSqueezeStrategy(),
        ChannelReboundStrategy(),
        #NR7Strategy(),
        WilliamsRStrategy(),
        Setup1234Strategy(),
    ]

    # -------------------------------------------------
    # 5m strategies
    #
    # These are checked only when the 15m timeframe
    # has no signal.
    # -------------------------------------------------

    strategies_5m = [
        EMACrossoverStrategy(),
        HiLoMACDStrategy(),
        FFFDStrategy(),
        BollingerSqueezeStrategy(),
        ChannelReboundStrategy(),
        # NR7Strategy(),
        WilliamsRStrategy(),
        Setup1234Strategy(),
    ]

    return StrategyCoordinator(
        strategies_15m=strategies_15m,
        strategies_5m=strategies_5m,
    )