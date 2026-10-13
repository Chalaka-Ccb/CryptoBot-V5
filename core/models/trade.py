from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.enums.position import PositionSide
from core.enums.trade import ExitReason, TradeStatus


@dataclass
class Trade:
    trade_id: str
    symbol: str
    side: PositionSide

    quantity: float
    entry_price: float
    entry_time: datetime

    strategy: Optional[str] = None

    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    status: TradeStatus = TradeStatus.OPEN
    exit_reason: Optional[ExitReason] = None

    fees: float = 0.0
    entry_fee: float = 0.0
    exit_fee: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    @property
    def is_closed(self) -> bool:
        return self.status == TradeStatus.CLOSED

    @property
    def gross_pnl(self) -> Optional[float]:
        if self.exit_price is None:
            return None

        if self.side == PositionSide.LONG:
            return (
                self.exit_price - self.entry_price
            ) * self.quantity

        return (
            self.entry_price - self.exit_price
        ) * self.quantity

    @property
    def net_pnl(self) -> Optional[float]:
        gross_pnl = self.gross_pnl

        if gross_pnl is None:
            return None

        return gross_pnl - self.fees

    def close(
        self,
        exit_price: float,
        exit_time: datetime,
        exit_reason: ExitReason,
        fees: float = 0.0,
    ) -> None:
        if exit_price <= 0:
            raise ValueError("exit_price must be greater than 0")

        if self.is_closed:
            raise ValueError("trade is already closed")

        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = exit_reason
        if fees < 0:
            raise ValueError("fees cannot be negative")

        self.exit_fee = fees
        self.fees += fees
        self.status = TradeStatus.CLOSED