from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    # Maximum account risk per trade.
    risk_percentage: float = 0.02

    # Default risk/reward ratio.
    risk_reward_ratio: float = 3.0

    # Daily account drawdown limit.
    daily_drawdown_limit: float = 0.05

    # ATR trailing-stop configuration.
    atr_period: int = 14
    atr_multiplier: float = 2.0

    # EMA trailing-stop configuration.
    ema_trailing_period: int = 9

    # Swing trailing configuration.
    swing_lookback: int = 3