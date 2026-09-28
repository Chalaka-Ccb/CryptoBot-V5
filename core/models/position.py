from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.enums.position import PositionSide, PositionStatus


@dataclass
class Position:
    position_id: str
    symbol: str
    side: PositionSide

    quantity: float
    entry_price: float
    opened_at: datetime

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    status: PositionStatus = PositionStatus.OPEN

    current_price: Optional[float] = None

    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None

    strategy: Optional[str] = None

    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None

    exit_reason: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN

    @property
    def is_closed(self) -> bool:
        return self.status == PositionStatus.CLOSED

    @property
    def unrealized_pnl(self) -> float:
        if self.current_price is None:
            return 0.0

        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity

        return (self.entry_price - self.current_price) * self.quantity

    @property
    def realized_pnl(self) -> Optional[float]:
        if self.exit_price is None:
            return None

        if self.side == PositionSide.LONG:
            return (self.exit_price - self.entry_price) * self.quantity

        return (self.entry_price - self.exit_price) * self.quantity