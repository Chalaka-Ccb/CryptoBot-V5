from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backtesting.broker import BacktestBroker
from core.enums.position import PositionSide
from core.models.signal import TradingSignal
from engine.risk_manager import RiskManager


@dataclass
class PendingEntry:
    signal: TradingSignal
    symbol: str
    timeframe: str


class BacktestExecution:
    def __init__(
        self,
        broker: BacktestBroker,
        risk_manager: RiskManager,
    ):
        self.broker = broker
        self.risk_manager = risk_manager

    def can_enter(self, symbol: str) -> bool:
        return not self.broker.has_open_trade()

    def sync_account(self) -> None:
        self.risk_manager.account.balance = self.broker.balance
        self.risk_manager.account.available_balance = self.broker.balance

    def create_pending_entry(
        self,
        signal: TradingSignal,
        symbol: str,
        timeframe: str,
    ) -> PendingEntry:
        return PendingEntry(
            signal=signal,
            symbol=symbol,
            timeframe=timeframe,
        )

    def execute_next_open(
        self,
        pending: PendingEntry,
        candle,
    ):
        self.sync_account()
        signal = pending.signal

        entry_price = candle.open

        decision = self.risk_manager.evaluate(
            signal=signal,
            entry_price=entry_price,
        )

        if not decision.approved:
            print()
            print("===== TRADE REJECTED =====")
            print(f"Strategy: {signal.strategy}")
            print(f"Reason: {decision.reason}")
            return None

        position_size = decision.position_size.position_size
        risk_reward = decision.risk_reward

        if signal.side.value == "long":
            side = PositionSide.LONG
        else:
            side = PositionSide.SHORT

        take_profit = risk_reward.take_profit

        trade = self.broker.open_trade(
            symbol=pending.symbol,
            side=side,
            quantity=position_size,
            entry_price=entry_price,
            stop_loss=signal.stop_loss,
            take_profit=take_profit,
            strategy=signal.strategy,
            timestamp=candle.timestamp,
        )

        return trade