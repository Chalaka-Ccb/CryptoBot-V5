"""Order lifecycle; never treat an API acknowledgement as a confirmed fill."""
import time
import uuid
from dataclasses import replace


class OrderManager:
    def __init__(self, exchange, controls, recorder, cfg):
        self.exchange, self.controls, self.recorder, self.cfg = exchange, controls, recorder, cfg

    def open_trade(self, plan):
        if self.controls.entries_blocked():
            raise RuntimeError("Entries blocked by operator control")
        if self.exchange.get_position() is not None:
            raise RuntimeError("Position already open")
        if self.exchange.get_protection():
            raise RuntimeError("Unresolved trigger orders exist; refusing entry")
        plan = replace(plan, client_order_id="cbv1-" + uuid.uuid4().hex[:24])
        self.recorder.event("order_sent", client_order_id=plan.client_order_id,
                            side=plan.side, qty=plan.qty)
        try:
            self.exchange.place_entry(plan)
        except Exception as exc:
            self.recorder.event("order_error", level="ERROR",
                                error_type=type(exc).__name__, client_order_id=plan.client_order_id)
            # Do not resubmit a potentially filled order.
        position = None
        for _ in range(5):
            position = self.exchange.get_position()
            if position is not None:
                break
            time.sleep(2)
        if position is None:
            self.recorder.event("entry_skipped", reason="no_position_confirmed")
            return None
        self.recorder.event("order_filled", qty=position.qty, entry=position.entry)
        if not self.verify_protection(plan, position):
            if not self.repair_protection(plan, position):
                self.kill_switch("Entry protection missing or incorrect")
                return None
        return position

    def verify_protection(self, plan, position):
        orders = self.exchange.get_protection()
        def matches(order, kind, target):
            info = order.get("info") or {}
            params = order.get("stopLoss") if kind == "sl" else order.get("takeProfit")
            prices = [order.get("triggerPrice"), (params or {}).get("triggerPrice"),
                      info.get("triggerPrice"), info.get("triggerPx")]
            return (any(p is not None and abs(float(p) - target) <= max(target * 1e-8, 1e-8)
                        for p in prices)
                    and (order.get("side") in (None, "sell" if position.side == "long" else "buy"))
                    and (order.get("amount") is None or float(order["amount"]) >= position.qty))
        # This endpoint can expose different Bitget order shapes. Unknown shapes fail closed.
        sl = any(matches(o, "sl", plan.sl) for o in orders
                 if "loss" in str(o.get("type", "")).lower() or
                 "loss" in str((o.get("info") or {}).get("planType", "")).lower() or o.get("stopLoss"))
        tp = any(matches(o, "tp", plan.tp) for o in orders
                 if "profit" in str(o.get("type", "")).lower() or
                 "profit" in str((o.get("info") or {}).get("planType", "")).lower() or o.get("takeProfit"))
        self.recorder.event("protection_check", sl_ok=sl, tp_ok=tp)
        return sl and tp

    def repair_protection(self, plan, position):
        # Avoid duplicate contingent orders when the API cannot distinguish them.
        # Until Bitget plan-order mapping is verified on demo, fail safely rather
        # than blindly adding potentially overlapping protection orders.
        self.recorder.event("protection_failed", level="ERROR",
                            reason="Protection unverified; automatic repair not yet validated")
        return False

    def kill_switch(self, reason):
        self.controls.lock(reason)
        self.recorder.event("kill_switch", level="ERROR", reason=reason)
        self.ensure_flat()

    def ensure_flat(self):
        # A failed flatten keeps LOCKED; operator intervention may be required.
        self.controls.lock("Flatten requested")
        for attempt in range(10):
            try:
                position = self.exchange.get_position()
                if position is None:
                    self.exchange.cancel_all()
                    self.recorder.event("position_closed", reason="flatten")
                    return True
                self.exchange.cancel_all()
                self.exchange.close_position(position)
            except Exception as exc:
                self.recorder.event("error", level="ERROR", action="flatten",
                                    error_type=type(exc).__name__)
            time.sleep(3)
        self.recorder.event("error", level="ERROR", action="flatten",
                            reason="Manual Bitget intervention required")
        return False
