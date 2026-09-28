from abc import ABC, abstractmethod
from datetime import datetime

from core.models.order import Order


class Broker(ABC):

    @abstractmethod
    def submit_order(self, order: Order) -> Order:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        pass


class ExecutionEngine:

    def __init__(self, broker: Broker):
        self.broker = broker

    def submit(self, order: Order) -> Order:
        return self.broker.submit_order(order)

    def cancel(self, order_id: str) -> None:
        self.broker.cancel_order(order_id)