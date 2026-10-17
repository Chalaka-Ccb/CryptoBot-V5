"""Phase 6K: offline Bitget Classic V2 order payload builder. NO NETWORK CALLS.

Builds candidate requests for review and mocked transport tests. Does NOT
assert that Bitget accepts them or that stop-loss / take-profit are installed.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from live.live_order_lifecycle import OrderIntent


def positive(value, label):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Invalid {label}") from None
    if not n.is_finite() or n <= 0:
        raise ValueError(f"Invalid {label}")
    return format(n, 'f')


@dataclass(frozen=True)
class CandidateOrderRequests:
    entry: dict
    stop: dict
    target: dict
    executable: bool = False


class BitgetOrderRequestBuilder:
    """Classic V2 candidate payloads for SOLUSDT isolated one-way swaps.

    Assumes exchange mode has ALREADY been verified independently.
    The protective plan payloads must be checked against Bitget's current API
    and observed read-only plan snapshots before enabling writes.
    """
    def build(self, intent: OrderIntent) -> CandidateOrderRequests:
        if not isinstance(intent, OrderIntent):
            raise TypeError("OrderIntent required")
        if intent.symbol != "SOL/USDT:USDT":
            raise ValueError("Unsupported symbol")
        side = 'buy' if intent.side == 'long' else 'sell'
        exit_side = 'sell' if intent.side == 'long' else 'buy'
        size = positive(intent.contracts, 'contracts')
        entry_price = positive(intent.entry, 'entry')
        sl = positive(intent.stop_loss, 'stop')
        tp = positive(intent.take_profit, 'target')
        # Entry is a stop/trigger order, NOT a market order.
        entry = dict(symbol='SOLUSDT', productType='USDT-FUTURES',
                     marginMode='isolated', marginCoin='USDT',
                     size=size, side=side, tradeSide='open',
                     orderType='limit', price=entry_price,
                     triggerPrice=entry_price, triggerType='mark_price',
                     clientOid=intent.client_id)
        common = dict(symbol='SOLUSDT', productType='USDT-FUTURES',
                      marginCoin='USDT', size=size, side=exit_side,
                      holdSide=intent.side, triggerType='mark_price',
                      executePrice='0')
        stop = dict(common, planType='loss_plan', triggerPrice=sl)
        target = dict(common, planType='profit_plan', triggerPrice=tp)
        return CandidateOrderRequests(entry, stop, target)
