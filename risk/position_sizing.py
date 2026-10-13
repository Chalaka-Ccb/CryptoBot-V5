# from dataclasses import dataclass
#
#
# @dataclass(frozen=True)
# class PositionSizeResult:
#     account_capital: float
#     risk_percentage: float
#     max_risk_amount: float
#     risk_per_unit: float
#     position_size: float
#
#
# def calculate_position_size(
#     account_capital: float,
#     risk_percentage: float,
#     entry_price: float,
#     stop_loss_price: float,
# ) -> PositionSizeResult:
#
#     if account_capital <= 0:
#         raise ValueError(
#             "account_capital must be greater than 0"
#         )
#
#     if risk_percentage <= 0:
#         raise ValueError(
#             "risk_percentage must be greater than 0"
#         )
#
#     if entry_price <= 0:
#         raise ValueError(
#             "entry_price must be greater than 0"
#         )
#
#     if stop_loss_price <= 0:
#         raise ValueError(
#             "stop_loss_price must be greater than 0"
#         )
#
#     max_risk_amount = (
#         account_capital * risk_percentage
#     )
#
#     risk_per_unit = abs(
#         entry_price - stop_loss_price
#     )
#
#     if risk_per_unit <= 0:
#         raise ValueError(
#             "entry price and stop-loss price "
#             "cannot be equal"
#         )
#
#     position_size = (
#         max_risk_amount / risk_per_unit
#     )
#
#     return PositionSizeResult(
#         account_capital=account_capital,
#         risk_percentage=risk_percentage,
#         max_risk_amount=max_risk_amount,
#         risk_per_unit=risk_per_unit,
#         position_size=position_size,
#     )


from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from risk.limits import QuantityLimits
from risk.validation import finite_number


@dataclass(frozen=True)
class PositionSizeResult:
    account_capital: float
    risk_percentage: float
    max_risk_amount: float
    risk_per_unit: float
    position_size: float
    actual_risk_amount: float = 0.0
    notional: float = 0.0
    required_margin: float = 0.0


def calculate_position_size(
    account_capital: float,
    risk_percentage: float,
    entry_price: float,
    stop_loss_price: float,
    *,
    max_notional: float | None = None,
    available_margin: float | None = None,
    leverage: float = 10.0,
    quantity_limits: QuantityLimits | None = None,
) -> PositionSizeResult:
    capital = finite_number("account_capital", account_capital, positive=True)
    risk = finite_number("risk_percentage", risk_percentage, positive=True)
    entry = finite_number("entry_price", entry_price, positive=True)
    stop = finite_number("stop_loss_price", stop_loss_price, positive=True)
    lev = finite_number("leverage", leverage, positive=True)
    if risk > 1 or lev < 1:
        raise ValueError("Require risk_percentage <= 1 and leverage >= 1")
    distance = abs(entry - stop)
    if distance == 0:
        raise ValueError("Entry and stop-loss cannot be equal")
    # Decimal arithmetic prevents rounding UP through a quantity-step boundary.
    d = lambda value: Decimal(str(value))
    budget = d(capital) * d(risk)
    quantity = budget / d(distance)
    # Even direct callers receive a default exposure ceiling.
    notional_cap = d(capital) * d(lev)
    if max_notional is not None:
        cap = finite_number("max_notional", max_notional, positive=True)
        notional_cap = min(notional_cap, d(cap))
    quantity = min(quantity, notional_cap / d(entry))
    if available_margin is not None:
        margin = finite_number("available_margin", available_margin)
        if margin <= 0:
            raise ValueError("Insufficient available margin")
        quantity = min(quantity, d(margin) * d(lev) / d(entry))
    limits = quantity_limits or QuantityLimits()
    if limits.maximum is not None:
        quantity = min(quantity, d(limits.maximum))
    if limits.step is not None:
        step = d(limits.step)
        quantity = (quantity / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if quantity <= 0:
        raise ValueError("Quantity is zero after applying limits")
    if limits.minimum is not None and quantity < d(limits.minimum):
        raise ValueError("Quantity is below exchange minimum")
    notional = quantity * d(entry)
    if limits.min_notional is not None and notional < d(limits.min_notional):
        raise ValueError("Notional is below exchange minimum")
    result = PositionSizeResult(
        capital, risk, float(budget), distance, float(quantity),
        float(quantity * d(distance)), float(notional), float(notional / d(lev)),
    )
    for name in ("max_risk_amount", "position_size", "actual_risk_amount", "notional", "required_margin"):
        finite_number(name, getattr(result, name), positive=True)
    return result
