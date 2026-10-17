"""Phase 6Q: authenticated READ-ONLY Bitget state probe.

Outputs aggregate counts only. Does not call any order-write methods.
"""
from dataclasses import dataclass
from math import isfinite

from live.bitget_gateway import BitgetGateway
from live.config import LiveConfig
from live.bitget_plan_inspector import BitgetPlanInspector


@dataclass(frozen=True)
class ReadProbeReport:
    symbol: str
    positions_returned: int
    open_positions: int
    ordinary_open_orders: int
    pending_plan_orders: int
    account_mode_verified: bool = False
    live_execution_authorized: bool = False


class BitgetLiveReadProbe:
    def __init__(self, gateway, inspector=None):
        self.gateway = gateway
        self.inspector = inspector or BitgetPlanInspector(gateway)

    def run(self):
        market = self.gateway.connect()
        if market.get('id') != 'SOLUSDT' or market.get('swap') is not True or market.get('linear') is not True:
            raise RuntimeError('Unexpected market')
        positions = self.gateway.fetch_positions()
        if not isinstance(positions, list):
            raise RuntimeError('Unreliable positions response')
        active = 0
        for p in positions:
            if not isinstance(p, dict) or p.get('symbol') != 'SOL/USDT:USDT':
                raise RuntimeError('Unexpected position record')
            size = p.get('contracts')
            if isinstance(size, bool) or not isinstance(size, (int, float)) or not isfinite(size) or size < 0:
                raise RuntimeError('Unreliable position size')
            if size:
                active += 1
        exchange = self.gateway.exchange
        if not exchange.has.get('fetchOpenOrders'):
            raise RuntimeError('Open-order read unsupported')
        orders = exchange.fetch_open_orders('SOL/USDT:USDT')
        if not isinstance(orders, list):
            raise RuntimeError('Unreliable ordinary orders response')
        plans = self.inspector.fetch_all()
        if not isinstance(plans, list):
            raise RuntimeError('Unreliable pending plans response')
        return ReadProbeReport('SOL/USDT:USDT', len(positions), active, len(orders), len(plans))


if __name__ == '__main__':
    report = BitgetLiveReadProbe(BitgetGateway(LiveConfig())).run()
    print(report)
