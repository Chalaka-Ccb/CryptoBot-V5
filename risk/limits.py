"""Conservative configurable limits for risk sizing."""
from dataclasses import dataclass
from risk.validation import finite_number


@dataclass(frozen=True)
class QuantityLimits:
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    min_notional: float | None = None

    def __post_init__(self):
        for field in ("minimum", "maximum", "step", "min_notional"):
            value = getattr(self, field)
            if value is not None:
                finite_number(field, value, positive=True)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")


@dataclass(frozen=True)
class RiskLimits:
    leverage: float = 5.0
    max_position_notional: float | None = None
    margin_reserve: float = 0.0

    def __post_init__(self):
        leverage = finite_number("leverage", self.leverage, positive=True)
        if leverage < 1:
            raise ValueError("leverage must be >= 1")
        if self.max_position_notional is not None:
            finite_number("max_position_notional", self.max_position_notional, positive=True)
        reserve = finite_number("margin_reserve", self.margin_reserve)
        if reserve < 0:
            raise ValueError("margin_reserve cannot be negative")
