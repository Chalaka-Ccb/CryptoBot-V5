from dataclasses import dataclass
from risk.validation import finite_number


@dataclass(frozen=True)
class RiskLimits:
    max_leverage: float = 10.0
    leverage: float = 10.0
    max_position_notional: float | None = None
    margin_reserve: float = 0.0

    def __post_init__(self):
        maximum = finite_number("max_leverage", self.max_leverage, positive=True)
        leverage = finite_number("leverage", self.leverage, positive=True)
        reserve = finite_number("margin_reserve", self.margin_reserve)
        if maximum < 1 or leverage < 1 or leverage > maximum:
            raise ValueError("Require 1 <= leverage <= max_leverage")
        if reserve < 0:
            raise ValueError("margin_reserve cannot be negative")
        if self.max_position_notional is not None:
            finite_number("max_position_notional", self.max_position_notional, positive=True)


@dataclass(frozen=True)
class QuantityLimits:
    # Base-asset units, NOT an exchange contract count.
    step: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    min_notional: float | None = None

    def __post_init__(self):
        for name in ("step", "minimum", "maximum", "min_notional"):
            value = getattr(self, name)
            if value is not None:
                finite_number(name, value, positive=True)
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("minimum quantity exceeds maximum")
