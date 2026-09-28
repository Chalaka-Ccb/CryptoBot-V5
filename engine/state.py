from dataclasses import dataclass, field

from core.models.account import Account
from core.models.order import Order
from core.models.position import Position
from core.models.trade import Trade


@dataclass
class EngineState:
    account: Account

    active_orders: dict[str, Order] = field(default_factory=dict)

    positions: dict[str, Position] = field(default_factory=dict)

    trades: list[Trade] = field(default_factory=list)

    def has_active_order(self, symbol: str) -> bool:
        return any(
            order.symbol == symbol and order.is_active
            for order in self.active_orders.values()
        )

    def has_open_position(self, symbol: str) -> bool:
        position = self.positions.get(symbol)

        return position is not None and position.is_open

    def symbol_is_busy(self, symbol: str) -> bool:
        return (
            self.has_active_order(symbol)
            or self.has_open_position(symbol)
        )

    def add_order(self, order: Order) -> None:
        self.active_orders[order.order_id] = order

    def add_position(self, position: Position) -> None:
        self.positions[position.symbol] = position

    def add_trade(self, trade: Trade) -> None:
        self.trades.append(trade)

    def remove_position(self, symbol: str) -> None:
        self.positions.pop(symbol, None)