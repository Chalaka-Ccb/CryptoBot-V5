"""Phase 7B: fail-closed, read-only trigger-order identity reconciliation.

A pending plan is NOT a fill. A missing plan is NOT proof of cancellation
or execution. The inspector's PlanSnapshot does not expose clientOid,
so ownership requires a separately verified exchange order ID.
"""
from dataclasses import dataclass
from live.bitget_plan_inspector import PlanSnapshot


@dataclass(frozen=True)
class TriggerReconciliation:
    client_id: str
    plan_order_id: str
    status: str
    execution_confirmed: bool = False
    live_execution_authorized: bool = False


class BitgetTriggerReconciler:
    def __init__(self, journal, inspector):
        self.journal = journal
        self.inspector = inspector

    def pending(self, client_id, *, verified_plan_order_id):
        record = self.journal.get(client_id)
        intent = record['intent']
        if intent.client_id != client_id or intent.symbol != 'SOL/USDT:USDT':
            raise RuntimeError('Journal identity mismatch')
        if not isinstance(verified_plan_order_id,str) or not verified_plan_order_id:
            raise RuntimeError('Verified plan order ID required')
        plans = self.inspector.fetch_all()
        if not isinstance(plans,list):
            raise RuntimeError('Unreliable plan snapshot')
        matches = [p for p in plans if isinstance(p,PlanSnapshot) and p.order_id == verified_plan_order_id]
        if len(matches) != 1:
            raise RuntimeError('Plan absent/duplicate: history reconciliation required')
        plan = matches[0]
        if plan.plan_type != 'normal_plan' or plan.symbol.upper() != 'SOLUSDT':
            raise RuntimeError('Plan category/symbol mismatch')
        if plan.trigger_price is None or plan.trigger_price != __import__('decimal').Decimal(str(intent.entry)):
            raise RuntimeError('Trigger price mismatch')
        if plan.size is None or plan.size != __import__('decimal').Decimal(str(intent.contracts)):
            raise RuntimeError('Plan size mismatch')
        return TriggerReconciliation(client_id,verified_plan_order_id,plan.status)
