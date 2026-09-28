from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class BacktestTrade:
    symbol: str
    strategy: str
    side: str

    entry_time: datetime
    entry_price: float

    quantity: float

    stop_loss: Optional[float]
    take_profit: Optional[float]

    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    pnl: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    initial_balance: float
    final_balance: float

    trades: list[BacktestTrade]

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> int:
        return sum(
            1
            for trade in self.trades
            if trade.pnl > 0
        )

    @property
    def losing_trades(self) -> int:
        return sum(
            1
            for trade in self.trades
            if trade.pnl < 0
        )

    @property
    def total_pnl(self) -> float:
        return self.final_balance - self.initial_balance

    @property
    def return_percentage(self) -> float:
        if self.initial_balance <= 0:
            return 0.0

        return (
            self.total_pnl
            / self.initial_balance
        ) * 100.0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0

        return (
            self.winning_trades
            / self.total_trades
        ) * 100.0