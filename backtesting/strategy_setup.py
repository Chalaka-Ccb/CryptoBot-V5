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
    """Baseline test: original EMA Crossover only, on both timeframes."""
    return StrategyCoordinator(
        strategies_15m=[EMACrossoverStrategy()],
        strategies_5m=[EMACrossoverStrategy()],
    )
