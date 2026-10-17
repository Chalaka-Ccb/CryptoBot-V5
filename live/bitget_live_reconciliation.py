"""Phase 7A: authenticated read-only reconciliation of ordinary order IDs.

Trigger/plan order fills are NOT proven by ordinary fetch_order. Never use
this report alone to unlock trading or clear a journal.
"""
from dataclasses import dataclass
from decimal import Decimal
from live.bitget_order_adapter import BitgetOrderAdapter
from live.bitget_plan_inspector import BitgetPlanInspector


@dataclass(frozen=True)
class LiveReconciliationReport:
    client_id: str
    journal_status: str
    exchange_order_id: str | None
    order_status: str | None
    order_filled: str | None
    open_positions: int
    ordinary_open_orders: int
    pending_plan_orders: int
    requires_manual_review: bool = True
    live_execution_authorized: bool = False


class BitgetLiveReconciler:
    def __init__(self, gateway, journal, orders=None, plans=None):
        self.gateway = gateway
        self.journal = journal
        self.orders = orders or BitgetOrderAdapter(gateway)
        self.plans = plans or BitgetPlanInspector(gateway)

    def inspect(self, client_id):
        record = self.journal.get(client_id)
        intent = record['intent']
        if intent.symbol != 'SOL/USDT:USDT' or intent.client_id != client_id:
            raise RuntimeError('Journal identity mismatch')
        market = self.gateway.connect()
        if market.get('id') != 'SOLUSDT' or market.get('swap') is not True or market.get('linear') is not True:
            raise RuntimeError('Unexpected market')
        order_id = record['exchange_order_id']
        order = None
        if order_id is not None:
            order = self.orders.fetch_order(order_id)
            if order.client_id != client_id:
                raise RuntimeError('Order client ID mismatch; manual reconciliation required')
        open_orders = self.orders.fetch_open_orders()
        positions = self.gateway.fetch_positions()
        plans = self.plans.fetch_all()
        if not isinstance(positions,list) or not isinstance(plans,list):
            raise RuntimeError('Unreliable exchange snapshot')
        active = 0
        for p in positions:
            if not isinstance(p,dict) or p.get('symbol') != intent.symbol:
                raise RuntimeError('Unexpected position')
            n = Decimal(str(p.get('contracts')))
            if not n.is_finite() or n < 0:
                raise RuntimeError('Unreliable position size')
            if n > 0: active += 1
        return LiveReconciliationReport(
            client_id,record['status'],order_id,
            order.status if order else None,
            str(order.filled) if order else None,
            active,len(open_orders),len(plans))
