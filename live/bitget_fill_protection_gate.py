"""Phase 6U: read-only fill/position/protection reconciliation gate.

Does not place protection orders or declare an unfilled trigger protected.
A PASS is a snapshot, not continuous protection or authorization to trade.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from live.live_order_lifecycle import OrderIntent


def quantity(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RuntimeError('Unreliable quantity') from None
    if not d.is_finite() or d < 0:
        raise RuntimeError('Unreliable quantity')
    return d


@dataclass(frozen=True)
class FillProtectionReport:
    filled_contracts: str
    position_contracts: str
    stop_order_id: str
    target_order_id: str
    read_only: bool = True
    live_execution_authorized: bool = False


class BitgetFillProtectionGate:
    def __init__(self, gateway, verifier):
        self.gateway = gateway
        self.verifier = verifier

    def check(self, intent: OrderIntent, cumulative_filled):
        if not isinstance(intent, OrderIntent) or intent.symbol != 'SOL/USDT:USDT':
            raise RuntimeError('Invalid intent')
        filled = quantity(cumulative_filled)
        if filled <= 0 or filled > quantity(intent.contracts):
            raise RuntimeError('No verified fill or overfill')
        positions = self.gateway.fetch_positions()
        if not isinstance(positions, list) or len(positions) != 1:
            raise RuntimeError('Expected exactly one scoped position')
        p = positions[0]
        if not isinstance(p, dict) or p.get('symbol') != intent.symbol:
            raise RuntimeError('Position symbol mismatch')
        if p.get('side') != intent.side:
            raise RuntimeError('Position side mismatch')
        held = quantity(p.get('contracts'))
        if held != filled:
            raise RuntimeError('Position size differs from cumulative fill')
        protection = self.verifier.verify(intent, float(filled))
        if not isinstance(protection, dict) or quantity(protection.get('covered_contracts')) != filled:
            raise RuntimeError('Unreliable protection coverage')
        sl = protection.get('stop_order_id')
        tp = protection.get('target_order_id')
        if not isinstance(sl, str) or not sl or not isinstance(tp, str) or not tp or sl == tp:
            raise RuntimeError('Unreliable protective order IDs')
        return FillProtectionReport(str(filled), str(held), sl, tp)
