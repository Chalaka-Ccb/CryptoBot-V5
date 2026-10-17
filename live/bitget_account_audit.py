"""Phase 6N: read-only, fail-closed account readiness audit.

Requires independently supplied account-mode evidence. No inferred defaults,
no CCXT write endpoints and no automatic margin/position-mode changes.
"""
from dataclasses import dataclass
from live.bitget_order_adapter import BitgetOrderAdapter
from live.bitget_plan_inspector import BitgetPlanInspector


@dataclass(frozen=True)
class AccountModeEvidence:
    margin_mode: str
    position_mode: str
    source: str


@dataclass(frozen=True)
class AuditResult:
    symbol: str
    margin_mode: str
    position_mode: str
    ordinary_orders: int
    plan_orders: int
    positions: int
    ready_for_review: bool = True
    live_execution_authorized: bool = False


class BitgetAccountAudit:
    def __init__(self, gateway, *, order_adapter=None, plan_inspector=None):
        self.gateway = gateway
        self.orders = order_adapter or BitgetOrderAdapter(gateway)
        self.plans = plan_inspector or BitgetPlanInspector(gateway)

    def run(self, mode_evidence: AccountModeEvidence):
        if not isinstance(mode_evidence, AccountModeEvidence):
            raise RuntimeError("Explicit verified account-mode evidence required")
        if mode_evidence.source != 'verified_exchange_response':
            raise RuntimeError("Account modes must come from verified exchange response")
        if mode_evidence.margin_mode != 'isolated' or mode_evidence.position_mode != 'one_way':
            raise RuntimeError("Expected isolated margin and one-way position mode")
        market = self.gateway.connect()
        if self.gateway.config.symbol != 'SOL/USDT:USDT':
            raise RuntimeError("Unsupported symbol")
        if market.get('swap') is not True or market.get('linear') is not True or market.get('settle') != 'USDT' or market.get('active') is False:
            raise RuntimeError("Unexpected or inactive perpetual market")
        if self.orders.fetch_open_orders():
            raise RuntimeError("Ordinary orders exist")
        if self.plans.fetch_all():
            raise RuntimeError("Pending plan or protection orders exist")
        positions = self.gateway.fetch_positions()
        if not isinstance(positions, list):
            raise RuntimeError("Unverifiable positions")
        for position in positions:
            if not isinstance(position, dict):
                raise RuntimeError("Malformed position")
            if position.get('symbol') != self.gateway.config.symbol:
                raise RuntimeError("Unexpected position symbol in scoped response")
            contracts = position.get('contracts')
            if isinstance(contracts, bool) or not isinstance(contracts, (int, float)):
                raise RuntimeError("Invalid position size")
            from math import isfinite
            if not isfinite(contracts) or contracts < 0:
                raise RuntimeError("Invalid position size")
            if contracts != 0:
                raise RuntimeError("Existing open position")
        return AuditResult(self.gateway.config.symbol, 'isolated', 'one_way', 0, 0, len(positions))
