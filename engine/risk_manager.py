from dataclasses import dataclass
from typing import Optional

from core.enums.position import PositionSide
from core.models.account import Account
from core.models.signal import TradingSignal

from risk.position_sizing import (
    PositionSizeResult,
    calculate_position_size,
)
from risk.risk_reward import (
    RiskRewardResult,
    calculate_take_profit,
)


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    position_size: Optional[PositionSizeResult]
    risk_reward: Optional[RiskRewardResult]
    reason: str = ""


class RiskManager:

    def __init__(
        self,
        account: Account,
        risk_percentage: float = 0.02,
        default_risk_reward: float = 3.0,
    ):
        self.account = account
        self.risk_percentage = risk_percentage
        self.default_risk_reward = default_risk_reward

    def evaluate(
        self,
        signal: TradingSignal,
        entry_price: float,
    ) -> RiskDecision:

        if entry_price <= 0:
            return RiskDecision(
                approved=False,
                position_size=None,
                risk_reward=None,
                reason="Entry price must be greater than 0",
            )

        if signal.stop_loss is None:
            return RiskDecision(
                approved=False,
                position_size=None,
                risk_reward=None,
                reason="Signal does not provide a stop-loss",
            )

        if signal.side.value == "long":
            side = PositionSide.LONG
        elif signal.side.value == "short":
            side = PositionSide.SHORT
        else:
            return RiskDecision(
                approved=False,
                position_size=None,
                risk_reward=None,
                reason="Unsupported signal side",
            )

        position_size = calculate_position_size(
            account_capital=self.account.balance,
            risk_percentage=self.risk_percentage,
            entry_price=entry_price,
            stop_loss_price=signal.stop_loss,
        )

        take_profit = signal.take_profit

        if take_profit is None:
            risk_reward = calculate_take_profit(
                entry_price=entry_price,
                stop_loss=signal.stop_loss,
                side=signal.side,
                risk_reward_ratio=self.default_risk_reward,
            )
        else:
            risk_reward = RiskRewardResult(
                entry_price=entry_price,
                stop_loss=signal.stop_loss,
                risk_distance=abs(
                    entry_price - signal.stop_loss
                ),
                risk_reward_ratio=(
                    abs(take_profit - entry_price)
                    / abs(entry_price - signal.stop_loss)
                ),
                take_profit=take_profit,
            )

        return RiskDecision(
            approved=True,
            position_size=position_size,
            risk_reward=risk_reward,
            reason="Risk checks passed",
        )