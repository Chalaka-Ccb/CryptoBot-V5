"""Phase 6C: read-only Bitget order reconciliation and guarded entry preparation.

Deliberately has NO order submission, cancellation, leverage or protection writes.
This module is safe to test with a read-only API key. It does NOT make live
trading safe: Bitget trigger orders and position protection need separate work.
"""
from dataclasses import dataclass
from math import isfinite

from live.live_order_lifecycle import OrderIntent


@dataclass(frozen=True)
class OrderSnapshot:
    order_id: str
    client_id: str | None
    symbol: str
    status: str
    amount: float
    filled: float
    remaining: float
    side: str
    reduce_only: bool | None


class BitgetOrderAdapter:
    def __init__(self, gateway):
        self.gateway = gateway
        self.symbol = gateway.config.symbol
        if self.symbol != 'SOL/USDT:USDT':
            raise ValueError('Unsupported symbol')

    def _ready(self):
        if self.gateway._market is None:
            self.gateway.connect()
        return self.gateway.exchange

    @staticmethod
    def _number(name, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise RuntimeError(f'Unreliable exchange {name}')
        return float(value)

    def normalize_order(self, raw):
        if not isinstance(raw, dict):
            raise RuntimeError('Malformed order response')
        order_id = raw.get('id')
        if not isinstance(order_id, str) or not order_id:
            raise RuntimeError('Missing exchange order ID')
        if raw.get('symbol') != self.symbol:
            raise RuntimeError('Unexpected order symbol')
        status = raw.get('status')
        if status not in ('open', 'closed', 'canceled', 'expired', 'rejected'):
            raise RuntimeError('Unknown order status')
        side = raw.get('side')
        if side not in ('buy', 'sell'):
            raise RuntimeError('Unknown order side')
        amount = self._number('amount', raw.get('amount'))
        filled = self._number('filled', raw.get('filled'))
        remaining = self._number('remaining', raw.get('remaining'))
        if filled > amount + 1e-8 or remaining > amount + 1e-8 or abs(amount - filled - remaining) > max(1e-8, amount * 1e-7):
            raise RuntimeError('Inconsistent order quantities')
        client_id = raw.get('clientOrderId')
        if client_id is not None and (not isinstance(client_id, str) or not client_id):
            raise RuntimeError('Invalid client order ID')
        reduce_only = raw.get('reduceOnly')
        if reduce_only is not None and not isinstance(reduce_only, bool):
            raise RuntimeError('Unreliable reduceOnly flag')
        return OrderSnapshot(order_id, client_id, self.symbol, status, amount, filled, remaining, side, reduce_only)

    def fetch_order(self, order_id: str):
        if not isinstance(order_id, str) or not order_id:
            raise ValueError('Order ID required')
        exchange = self._ready()
        if not exchange.has.get('fetchOrder'):
            raise RuntimeError('fetchOrder unavailable; manual reconciliation required')
        order = self.normalize_order(exchange.fetch_order(order_id, self.symbol))
        if order.order_id != order_id:
            raise RuntimeError('Exchange returned wrong order ID')
        return order

    def fetch_open_orders(self):
        exchange = self._ready()
        if not exchange.has.get('fetchOpenOrders'):
            raise RuntimeError('fetchOpenOrders unavailable')
        orders = exchange.fetch_open_orders(self.symbol)
        if not isinstance(orders, list):
            raise RuntimeError('Unreliable open orders response')
        result = [self.normalize_order(item) for item in orders]
        if any(item.status != 'open' for item in result):
            raise RuntimeError('Unexpected non-open order in open orders')
        return result

    def assert_flat_for_new_entry(self):
        """Checks ordinary orders/positions, but NOT Bitget plan/trigger orders.

        Consequently this method is not a sufficient live-entry gate.
        """
        if self.fetch_open_orders():
            raise RuntimeError('Existing ordinary open orders')
        positions = self.gateway.fetch_positions()
        if not isinstance(positions, list):
            raise RuntimeError('Unreliable positions response')
        for p in positions:
            if p.get('symbol') != self.symbol:
                continue
            contracts = self._number('position contracts', p.get('contracts'))
            if contracts > 0:
                raise RuntimeError('Existing position')
        return True

    def validate_intent(self, intent: OrderIntent):
        """Local validation only; does not place an order."""
        if not isinstance(intent, OrderIntent) or intent.symbol != self.symbol:
            raise ValueError('Invalid intent')
        self._ready()
        return intent

    def submit_order(self, *args, **kwargs):
        raise RuntimeError('LIVE ORDER SUBMISSION DISABLED: protection and reconciliation not implemented')
