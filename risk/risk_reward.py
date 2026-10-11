# from dataclasses import dataclass
#
# from core.models.signal import SignalSide
#
#
# @dataclass(frozen=True)
# class RiskRewardResult:
#     entry_price: float
#     stop_loss: float
#     risk_distance: float
#     risk_reward_ratio: float
#     take_profit: float
#
#
# def calculate_take_profit(
#     entry_price: float,
#     stop_loss: float,
#     side: SignalSide,
#     risk_reward_ratio: float = 3.0,
# ) -> RiskRewardResult:
#
#     if entry_price <= 0:
#         raise ValueError(
#             "entry_price must be greater than 0"
#         )
#
#     if stop_loss <= 0:
#         raise ValueError(
#             "stop_loss must be greater than 0"
#         )
#
#     if risk_reward_ratio <= 0:
#         raise ValueError(
#             "risk_reward_ratio must be greater than 0"
#         )
#
#     risk_distance = abs(
#         entry_price - stop_loss
#     )
#
#     if risk_distance <= 0:
#         raise ValueError(
#             "entry price and stop-loss cannot be equal"
#         )
#
#     if side == SignalSide.LONG:
#         take_profit = (
#             entry_price
#             + risk_distance * risk_reward_ratio
#         )
#
#     elif side == SignalSide.SHORT:
#         take_profit = (
#             entry_price
#             - risk_distance * risk_reward_ratio
#         )
#
#     else:
#         raise ValueError(
#             f"Unsupported signal side: {side}"
#         )
#
#     return RiskRewardResult(
#         entry_price=entry_price,
#         stop_loss=stop_loss,
#         risk_distance=risk_distance,
#         risk_reward_ratio=risk_reward_ratio,
#         take_profit=take_profit,
#     )

from dataclasses import dataclass
from core.models.signal import SignalSide
from risk.validation import finite_number


@dataclass(frozen=True)
class RiskRewardResult:
    entry_price: float
    stop_loss: float
    risk_distance: float
    risk_reward_ratio: float
    take_profit: float


def validate_levels(entry_price, stop_loss, side, take_profit=None):
    entry = finite_number("entry_price", entry_price, positive=True)
    stop = finite_number("stop_loss", stop_loss, positive=True)
    if side == SignalSide.LONG:
        if stop >= entry:
            raise ValueError("LONG stop must be below entry")
    elif side == SignalSide.SHORT:
        if stop <= entry:
            raise ValueError("SHORT stop must be above entry")
    else:
        raise ValueError(f"Unsupported signal side: {side}")
    if take_profit is not None:
        target = finite_number("take_profit", take_profit, positive=True)
        if side == SignalSide.LONG and target <= entry:
            raise ValueError("LONG TP must be above entry")
        if side == SignalSide.SHORT and target >= entry:
            raise ValueError("SHORT TP must be below entry")


def calculate_take_profit(entry_price, stop_loss, side, risk_reward_ratio=3.0):
    validate_levels(entry_price, stop_loss, side)
    ratio = finite_number("risk_reward_ratio", risk_reward_ratio, positive=True)
    distance = abs(entry_price - stop_loss)
    target = entry_price + distance * ratio if side == SignalSide.LONG else entry_price - distance * ratio
    validate_levels(entry_price, stop_loss, side, target)
    return RiskRewardResult(entry_price, stop_loss, distance, ratio, target)
