"""Single-symbol Live V1 configuration; no exchange credentials here."""
from dataclasses import dataclass
from risk.limits import RiskLimits
from risk.validation import finite_number


@dataclass(frozen=True)
class LiveConfig:
    exchange: str = "bitget"
    symbol: str = "SOL/USDT:USDT"
    strategy: str = "bollinger_channel_rebound"
    mode: str = "paper"
    risk_percentage: float = 0.02
    leverage: float = 5.0
    primary_timeframe: str = "15m"
    secondary_timeframe: str = "5m"

    def __post_init__(self):
        if self.exchange != "bitget":
            raise ValueError("Live V1 supports Bitget only")
        if self.symbol != "SOL/USDT:USDT":
            raise ValueError("Live V1 supports SOL/USDT:USDT only")
        if self.strategy != "bollinger_channel_rebound":
            raise ValueError("Live V1 supports Channel Rebound only")
        if self.mode not in ("paper", "live"):
            raise ValueError("mode must be paper or live")
        risk = finite_number("risk_percentage", self.risk_percentage, positive=True)
        if risk > 0.05:
            raise ValueError("Live V1 risk per trade cannot exceed 5%")
        RiskLimits(leverage=self.leverage)
        if (self.primary_timeframe, self.secondary_timeframe) != ("15m", "5m"):
            raise ValueError("Live V1 uses 15m primary and 5m secondary")

    def risk_limits(self, *, margin_reserve: float = 0.0) -> RiskLimits:
        return RiskLimits(leverage=self.leverage, margin_reserve=margin_reserve)
