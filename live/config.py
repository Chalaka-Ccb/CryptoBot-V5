"""Strict live settings. No secrets are written to logs."""
from dataclasses import dataclass
from pathlib import Path
import os


def _dotenv(path=".env"):
    values = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return {**values, **os.environ}


@dataclass(frozen=True)
class LiveConfig:
    symbol: str = "SOL/USDT:USDT"
    risk_percentage: float = 0.05
    leverage: int = 12
    margin_mode: str = "isolated"
    demo: bool = True
    live_confirm: str = ""
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    breakout_expiry_candles: int = 3
    poll_seconds: float = 5.0
    protect_check_seconds: float = 30.0
    protect_retries: int = 3
    max_entry_slippage: float = 0.001
    margin_buffer: float = 0.05
    max_notional: float | None = None
    daily_drawdown_limit: float = 0.05
    data_dir: str = "data"
    log_dir: str = "logs"

    @classmethod
    def from_env(cls, path=".env"):
        e = _dotenv(path)
        def get(name, default):
            return e.get(name, default)
        def number(name, default):
            return float(get(name, default))
        cfg = cls(
            symbol=get("SYMBOL", cls.symbol),
            risk_percentage=number("RISK_PERCENTAGE", cls.risk_percentage),
            leverage=int(get("LEVERAGE", cls.leverage)),
            margin_mode=get("MARGIN_MODE", cls.margin_mode),
            demo=str(get("BITGET_DEMO", "true")).lower() in ("1", "true", "yes"),
            live_confirm=get("LIVE_CONFIRM", ""),
            api_key=get("BITGET_API_KEY", ""),
            api_secret=get("BITGET_API_SECRET", ""),
            api_passphrase=get("BITGET_API_PASSPHRASE", ""),
            breakout_expiry_candles=int(get("BREAKOUT_EXPIRY_CANDLES", 3)),
            poll_seconds=number("POLL_SECONDS", 5),
            protect_check_seconds=number("PROTECT_CHECK_SECONDS", 30),
            protect_retries=int(get("PROTECT_RETRIES", 3)),
            max_entry_slippage=number("MAX_ENTRY_SLIPPAGE", 0.001),
            margin_buffer=number("MARGIN_BUFFER", 0.05),
            max_notional=(number("MAX_NOTIONAL", 0) or None),
            daily_drawdown_limit=number("DAILY_DRAWDOWN_LIMIT", 0.05),
            data_dir=get("DATA_DIR", "data"), log_dir=get("LOG_DIR", "logs"),
        )
        cfg.validate()
        return cfg

    def validate(self):
        if self.symbol != "SOL/USDT:USDT":
            raise ValueError("Live V1 is restricted to SOL/USDT:USDT")
        if not 0 < self.risk_percentage <= 0.05:
            raise ValueError("Risk must be >0 and <= 5%")
        if not 1 <= self.leverage <= 12:
            raise ValueError("Leverage must be between 1 and 12")
        if self.margin_mode != "isolated":
            raise ValueError("Live V1 requires isolated margin")
        if self.breakout_expiry_candles < 1 or self.poll_seconds <= 0:
            raise ValueError("Invalid polling or expiry")
        if self.protect_check_seconds <= 0 or self.protect_retries < 1:
            raise ValueError("Invalid protection settings")
        if not 0 <= self.margin_buffer < 1 or not 0 <= self.max_entry_slippage < 1:
            raise ValueError("Invalid margin buffer or slippage")
        if not 0 < self.daily_drawdown_limit < 1:
            raise ValueError("Invalid drawdown limit")
        if self.max_notional is not None and self.max_notional <= 0:
            raise ValueError("Invalid maximum notional")

    def require_trading_confirmation(self):
        if self.live_confirm != "YES_I_UNDERSTAND":
            raise RuntimeError("Trading disabled: set LIVE_CONFIRM=YES_I_UNDERSTAND")
        if not all((self.api_key, self.api_secret, self.api_passphrase)):
            raise RuntimeError("Missing Bitget API credentials")
