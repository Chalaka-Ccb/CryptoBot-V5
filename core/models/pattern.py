# core/models/pattern.py

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PatternResult:
    detected: bool
    pattern: str

    candle_index: Optional[int] = None
    entry_price: Optional[float] = None

    reason: Optional[str] = None

    @classmethod
    def no_match(cls, pattern: str, reason: str = ""):
        return cls(
            detected=False,
            pattern=pattern,
            reason=reason,
        )