"""Risk and exchange quantity limits for Live V1."""
from dataclasses import dataclass
from risk.validation import finite_number


@dataclass(frozen=True)
class QuantityLimits:
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    min_notional: float | None = None

    def __post_init__(self):
        for name in ("minimum", "maximum", "step", "min_notional"):
            value = getattr(self, name)
            if value is not None:
                finite_number(name, value, positive=True)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")


@dataclass(frozen=True)
class RiskLimits:
    leverage: float = 5.0
    max_position_notional: float | None = None
    margin_reserve: float = 0.0

    def __post_init__(self):
        leverage = finite_number("leverage", self.leverage, positive=True)
        if not 1 <= leverage <= 15:
            raise ValueError("leverage must be between 1 and 15")
        if self.max_position_notional is not None:
            finite_number("max_position_notional", self.max_position_notional, positive=True)
        reserve = finite_number("margin_reserve", self.margin_reserve)
        if reserve < 0:
            raise ValueError("margin_reserve cannot be negative")
