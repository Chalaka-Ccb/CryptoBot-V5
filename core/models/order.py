from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.enums.order import OrderSide, OrderStatus, OrderType


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float

    created_at: datetime

    price: Optional[float] = None
    stop_price: Optional[float] = None

    status: OrderStatus = OrderStatus.PENDING

    filled_quantity: float = 0.0
    average_fill_price: Optional[float] = None

    exchange_order_id: Optional[str] = None

    strategy: Optional[str] = None
    reason: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in {
            OrderStatus.PENDING,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
        }

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def remaining_quantity(self) -> float:
        return max(self.quantity - self.filled_quantity, 0.0)