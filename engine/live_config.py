"""Environment configuration for the live USDT perpetual engine."""
import os
from dataclasses import dataclass
from pathlib import Path
import math


@dataclass(frozen=True)
class LiveConfig:
    exchange: str = "bybit"
    symbols: tuple[str, ...] = ("SOL/USDT:USDT",)
    sandbox: bool = True
    enabled: bool = False
    leverage: int = 10
    margin_mode: str = "isolated"
    history: int = 1000
    poll_seconds: float = 10.0
    risk_percentage: float = 0.02
    drawdown_percentage: float = 0.05
    drawdown_enabled: bool = False
    default_risk_reward: float = 3.0
    default_stop_percentage: float = 0.01
    breakout_expiry_candles: int = 3
    journal: Path = Path("logs/live-bybit-demo.json")

    def __post_init__(self):
        if self.exchange not in {"bitget", "bybit"}:
            raise ValueError("LIVE_EXCHANGE must be bitget or bybit")
        if not self.symbols or len(set(self.symbols)) != len(self.symbols):
            raise ValueError("Provide unique live symbols")
        if self.margin_mode not in {"isolated", "cross"}:
            raise ValueError("Invalid margin mode")
        if not 1 <= self.leverage <= 10 or not 100 <= self.history <= 1000:
            raise ValueError("Leverage must be 1..10; history must be 100..1000")
        for value in (self.risk_percentage, self.drawdown_percentage):
            if not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError("Risk and drawdown percentages must be in (0, 1]")
        if not math.isfinite(self.poll_seconds) or self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if not math.isfinite(self.default_risk_reward) or self.default_risk_reward <= 0:
            raise ValueError("default_risk_reward must be positive")
        if not math.isfinite(self.default_stop_percentage) or not 0 < self.default_stop_percentage < 1:
            raise ValueError("default_stop_percentage must be in (0, 1)")
        if self.breakout_expiry_candles < 1:
            raise ValueError("breakout_expiry_candles must be >= 1")

    @classmethod
    def from_env(cls):
        def flag(name, default):
            value = os.getenv(name, default).lower()
            if value not in {"true", "false"}:
                raise ValueError(f"{name} must be true or false")
            return value == "true"
        exchange = os.getenv("LIVE_EXCHANGE", "bybit").lower()
        sandbox = flag("LIVE_SANDBOX", "true")
        mode = "demo" if sandbox else "production"
        return cls(
            exchange=exchange,
            symbols=tuple(s.strip() for s in os.getenv("LIVE_SYMBOLS", "SOL/USDT:USDT").split(",") if s.strip()),
            sandbox=sandbox, enabled=flag("LIVE_TRADING_ENABLED", "false"),
            leverage=int(os.getenv("LIVE_LEVERAGE", "10")),
            margin_mode=os.getenv("LIVE_MARGIN_MODE", "isolated"),
            history=int(os.getenv("LIVE_HISTORY", "1000")),
            poll_seconds=float(os.getenv("LIVE_POLL_SECONDS", "10")),
            risk_percentage=float(os.getenv("LIVE_RISK_PERCENTAGE", "0.02")),
            drawdown_percentage=float(os.getenv("LIVE_DRAWDOWN_PERCENTAGE", "0.05")),
            drawdown_enabled=flag("LIVE_DRAWDOWN_ENABLED", "false"),
            default_risk_reward=float(os.getenv("LIVE_RISK_REWARD", "3")),
            default_stop_percentage=float(os.getenv("LIVE_DEFAULT_STOP_PERCENTAGE", "0.01")),
            breakout_expiry_candles=int(os.getenv("LIVE_BREAKOUT_EXPIRY_CANDLES", "3")),
            journal=Path(os.getenv("LIVE_JOURNAL", f"logs/live-{exchange}-{mode}.json")),
        )
