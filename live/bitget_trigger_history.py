"""Bitget Classic V2 plan history reader. Authenticated, read-only.

Does not infer a child order ID unless explicitly present in the API result.
Incomplete history must never be used to clear journal state or unlock orders.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class TriggerHistoryItem:
    plan_order_id: str
    client_id: str | None
    symbol: str
    status: str
    plan_type: str
    trigger_price: Decimal | None
    child_order_id: str | None


@dataclass(frozen=True)
class TriggerHistoryPage:
    items: tuple[TriggerHistoryItem, ...]
    # This only means the requested endpoint returned its terminal page.
    # It does not prove history is exhaustive across exchange retention windows.
    page_terminated: bool
    live_execution_authorized: bool = False


def _optional_decimal(value):
    if value in (None, ''):
        return None
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RuntimeError('Invalid trigger price') from None
    if not n.is_finite() or n <= 0:
        raise RuntimeError('Invalid trigger price')
    return n


def _optional_id(value, label):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError('Invalid ' + label)
    return value


class BitgetTriggerHistoryReader:
    METHOD = 'privateMixGetV2MixOrderOrdersPlanHistory'

    def __init__(self, gateway):
        if gateway.config.symbol != 'SOL/USDT:USDT':
            raise ValueError('Unsupported symbol')
        self.gateway = gateway

    def fetch(self, *, plan_type='normal_plan', max_pages=10):
        if plan_type not in ('normal_plan', 'track_plan', 'profit_loss'):
            raise ValueError('Unsupported plan type')
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 100:
            raise ValueError('Invalid max_pages')
        market = self.gateway.connect()
        if market.get('id') != 'SOLUSDT' or market.get('swap') is not True or market.get('linear') is not True:
            raise RuntimeError('Unexpected market')
        method = getattr(self.gateway.exchange, self.METHOD, None)
        if not callable(method):
            raise RuntimeError('Bitget V2 plan-history endpoint unavailable')
        cursor = None
        seen_cursors = set()
        seen_ids = set()
        items = []
        for _ in range(max_pages):
            params = {'productType': 'USDT-FUTURES', 'symbol': 'SOLUSDT',
                      'planType': plan_type, 'limit': '100'}
            if cursor:
                params['idLessThan'] = cursor
            raw = method(params)
            if not isinstance(raw, dict) or raw.get('code') != '00000':
                raise RuntimeError('Plan-history API error')
            data = raw.get('data')
            if not isinstance(data, dict):
                raise RuntimeError('Invalid plan-history data')
            rows = data.get('entrustedList')
            if rows is None:
                if cursor is not None or data.get('endId') not in (None, ''):
                    raise RuntimeError('Ambiguous null history page')
                rows = []
            if not isinstance(rows, list) or len(rows) > 100:
                raise RuntimeError('Invalid plan-history rows')
            for row in rows:
                if not isinstance(row, dict) or row.get('symbol') != 'SOLUSDT':
                    raise RuntimeError('Unexpected plan-history symbol')
                plan_id = _optional_id(row.get('orderId'), 'plan ID')
                if plan_id is None or plan_id in seen_ids:
                    raise RuntimeError('Missing or duplicate plan ID')
                seen_ids.add(plan_id)
                status = row.get('status')
                if not isinstance(status, str) or not status:
                    raise RuntimeError('Missing plan status')
                # Field is not always present; never synthesize it from price/time.
                child = _optional_id(row.get('executeOrderId'), 'execution order ID')
                items.append(TriggerHistoryItem(
                    plan_id, _optional_id(row.get('clientOid'), 'client ID'),
                    'SOLUSDT', status, plan_type,
                    _optional_decimal(row.get('triggerPrice')), child))
            if len(rows) < 100:
                return TriggerHistoryPage(tuple(items), True)
            next_cursor = data.get('endId')
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
                raise RuntimeError('Unverifiable history pagination')
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        raise RuntimeError('History pagination cap reached; incomplete history')

    def find_verified(self, *, plan_order_id, client_id):
        if not isinstance(plan_order_id, str) or not plan_order_id:
            raise ValueError('Plan order ID required')
        if not isinstance(client_id, str) or not client_id:
            raise ValueError('Client ID required')
        page = self.fetch()
        matches = [x for x in page.items if x.plan_order_id == plan_order_id]
        if len(matches) != 1:
            raise RuntimeError('Plan order not found uniquely; manual reconciliation')
        item = matches[0]
        if item.client_id != client_id:
            raise RuntimeError('Plan client ID missing or mismatched')
        return item
