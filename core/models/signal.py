from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SignalSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class EntryTiming(str, Enum):
    CURRENT_CLOSE = "current_close"
    NEXT_OPEN = "next_open"
    BREAKOUT = "breakout"
    LIMIT = "limit"


@dataclass(frozen=True)
class TradingSignal:
    strategy: str
    side: SignalSide

    candle_index: int

    entry_timing: EntryTiming

    trigger_price: Optional[float]
    stop_loss: Optional[float]

    take_profit: Optional[float] = None

    reason: str = ""