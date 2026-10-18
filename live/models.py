"""Exchange-neutral live models."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Balance:
    equity: float
    available: float

@dataclass(frozen=True)
class Position:
    side: str
    qty: float
    entry: float
    liquidation: float | None = None

@dataclass(frozen=True)
class Protection:
    sl_price: float | None = None
    tp_price: float | None = None
    sl_ok: bool = False
    tp_ok: bool = False

@dataclass(frozen=True)
class TradePlan:
    side: str
    qty: float
    sl: float
    tp: float
    signal: object
    timeframe: str
    entry_price: float
    client_order_id: str = ""
