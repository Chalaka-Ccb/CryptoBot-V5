# from dataclasses import dataclass
# from typing import Optional
#
# from core.enums.position import PositionSide
# from core.models.account import Account
# from core.models.signal import TradingSignal
#
# from risk.position_sizing import (
#     PositionSizeResult,
#     calculate_position_size,
# )
# from risk.risk_reward import (
#     RiskRewardResult,
#     calculate_take_profit,
# )
#
#
# @dataclass(frozen=True)
# class RiskDecision:
#     approved: bool
#     position_size: Optional[PositionSizeResult]
#     risk_reward: Optional[RiskRewardResult]
#     reason: str = ""
#
#
# class RiskManager:
#
#     def __init__(
#         self,
#         account: Account,
#         risk_percentage: float = 0.02,
#         default_risk_reward: float = 3.0,
#     ):
#         self.account = account
#         self.risk_percentage = risk_percentage
#         self.default_risk_reward = default_risk_reward
#
#     def evaluate(
#         self,
#         signal: TradingSignal,
#         entry_price: float,
#     ) -> RiskDecision:
#
#         if entry_price <= 0:
#             return RiskDecision(
#                 approved=False,
#                 position_size=None,
#                 risk_reward=None,
#                 reason="Entry price must be greater than 0",
#             )
#
#         if signal.stop_loss is None:
#             return RiskDecision(
#                 approved=False,
#                 position_size=None,
#                 risk_reward=None,
#                 reason="Signal does not provide a stop-loss",
#             )
#
#         if signal.side.value == "long":
#             side = PositionSide.LONG
#         elif signal.side.value == "short":
#             side = PositionSide.SHORT
#         else:
#             return RiskDecision(
#                 approved=False,
#                 position_size=None,
#                 risk_reward=None,
#                 reason="Unsupported signal side",
#             )
#
#         position_size = calculate_position_size(
#             account_capital=self.account.balance,
#             risk_percentage=self.risk_percentage,
#             entry_price=entry_price,
#             stop_loss_price=signal.stop_loss,
#         )
#
#         take_profit = signal.take_profit
#
#         if take_profit is None:
#             risk_reward = calculate_take_profit(
#                 entry_price=entry_price,
#                 stop_loss=signal.stop_loss,
#                 side=signal.side,
#                 risk_reward_ratio=self.default_risk_reward,
#             )
#         else:
#             risk_reward = RiskRewardResult(
#                 entry_price=entry_price,
#                 stop_loss=signal.stop_loss,
#                 risk_distance=abs(
#                     entry_price - signal.stop_loss
#                 ),
#                 risk_reward_ratio=(
#                     abs(take_profit - entry_price)
#                     / abs(entry_price - signal.stop_loss)
#                 ),
#                 take_profit=take_profit,
#             )
#
#         return RiskDecision(
#             approved=True,
#             position_size=position_size,
#             risk_reward=risk_reward,
#             reason="Risk checks passed",
#         )


from dataclasses import dataclass
from typing import Optional
from core.models.account import Account
from core.models.signal import TradingSignal
from risk.limits import RiskLimits, QuantityLimits
from risk.position_sizing import PositionSizeResult, calculate_position_size
from risk.risk_reward import RiskRewardResult, calculate_take_profit, validate_levels
from risk.validation import finite_number


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    position_size: Optional[PositionSizeResult]
    risk_reward: Optional[RiskRewardResult]
    reason: str = ""


class RiskManager:
    def __init__(self, account: Account, risk_percentage=0.02,
                 default_risk_reward=3.0, *, limits: RiskLimits | None = None,
                 quantity_limits: dict[str, QuantityLimits] | None = None):
        self.account = account
        self.risk_percentage = finite_number("risk_percentage", risk_percentage, positive=True)
        if self.risk_percentage > 1:
            raise ValueError("risk_percentage cannot exceed 1")
        self.default_risk_reward = finite_number("default_risk_reward", default_risk_reward, positive=True)
        self.limits = limits or RiskLimits()
        self.quantity_limits = dict(quantity_limits or {})

    def evaluate(self, signal: TradingSignal, entry_price: float, *,
                 symbol: str | None = None) -> RiskDecision:
        try:
            if signal.stop_loss is None:
                raise ValueError("Signal does not provide a stop-loss")
            validate_levels(entry_price, signal.stop_loss, signal.side, signal.take_profit)
            balance = finite_number("balance", self.account.balance)
            equity = finite_number("equity", self.account.equity, positive=True)
            used = finite_number("used_margin", self.account.used_margin)
            available = finite_number("available_balance", self.account.available_balance)
            if balance < 0 or used < 0 or available < 0:
                raise ValueError("Account balances and used margin cannot be negative")
            # Conservative check against both reported funds and derived funds.
            free_margin = min(available, balance - used, equity - used) - self.limits.margin_reserve
            if free_margin <= 0:
                raise ValueError("Insufficient available margin")
            if self.quantity_limits and symbol not in self.quantity_limits:
                raise ValueError("Missing quantity limits for symbol")
            if signal.take_profit is None:
                reward = calculate_take_profit(entry_price, signal.stop_loss, signal.side, self.default_risk_reward)
            else:
                distance = abs(entry_price - signal.stop_loss)
                reward = RiskRewardResult(entry_price, signal.stop_loss, distance,
                    abs(signal.take_profit - entry_price) / distance, signal.take_profit)
                finite_number("risk_reward_ratio", reward.risk_reward_ratio, positive=True)
            size = calculate_position_size(equity, self.risk_percentage, entry_price,
                signal.stop_loss, max_notional=self.limits.max_position_notional,
                available_margin=free_margin, leverage=self.limits.leverage,
                quantity_limits=self.quantity_limits.get(symbol))
            return RiskDecision(True, size, reward, "Risk checks passed")
        except (ValueError, ArithmeticError) as error:
            return RiskDecision(False, None, None, str(error))
