"""Phase 6E: fail-closed pre-submission guard. No write API methods.

This is NOT an order executor. It checks that the read-only order and plan
inspectors both see an empty account before preparing a future submission.
"""
from dataclasses import dataclass
from live.bitget_order_adapter import BitgetOrderAdapter
from live.bitget_plan_inspector import BitgetPlanInspector
from live.live_order_lifecycle import OrderIntent


@dataclass(frozen=True)
class GuardResult:
    intent: OrderIntent
    checked_ordinary_orders: bool
    checked_positions: bool
    checked_plan_orders: bool


class BitgetLiveGuard:
    def __init__(self, gateway, order_adapter=None, plan_inspector=None):
        self.gateway = gateway
        self.orders = order_adapter or BitgetOrderAdapter(gateway)
        self.plans = plan_inspector or BitgetPlanInspector(gateway)

    def verify_flat(self):
        """Fail closed if ANY ordinary order, position, or plan exists."""
        self.orders.assert_flat_for_new_entry()
        self.plans.assert_no_pending_plans()
        return True

    def prepare_intent(self, intent: OrderIntent) -> GuardResult:
        if not isinstance(intent, OrderIntent):
            raise TypeError('Expected OrderIntent')
        self.orders.validate_intent(intent)
        self.verify_flat()
        return GuardResult(intent, True, True, True)

    def submit_order(self, *args, **kwargs):
        raise RuntimeError('LIVE ORDER SUBMISSION DISABLED: exchange-side protection and durable reconciliation not implemented')
