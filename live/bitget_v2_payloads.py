"""Phase 6T: offline Classic V2 endpoint-specific candidate payloads.

NO network calls, submission, protection claims or trading authorization.
"""
from dataclasses import dataclass
from decimal import Decimal
from live.live_order_lifecycle import OrderIntent


def fmt(value):
    n = Decimal(str(value))
    if not n.is_finite() or n <= 0:
        raise ValueError('Nonpositive or nonfinite amount')
    return format(n, 'f')


@dataclass(frozen=True)
class EndpointPayload:
    endpoint: str
    body: dict


@dataclass(frozen=True)
class OfflineOrderBundle:
    entry: EndpointPayload
    stop: EndpointPayload
    target: EndpointPayload
    executable: bool = False


class BitgetV2PayloadBuilder:
    def build(self, intent: OrderIntent) -> OfflineOrderBundle:
        if not isinstance(intent, OrderIntent):
            raise TypeError('OrderIntent required')
        base = dict(symbol='SOLUSDT', productType='USDT-FUTURES',
                    marginCoin='USDT')
        side = 'buy' if intent.side == 'long' else 'sell'
        # Plan trigger submits a MARKET order when triggered. No guaranteed
        # execution price; gap/slippage and fees must be accounted for.
        entry = dict(base, planType='normal_plan', marginMode='isolated',
                     size=fmt(intent.contracts), side=side,
                     orderType='market', triggerPrice=fmt(intent.entry),
                     triggerType='mark_price', clientOid=intent.client_id)
        common = dict(base, holdSide=intent.side, size=fmt(intent.contracts),
                      triggerType='mark_price', executePrice='0')
        stop = dict(common, planType='loss_plan',
                    triggerPrice=fmt(intent.stop_loss),
                    clientOid=f'{intent.client_id}-sl')
        target = dict(common, planType='profit_plan',
                      triggerPrice=fmt(intent.take_profit),
                      clientOid=f'{intent.client_id}-tp')
        return OfflineOrderBundle(
            EndpointPayload('/api/v2/mix/order/place-plan-order', entry),
            EndpointPayload('/api/v2/mix/order/place-tpsl-order', stop),
            EndpointPayload('/api/v2/mix/order/place-tpsl-order', target))
