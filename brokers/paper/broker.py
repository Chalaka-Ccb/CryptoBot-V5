from core.enums.order import OrderStatus
from core.models.order import Order
from engine.execution_engine import Broker


class PaperBroker(Broker):

    def submit_order(self, order: Order) -> Order:
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity

        if order.price is not None:
            order.average_fill_price = order.price

        elif order.stop_price is not None:
            order.average_fill_price = order.stop_price

        else:
            raise ValueError(
                "Cannot determine paper fill price"
            )

        order.exchange_order_id = (
            f"PAPER-{order.order_id}"
        )

        return order

    def cancel_order(self, order_id: str) -> None:
        return None