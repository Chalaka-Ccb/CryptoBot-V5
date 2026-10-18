"""Conservative exchange execution: unresolved orders trigger a lock."""
import time
import uuid
from dataclasses import replace


class OrderManager:
    def __init__(self, exchange, controls, recorder, cfg):
        self.exchange, self.controls, self.recorder, self.cfg = exchange, controls, recorder, cfg

    def _match(self, orders, price, kind, position):
        """Accept only explicit SL/TP identification and matching quantity."""
        for order in orders:
            info = order.get("info") or {}
            plan_type = str(info.get("planType") or info.get("plan_type") or "").lower()
            detail = order.get("stopLoss") if kind == "sl" else order.get("takeProfit")
            is_kind = (bool(detail) or ("loss" in plan_type if kind == "sl" else "profit" in plan_type))
            if not is_kind:
                continue
            values = [order.get("triggerPrice"), info.get("triggerPrice"),
                      info.get("triggerPx"), (detail or {}).get("triggerPrice")]
            if not any(v is not None and abs(float(v) - float(price)) <= max(float(price) * 1e-7, 1e-8)
                       for v in values):
                continue
            side = order.get("side")
            expected = "sell" if position.side == "long" else "buy"
            if side is not None and side != expected:
                continue
            amount = order.get("amount")
            if amount is not None and float(amount) + 1e-9 < position.qty:
                continue
            return True
        return False

    def verify_saved_protection(self, saved, position):
        orders = self.exchange.get_protection()
        sl = self._match(orders, saved["sl"], "sl", position)
        tp = self._match(orders, saved["tp"], "tp", position)
        self.recorder.event("protection_check", sl_ok=sl, tp_ok=tp)
        return sl and tp

    def verify_protection(self, plan, position):
        return self.verify_saved_protection({"sl": plan.sl, "tp": plan.tp}, position)

    def repair_protection(self, plan, position):
        """No blind repair: account/endpoint semantics must be validated first."""
        self.recorder.event("protection_repair_blocked", level="ERROR",
                            reason="Bitget conditional-order mapping not demo-verified")
        return False

    def open_trade(self, plan):
        if self.controls.entries_blocked():
            raise RuntimeError("Entries blocked")
        if self.exchange.get_position() is not None or self.exchange.get_protection():
            raise RuntimeError("Position or contingent orders already present")
        plan = replace(plan, client_order_id="cbv1-" + uuid.uuid4().hex[:24])
        self.recorder.event("entry_submit", side=plan.side, qty=plan.qty,
                            client_order_id=plan.client_order_id)
        try:
            self.exchange.place_entry(plan)
        except Exception as error:
            # Unknown outcome: NEVER retry, even if the position isn't visible yet.
            self.controls.lock("Ambiguous entry result: manual reconciliation required")
            self.recorder.event("entry_ambiguous", level="ERROR", error_type=type(error).__name__)
            raise
        for _ in range(5):
            position = self.exchange.get_position()
            if position is not None:
                self.recorder.event("entry_filled", qty=position.qty, price=position.entry)
                if not self.verify_protection(plan, position):
                    if not self.repair_protection(plan, position):
                        self.kill_switch("SL/TP not confirmed after entry")
                        return None
                return position
            time.sleep(2)
        self.controls.lock("Entry acknowledgement without confirmed position")
        self.recorder.event("entry_unresolved", level="ERROR")
        return None

    def kill_switch(self, reason):
        self.controls.lock(reason)
        self.recorder.event("kill_switch", level="ERROR", reason=reason)
        self.ensure_flat()

    def ensure_flat(self):
        self.controls.lock("Flatten requested")
        for _ in range(5):
            try:
                position = self.exchange.get_position()
                self.exchange.cancel_all()
                if position is None:
                    self.recorder.event("flat_confirmed")
                    return True
                self.exchange.close_position(position)
            except Exception as error:
                self.recorder.event("flatten_error", level="ERROR", error_type=type(error).__name__)
            time.sleep(3)
        self.recorder.event("flatten_unresolved", level="ERROR")
        return False
