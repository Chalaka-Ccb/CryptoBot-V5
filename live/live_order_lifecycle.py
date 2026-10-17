"""Phase 6B: fail-closed local order lifecycle, offline only.

NO EXCHANGE CALLS OR ORDER SUBMISSION. An adapter may later feed normalized
exchange events after explicit reconciliation and protected order integration.
"""
from dataclasses import dataclass
from enum import Enum
from math import isfinite


class OrderState(str, Enum):
    READY = 'ready'
    PENDING = 'pending'
    PARTIAL = 'partial'
    FILLED_UNPROTECTED = 'filled_unprotected'
    PROTECTED = 'protected'
    CANCELLED = 'cancelled'
    HALTED = 'halted'


@dataclass(frozen=True)
class OrderIntent:
    client_id: str
    symbol: str
    side: str
    contracts: float
    entry: float
    stop_loss: float
    take_profit: float

    def __post_init__(self):
        if not self.client_id or len(self.client_id) > 64 or not self.client_id.isascii():
            raise ValueError('Invalid client ID')
        if self.symbol != 'SOL/USDT:USDT' or self.side not in ('long', 'short'):
            raise ValueError('Unsupported symbol or side')
        for value in (self.contracts, self.entry, self.stop_loss, self.take_profit):
            if not isinstance(value, (float, int)) or not isfinite(value) or value <= 0:
                raise ValueError('All amounts and prices must be finite and positive')
        if self.side == 'long' and not self.stop_loss < self.entry < self.take_profit:
            raise ValueError('Invalid LONG protective levels')
        if self.side == 'short' and not self.take_profit < self.entry < self.stop_loss:
            raise ValueError('Invalid SHORT protective levels')


class OfflineOrderLifecycle:
    """Models order acknowledgments, cumulative fills, protection and halts.

    Does not trust an order acknowledgment as evidence of a fill. Protection
    must cover all cumulative filled contracts before state becomes PROTECTED.
    Any discrepancy halts further actions pending manual reconciliation.
    """
    def __init__(self):
        self.state = OrderState.READY
        self.intent = None
        self.order_id = None
        self.filled = 0.0
        self.protected = 0.0
        self.used_client_ids = set()
        self.halt_reason = None

    def plan(self, intent: OrderIntent):
        if self.state != OrderState.READY:
            raise RuntimeError('Cannot plan while an order is active or halted')
        if intent.client_id in self.used_client_ids:
            raise RuntimeError('Client order ID already used')
        self.used_client_ids.add(intent.client_id)
        self.intent = intent
        self.state = OrderState.PENDING

    def acknowledge(self, client_id: str, order_id: str):
        self._require_active(client_id)
        if not order_id:
            self.halt('Missing exchange order ID')
            raise RuntimeError(self.halt_reason)
        if self.order_id is not None and self.order_id != order_id:
            self.halt('Conflicting exchange order IDs')
            raise RuntimeError(self.halt_reason)
        self.order_id = order_id

    def report_fill(self, client_id: str, cumulative_contracts: float):
        self._require_active(client_id)
        if not isinstance(cumulative_contracts, (int, float)) or not isfinite(cumulative_contracts):
            self.halt('Invalid fill amount')
            raise RuntimeError(self.halt_reason)
        if cumulative_contracts < self.filled or cumulative_contracts > self.intent.contracts + 1e-9:
            self.halt('Nonmonotonic or excessive cumulative fill')
            raise RuntimeError(self.halt_reason)
        self.filled = cumulative_contracts
        if self.filled > self.protected + 1e-9:
            self.state = OrderState.PARTIAL if self.filled < self.intent.contracts - 1e-9 else OrderState.FILLED_UNPROTECTED
        elif self.filled > 0:
            self.state = OrderState.PROTECTED

    def report_protection(self, client_id: str, covered_contracts: float, *, stop_confirmed: bool, target_confirmed: bool):
        self._require_active(client_id)
        if not (stop_confirmed and target_confirmed):
            self.halt('Stop and target must both be confirmed')
            raise RuntimeError(self.halt_reason)
        if not isinstance(covered_contracts, (int, float)) or not isfinite(covered_contracts) or covered_contracts < 0:
            self.halt('Invalid protected quantity')
            raise RuntimeError(self.halt_reason)
        if self.filled <= 0 or covered_contracts + 1e-9 < self.filled:
            self.halt('Protection does not cover full filled quantity')
            raise RuntimeError(self.halt_reason)
        if covered_contracts > self.intent.contracts + 1e-9:
            self.halt('Protection exceeds planned order quantity')
            raise RuntimeError(self.halt_reason)
        self.protected = covered_contracts
        self.state = OrderState.PROTECTED

    def cancel_unfilled(self, client_id: str, *, exchange_confirmed: bool):
        self._require_active(client_id)
        if not exchange_confirmed or self.filled > 0:
            self.halt('Cannot assume cancellation or abandon filled position')
            raise RuntimeError(self.halt_reason)
        self.state = OrderState.CANCELLED

    def halt(self, reason: str):
        self.halt_reason = reason
        self.state = OrderState.HALTED

    def _require_active(self, client_id: str):
        if self.intent is None or self.intent.client_id != client_id:
            raise RuntimeError('Unknown client ID')
        if self.state not in (OrderState.PENDING, OrderState.PARTIAL, OrderState.FILLED_UNPROTECTED, OrderState.PROTECTED):
            raise RuntimeError('Lifecycle is not active')
