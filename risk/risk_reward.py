from dataclasses import dataclass

from core.models.signal import SignalSide


@dataclass(frozen=True)
class RiskRewardResult:
    entry_price: float
    stop_loss: float
    risk_distance: float
    risk_reward_ratio: float
    take_profit: float


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    side: SignalSide,
    risk_reward_ratio: float = 3.0,
) -> RiskRewardResult:

    if entry_price <= 0:
        raise ValueError(
            "entry_price must be greater than 0"
        )

    if stop_loss <= 0:
        raise ValueError(
            "stop_loss must be greater than 0"
        )

    if risk_reward_ratio <= 0:
        raise ValueError(
            "risk_reward_ratio must be greater than 0"
        )

    risk_distance = abs(
        entry_price - stop_loss
    )

    if risk_distance <= 0:
        raise ValueError(
            "entry price and stop-loss cannot be equal"
        )

    if side == SignalSide.LONG:
        take_profit = (
            entry_price
            + risk_distance * risk_reward_ratio
        )

    elif side == SignalSide.SHORT:
        take_profit = (
            entry_price
            - risk_distance * risk_reward_ratio
        )

    else:
        raise ValueError(
            f"Unsupported signal side: {side}"
        )

    return RiskRewardResult(
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_distance=risk_distance,
        risk_reward_ratio=risk_reward_ratio,
        take_profit=take_profit,
    )