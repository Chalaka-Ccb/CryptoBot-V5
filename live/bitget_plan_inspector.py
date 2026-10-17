"""Read-only Classic Bitget V2 USDT futures plan-order inspector.

Fail closed on unknown account API, pagination, responses or plan categories.
Never submits/cancels/modifies orders. Not a proof that a position is protected.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

PLAN_TYPES = ('normal_plan', 'track_plan', 'profit_loss')


@dataclass(frozen=True)
class PlanSnapshot:
    plan_type: str
    order_id: str
    symbol: str
    status: str
    subtype: str | None
    trigger_price: Decimal | None
    size: Decimal | None


class BitgetPlanInspector:
    def __init__(self, gateway):
        if gateway.config.symbol != 'SOL/USDT:USDT':
            raise ValueError('Only SOL/USDT:USDT supported')
        self.gateway = gateway

    @staticmethod
    def _decimal(value, name):
        if value is None or value == '':
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise RuntimeError(f'Invalid {name}') from None
        if not result.is_finite() or result < 0:
            raise RuntimeError(f'Invalid {name}')
        return result

    def fetch_all(self):
        if self.gateway._market is None:
            self.gateway.connect()
        exchange = self.gateway.exchange
        method = getattr(exchange, 'privateMixGetV2MixOrderOrdersPlanPending', None)
        if not callable(method):
            raise RuntimeError('Classic V2 plan-order read endpoint unavailable; account compatibility must be verified')
        market_id = self.gateway._market.get('id')
        if not isinstance(market_id, str) or not market_id:
            raise RuntimeError('Unknown exchange market ID')
        result = []
        for plan_type in PLAN_TYPES:
            cursor = None
            seen = set()
            for _ in range(100):
                params = {'productType': 'USDT-FUTURES', 'planType': plan_type, 'symbol': market_id, 'limit': '100'}
                if cursor:
                    params['idLessThan'] = cursor
                raw = method(params)
                if not isinstance(raw, dict) or raw.get('code') != '00000':
                    raise RuntimeError(f'Bitget plan query failed: {plan_type}')
                data = raw.get('data')
                if not isinstance(data, dict):
                    raise RuntimeError('Malformed plan-order response data')
                if 'entrustedList' not in data:
                    raise RuntimeError('Missing plan-order list')
                rows = data['entrustedList']
                if rows is None:
                    # Bitget Classic V2 returns null for an empty first page.
                    # Only accept this when pagination is also empty.
                    if cursor is not None or data.get('endId') not in (None, ''):
                        raise RuntimeError('Ambiguous null plan-order page')
                    rows = []
                if not isinstance(rows, list):
                    raise RuntimeError('Invalid plan-order list')
                for row in rows:
                    if not isinstance(row, dict):
                        raise RuntimeError('Malformed plan order')
                    symbol = row.get('symbol')
                    if not isinstance(symbol, str) or symbol.upper() != market_id.upper():
                        raise RuntimeError('Unexpected plan-order symbol')
                    order_id = row.get('orderId')
                    if not isinstance(order_id, str) or not order_id:
                        raise RuntimeError('Missing plan-order ID')
                    status = row.get('status')
                    if not isinstance(status, str) or not status:
                        raise RuntimeError('Unknown plan-order status')
                    subtype = row.get('planType')
                    if subtype is not None and not isinstance(subtype, str):
                        raise RuntimeError('Invalid plan subtype')
                    result.append(PlanSnapshot(plan_type, order_id, symbol, status, subtype,
                        self._decimal(row.get('triggerPrice'), 'trigger price'),
                        self._decimal(row.get('size'), 'plan size')))
                # Bitget classic response returns endId; short page terminates pagination.
                if len(rows) < 100:
                    break
                next_cursor = data.get('endId')
                if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen:
                    raise RuntimeError('Plan-order pagination cannot be verified')
                seen.add(next_cursor)
                cursor = next_cursor
            else:
                raise RuntimeError('Plan-order pagination limit reached')
        return result

    def assert_no_pending_plans(self):
        plans = self.fetch_all()
        if plans:
            raise RuntimeError(f'{len(plans)} Bitget plan/trigger/TP-SL orders detected; new entry blocked')
        return True
