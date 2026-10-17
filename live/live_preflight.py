"""Phase 6: fail-closed Bitget local-live preflight. NO ORDER SUBMISSION.

Prepares an indicative entry plan only; it does not reserve funds, set leverage,
change position mode, or submit any exchange orders.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

from core.models.signal import SignalSide, EntryTiming
from risk.risk_reward import validate_levels
from risk.validation import finite_number


@dataclass(frozen=True)
class EntryPlan:
    symbol: str
    side: str
    trigger_price: float
    stop_loss: float
    take_profit: float
    base_quantity: float
    contracts: float
    notional_usdt: float
    estimated_margin_usdt: float
    max_loss_before_fees_usdt: float
    balance_usdt: float
    leverage_assumption: float
    risk_fraction: float


class LivePreflight:
    def __init__(self, gateway, *, risk_fraction=0.02, leverage=5.0,
                 fee_rate=0.0006, margin_reserve=0.0):
        self.gateway = gateway
        self.risk_fraction = finite_number('risk_fraction', risk_fraction, positive=True)
        self.leverage = finite_number('leverage', leverage, positive=True)
        self.fee_rate = finite_number('fee_rate', fee_rate)
        self.margin_reserve = finite_number('margin_reserve', margin_reserve)
        if self.risk_fraction > 0.05 or not 1 <= self.leverage <= 15:
            raise ValueError('Live V1 limits: risk <= 5%, leverage 1-15x')
        if self.fee_rate < 0 or self.margin_reserve < 0:
            raise ValueError('Fees and reserve must be nonnegative')

    def _check_flat(self):
        exchange = self.gateway.exchange
        symbol = self.gateway.config.symbol
        if not exchange.has.get('fetchOpenOrders'):
            raise RuntimeError('Cannot verify open orders: exchange support unavailable')
        orders = exchange.fetch_open_orders(symbol)
        if orders is None or orders:
            raise RuntimeError('Existing or unverified open orders; no new entries')
        positions = self.gateway.fetch_positions()
        if positions is None:
            raise RuntimeError('Cannot verify current positions')
        for position in positions:
            if position.get('symbol') != symbol:
                continue
            contracts = position.get('contracts')
            if contracts is None:
                raise RuntimeError('Cannot determine existing position size')
            if abs(finite_number('position contracts', contracts)) > 0:
                raise RuntimeError('Existing position; no new entries')
        # Account position mode is not reliably exposed across CCXT/Bitget versions.
        # Explicit exchange-side verification is still mandatory before real orders.

    def prepare(self, signal):
        symbol = self.gateway.config.symbol
        if signal.strategy != self.gateway.config.strategy:
            raise ValueError('Wrong strategy')
        if signal.entry_timing != EntryTiming.BREAKOUT:
            raise ValueError('Only breakout signals supported')
        if signal.side not in (SignalSide.LONG, SignalSide.SHORT):
            raise ValueError('Invalid side')
        if signal.trigger_price is None or signal.stop_loss is None or signal.take_profit is None:
            raise ValueError('Missing entry/stop/target')
        entry = finite_number('entry', signal.trigger_price, positive=True)
        stop = finite_number('stop', signal.stop_loss, positive=True)
        target = finite_number('target', signal.take_profit, positive=True)
        validate_levels(entry, stop, signal.side, target)
        market = self.gateway.connect()
        self._check_flat()
        balance = self.gateway.fetch_available_balance()
        free = finite_number('free_usdt', balance.free_usdt)
        total = finite_number('total_usdt', balance.total_usdt)
        if free <= self.margin_reserve or total <= 0:
            raise RuntimeError('Insufficient USDT for live entry')
        contract_size = finite_number('contractSize', market.get('contractSize'), positive=True)
        if market.get('contract') is not True:
            raise RuntimeError('Expected a contract market')
        # Risk includes approximate two-sided taker fees. This is a planning
        # estimate, NOT a guarantee against gaps, slippage, or liquidation.
        risk_per_base = abs(entry-stop) + (entry+stop)*self.fee_rate
        risk_budget = total*self.risk_fraction
        qty_by_risk = risk_budget/risk_per_base
        qty_by_margin = (free-self.margin_reserve)*self.leverage/(entry*(1+self.fee_rate))
        raw_contracts = min(qty_by_risk, qty_by_margin)/contract_size
        if raw_contracts <= 0:
            raise RuntimeError('Zero allowed quantity')
        # CCXT amount is contracts for contract markets; precision must be
        # rounded DOWN rather than nearest, to avoid increasing risk.
        precision = market.get('precision', {}).get('amount')
        if precision is None:
            raise RuntimeError('Unknown contract amount precision')
        precision_mode = getattr(self.gateway.exchange, 'precisionMode', None)
        # CCXT DECIMAL_PLACES=2, TICK_SIZE=4; SIGNIFICANT_DIGITS=3.
        if precision_mode == 4:
            step = Decimal(str(precision))
        elif precision_mode == 2:
            step = Decimal(1).scaleb(-int(precision))
        else:
            raise RuntimeError('Unsupported amount precision mode; cannot size safely')
        if step <= 0:
            raise RuntimeError('Invalid amount step')
        contracts_d = (Decimal(str(raw_contracts))/step).to_integral_value(rounding=ROUND_FLOOR)*step
        contracts = float(contracts_d)
        if contracts <= 0:
            raise RuntimeError('Rounded contract size is zero')
        limits = market.get('limits', {})
        amount_limits = limits.get('amount') or {}
        cost_limits = limits.get('cost') or {}
        if amount_limits.get('min') is not None and contracts < float(amount_limits['min']):
            raise RuntimeError('Below exchange minimum contracts')
        if amount_limits.get('max') is not None and contracts > float(amount_limits['max']):
            raise RuntimeError('Above exchange maximum contracts')
        base_qty = contracts*contract_size
        notional = base_qty*entry
        if cost_limits.get('min') is not None and notional < float(cost_limits['min']):
            raise RuntimeError('Below exchange minimum notional')
        margin = notional/self.leverage
        if margin + notional*self.fee_rate > free-self.margin_reserve + 1e-9:
            raise RuntimeError('Insufficient margin after precision')
        estimated_loss = base_qty*abs(entry-stop)
        if estimated_loss + base_qty*(entry+stop)*self.fee_rate > risk_budget+1e-8:
            raise RuntimeError('Risk cap exceeded after rounding')
        return EntryPlan(symbol, signal.side.value, entry, stop, target, base_qty,
                         contracts, notional, margin, estimated_loss, total,
                         self.leverage, self.risk_fraction)
