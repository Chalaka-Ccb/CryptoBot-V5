"""Phase 6W: read-only restart reconciliation, never unlocks entries.

No exchange writes. Any unresolved journal record requires manual
reconciliation even when the exchange looks flat.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def size(value):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RuntimeError('Unreliable position size') from None
    if not n.is_finite() or n < 0:
        raise RuntimeError('Unreliable position size')
    return n


@dataclass(frozen=True)
class RestartRecoveryReport:
    unresolved_intents: tuple[str, ...]
    open_positions: int
    ordinary_open_orders: int
    pending_plan_orders: int
    manual_reconciliation_required: bool
    live_execution_authorized: bool = False


class BitgetRestartRecovery:
    def __init__(self, journal, gateway, inspector):
        self.journal = journal
        self.gateway = gateway
        self.inspector = inspector

    def check(self):
        unresolved = self.journal.unresolved()
        if not isinstance(unresolved, list) or not all(isinstance(x,str) and x for x in unresolved):
            raise RuntimeError('Unreliable journal')
        market = self.gateway.connect()
        if market.get('id') != 'SOLUSDT' or market.get('swap') is not True or market.get('linear') is not True:
            raise RuntimeError('Unsupported market')
        positions = self.gateway.fetch_positions()
        if not isinstance(positions, list):
            raise RuntimeError('Unreliable positions')
        active = 0
        for p in positions:
            if not isinstance(p, dict) or p.get('symbol') != 'SOL/USDT:USDT':
                raise RuntimeError('Unexpected position')
            if size(p.get('contracts')) > 0:
                active += 1
        exchange = self.gateway.exchange
        if not exchange.has.get('fetchOpenOrders'):
            raise RuntimeError('Open-order query unavailable')
        orders = exchange.fetch_open_orders('SOL/USDT:USDT')
        plans = self.inspector.fetch_all()
        if not isinstance(orders,list) or not isinstance(plans,list):
            raise RuntimeError('Unreliable order snapshot')
        return RestartRecoveryReport(tuple(unresolved),active,len(orders),len(plans),
                                     bool(unresolved or active or orders or plans))
