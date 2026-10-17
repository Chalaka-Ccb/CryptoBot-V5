"""Phase 6J: fail-closed exchange-side SL/TP verification. READ ONLY.

Accepts only explicit, known Bitget profit_loss subtypes. This deliberately
rejects ambiguous plan responses instead of guessing protection is installed.
"""
from decimal import Decimal, InvalidOperation

from live.bitget_plan_inspector import PlanSnapshot


def decimal_positive(value, label):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise RuntimeError(f"Invalid {label}") from None
    if not n.is_finite() or n <= 0:
        raise RuntimeError(f"Invalid {label}")
    return n


class BitgetProtectionVerifier:
    """Verify pending protective plans against a filled OrderIntent.

    This does not prove reduce-only semantics, position ownership, or
    OCO behavior. Those require additional exchange-specific verification.
    """
    def __init__(self, inspector, *, tick_tolerance=Decimal("0")):
        self.inspector = inspector
        self.tick_tolerance = Decimal(str(tick_tolerance))
        if not self.tick_tolerance.is_finite() or self.tick_tolerance < 0:
            raise ValueError("Invalid tick tolerance")

    def verify(self, intent, filled_contracts):
        filled = decimal_positive(filled_contracts, "filled contracts")
        if filled > decimal_positive(intent.contracts, "planned contracts"):
            raise RuntimeError("Fill exceeds intent")
        plans = self.inspector.fetch_all()
        if not isinstance(plans, list):
            raise RuntimeError("Unreliable pending plans response")
        if len(plans) != 2:
            raise RuntimeError("Expected exactly two protective plans")
        expected = {
            "loss_plan": Decimal(str(intent.stop_loss)),
            "profit_plan": Decimal(str(intent.take_profit)),
        }
        seen = {}
        for p in plans:
            if not isinstance(p, PlanSnapshot):
                raise RuntimeError("Unrecognized plan record")
            if p.symbol.upper() != "SOLUSDT" or p.plan_type != "profit_loss":
                raise RuntimeError("Unexpected pending plan")
            if p.subtype not in expected or p.subtype in seen:
                raise RuntimeError("Missing, duplicate or ambiguous SL/TP subtype")
            if not isinstance(p.order_id, str) or not p.order_id:
                raise RuntimeError("Invalid protection order ID")
            if p.trigger_price is None or abs(p.trigger_price - expected[p.subtype]) > self.tick_tolerance:
                raise RuntimeError("Protection trigger price mismatch")
            if p.size is None or p.size < filled:
                raise RuntimeError("Protection quantity does not cover fill")
            if p.size > decimal_positive(intent.contracts, "planned contracts"):
                raise RuntimeError("Protection quantity exceeds intent")
            seen[p.subtype] = p.order_id
        if set(seen) != set(expected):
            raise RuntimeError("Both SL and TP required")
        if len(set(seen.values())) != 2:
            raise RuntimeError("SL and TP cannot share order ID")
        return {"stop_order_id": seen["loss_plan"],
                "target_order_id": seen["profit_plan"],
                "covered_contracts": str(filled)}
