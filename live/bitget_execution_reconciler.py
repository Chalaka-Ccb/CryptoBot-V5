"""Phase 7C.3: read-only end-to-end reconciliation. Never clears the journal.

The exchange must explicitly link a trigger to its child order. Missing
fills/history do not prove a position is flat. An unprotected fill is
an emergency requiring separate vetted exchange action.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def qty(value):
    try: n=Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise RuntimeError('Invalid quantity') from None
    if not n.is_finite() or n < 0: raise RuntimeError('Invalid quantity')
    return n


@dataclass(frozen=True)
class ExecutionReconciliation:
    client_id: str
    plan_order_id: str
    child_order_id: str | None
    filled_amount: str | None
    position_amount: str
    status: str
    emergency_attention: bool
    read_only: bool = True
    live_execution_authorized: bool = False


class BitgetExecutionReconciler:
    def __init__(self, journal, trigger_history, fill_history, gateway, protection_gate):
        self.journal=journal
        self.trigger_history=trigger_history
        self.fill_history=fill_history
        self.gateway=gateway
        self.protection_gate=protection_gate

    def inspect(self, client_id, *, plan_order_id, since_ms, until_ms):
        record=self.journal.get(client_id)
        intent=record['intent']
        if intent.client_id != client_id or intent.symbol != 'SOL/USDT:USDT':
            raise RuntimeError('Journal identity mismatch')
        if not isinstance(plan_order_id,str) or not plan_order_id:
            raise ValueError('Verified plan ID required')
        history=self.trigger_history.find_verified(
            plan_order_id=plan_order_id,client_id=client_id)
        if history.plan_order_id != plan_order_id or history.client_id != client_id:
            raise RuntimeError('Unreliable trigger history identity')
        child=history.child_order_id
        positions=self.gateway.fetch_positions()
        if not isinstance(positions,list):
            raise RuntimeError('Invalid position response')
        held=Decimal(0)
        for p in positions:
            if not isinstance(p,dict) or p.get('symbol')!='SOL/USDT:USDT':
                raise RuntimeError('Unexpected position record')
            amount=qty(p.get('contracts'))
            if amount:
                if p.get('side')!=intent.side or held:
                    raise RuntimeError('Conflicting active positions')
                held=amount
        if child is None:
            # No inference from trigger status or missing history.
            return ExecutionReconciliation(client_id,plan_order_id,None,None,str(held),
                                           'UNKNOWN_CHILD_ORDER',bool(held))
        if not isinstance(child,str) or not child:
            raise RuntimeError('Invalid child order ID')
        side='buy' if intent.side=='long' else 'sell'
        fills=self.fill_history.inspect(child,side,since_ms=since_ms,until_ms=until_ms)
        if fills.order_id != child:
            raise RuntimeError('Fill order ID mismatch')
        executed=qty(fills.amount)
        if executed > qty(intent.contracts):
            raise RuntimeError('Overfill detected: emergency reconciliation required')
        if held != executed:
            return ExecutionReconciliation(client_id,plan_order_id,child,str(executed),str(held),
                                           'POSITION_FILL_MISMATCH',bool(held or executed))
        if not executed:
            return ExecutionReconciliation(client_id,plan_order_id,child,'0','0',
                                           'NO_CONFIRMED_FILL',False)
        try:
            protection=self.protection_gate.check(intent,executed)
            if qty(protection.filled_contracts)!=executed:
                raise RuntimeError('Coverage mismatch')
        except Exception:
            return ExecutionReconciliation(client_id,plan_order_id,child,str(executed),str(held),
                                           'FILLED_PROTECTION_UNVERIFIED',True)
        return ExecutionReconciliation(client_id,plan_order_id,child,str(executed),str(held),
                                       'PROTECTED_SNAPSHOT_UNVERIFIED_HISTORY',False)
