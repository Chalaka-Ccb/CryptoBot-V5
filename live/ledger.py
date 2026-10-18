"""Reconcile closed trades from actual Bitget fills, including fees.

An incomplete or ambiguous fill history must never be reported as realized PnL.
"""
from decimal import Decimal
from datetime import datetime, timezone


def closed_trade_record(saved, fills):
    if not saved or saved.get("adopted"):
        return None
    qty = Decimal(str(saved["qty"]))
    if qty <= 0:
        return None
    entry_side = "buy" if saved["side"] == "long" else "sell"
    exit_side = "sell" if entry_side == "buy" else "buy"
    since = saved.get("entry_ts")
    if since is None:
        return None
    selected = [f for f in fills if f.get("timestamp") is not None
                and f["timestamp"] >= since - 60000]
    entry = [f for f in selected if f.get("side") == entry_side]
    exit_ = [f for f in selected if f.get("side") == exit_side]

    def total(rows):
        amount = sum((Decimal(str(f["amount"])) for f in rows), Decimal(0))
        value = sum((Decimal(str(f["amount"])) * Decimal(str(f["price"])) for f in rows), Decimal(0))
        return amount, value

    entry_qty, entry_value = total(entry)
    exit_qty, exit_value = total(exit_)
    tolerance = Decimal("0.00000001")
    if abs(entry_qty - qty) > tolerance or abs(exit_qty - qty) > tolerance:
        return None
    fees = Decimal(0)
    for fill in entry + exit_:
        fee = fill.get("fee")
        if not fee or fee.get("cost") is None or fee.get("currency") != "USDT":
            return None
        fees += Decimal(str(fee["cost"]))
    gross = exit_value - entry_value if saved["side"] == "long" else entry_value - exit_value
    timestamp = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()
    return {
        "trade_id": saved.get("client_order_id", ""),
        "symbol": saved.get("symbol", "SONIC/USDT:USDT"),
        "strategy": "bollinger_channel_rebound",
        "timeframe": saved.get("timeframe", ""),
        "side": saved["side"],
        "qty": float(qty),
        "entry_price": float(entry_value / entry_qty),
        "exit_price": float(exit_value / exit_qty),
        "entry_time": timestamp(min(f["timestamp"] for f in entry)),
        "exit_time": timestamp(max(f["timestamp"] for f in exit_)),
        "gross_pnl": float(gross),
        "fees": float(fees),
        "net_pnl": float(gross - fees),
        "exit_reason": "exchange_fill",
    }
