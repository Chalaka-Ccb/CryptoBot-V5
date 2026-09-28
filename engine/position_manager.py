from datetime import datetime
from typing import Optional

from core.enums.position import (
    PositionSide,
    PositionStatus,
)
from core.enums.trade import ExitReason
from core.models.position import Position
from core.models.trade import Trade
from engine.state import EngineState


class PositionManager:

    def __init__(self, state: EngineState):
        self.state = state

    def open_position(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        strategy: Optional[str],
        timestamp: datetime,
    ) -> Position:

        if self.state.symbol_is_busy(symbol):
            raise ValueError(
                f"Symbol already has an active order or position: {symbol}"
            )

        position_id = f"POS-{len(self.state.positions) + 1:06d}"

        position = Position(
            position_id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            opened_at=timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            current_price=entry_price,
            highest_price=entry_price,
            lowest_price=entry_price,
        )

        trade_id = f"TRD-{len(self.state.trades) + 1:06d}"

        trade = Trade(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=timestamp,
            strategy=strategy,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.state.add_position(position)
        self.state.add_trade(trade)

        return position

    def update_price(
        self,
        symbol: str,
        price: float,
    ) -> None:

        position = self.state.positions.get(symbol)

        if position is None or not position.is_open:
            return

        position.current_price = price

        if position.highest_price is None:
            position.highest_price = price
        else:
            position.highest_price = max(
                position.highest_price,
                price,
            )

        if position.lowest_price is None:
            position.lowest_price = price
        else:
            position.lowest_price = min(
                position.lowest_price,
                price,
            )

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: ExitReason,
        timestamp: datetime,
        fees: float = 0.0,
    ) -> Position:

        position = self.state.positions.get(symbol)

        if position is None or not position.is_open:
            raise ValueError(
                f"No open position exists for {symbol}"
            )

        position.status = PositionStatus.CLOSED
        position.closed_at = timestamp
        position.exit_price = exit_price
        position.exit_reason = exit_reason

        for trade in reversed(self.state.trades):
            if (
                trade.symbol == symbol
                and trade.is_open
            ):
                trade.close(
                    exit_price=exit_price,
                    exit_time=timestamp,
                    exit_reason=exit_reason,
                    fees=fees,
                )
                break

        return position