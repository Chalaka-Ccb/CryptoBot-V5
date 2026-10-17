"""Phase 6G: offline authorization boundary. No exchange write operations.

A validated intent is not authorization to trade. This module intentionally
has no path to an exchange create_order/cancel_order endpoint.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from live.live_order_lifecycle import OrderIntent


@dataclass(frozen=True)
class SubmissionPreview:
    client_id: str
    symbol: str
    margin_mode: str
    position_mode: str
    side: str
    contracts: str
    entry: str
    stop_loss: str
    take_profit: str
    execution_enabled: bool = False


class BitgetSubmissionGate:
    """Produce offline previews, always reject real submissions."""
    def __init__(self, gateway, guard):
        self.gateway = gateway
        self.guard = guard

    @staticmethod
    def _positive(value, name):
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f'Invalid {name}') from None
        if not number.is_finite() or number <= 0:
            raise ValueError(f'Invalid {name}')
        return str(number)

    def preview(self, intent: OrderIntent) -> SubmissionPreview:
        if not isinstance(intent, OrderIntent):
            raise TypeError('OrderIntent required')
        if self.gateway.config.symbol != 'SOL/USDT:USDT':
            raise RuntimeError('Unsupported market')
        if self.gateway.config.strategy != 'bollinger_channel_rebound':
            raise RuntimeError('Unsupported strategy')
        # This performs the combined ordinary-order, position and plan checks.
        checked = self.guard.prepare_intent(intent)
        if checked.intent != intent or not all((checked.checked_ordinary_orders,
                checked.checked_positions, checked.checked_plan_orders)):
            raise RuntimeError('Incomplete account verification')
        return SubmissionPreview(
            client_id=intent.client_id, symbol=intent.symbol,
            margin_mode='isolated', position_mode='one_way', side=intent.side,
            contracts=self._positive(intent.contracts, 'contracts'),
            entry=self._positive(intent.entry, 'entry'),
            stop_loss=self._positive(intent.stop_loss, 'stop loss'),
            take_profit=self._positive(intent.take_profit, 'take profit'))

    def submit_order(self, *args, **kwargs):
        raise RuntimeError('PHASE 6G WRITE LOCK: exchange order submission is disabled')

    def cancel_order(self, *args, **kwargs):
        raise RuntimeError('PHASE 6G WRITE LOCK: exchange cancellation is disabled')

    def amend_protection(self, *args, **kwargs):
        raise RuntimeError('PHASE 6G WRITE LOCK: protection amendments are disabled')
