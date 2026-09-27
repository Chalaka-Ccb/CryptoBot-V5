from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSizeResult:
    account_capital: float
    risk_percentage: float
    max_risk_amount: float
    risk_per_unit: float
    position_size: float


def calculate_position_size(
    account_capital: float,
    risk_percentage: float,
    entry_price: float,
    stop_loss_price: float,
) -> PositionSizeResult:

    if account_capital <= 0:
        raise ValueError(
            "account_capital must be greater than 0"
        )

    if risk_percentage <= 0:
        raise ValueError(
            "risk_percentage must be greater than 0"
        )

    if entry_price <= 0:
        raise ValueError(
            "entry_price must be greater than 0"
        )

    if stop_loss_price <= 0:
        raise ValueError(
            "stop_loss_price must be greater than 0"
        )

    max_risk_amount = (
        account_capital * risk_percentage
    )

    risk_per_unit = abs(
        entry_price - stop_loss_price
    )

    if risk_per_unit <= 0:
        raise ValueError(
            "entry price and stop-loss price "
            "cannot be equal"
        )

    position_size = (
        max_risk_amount / risk_per_unit
    )

    return PositionSizeResult(
        account_capital=account_capital,
        risk_percentage=risk_percentage,
        max_risk_amount=max_risk_amount,
        risk_per_unit=risk_per_unit,
        position_size=position_size,
    )