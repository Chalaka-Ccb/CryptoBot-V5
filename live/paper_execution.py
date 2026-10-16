"""Single-symbol, offline paper execution state machine for Live V1.

This component NEVER calls an exchange or sends orders. It models breakout
entries, protective exits, fees, and graceful stop requests. Candle-based
simulation is conservative when both stop and target are crossed.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.models.candle import Candle
from core.models.signal import TradingSignal, EntryTiming, SignalSide
from risk.risk_reward import validate_levels
from risk.validation import finite_number


class PaperState(str, Enum):
    IDLE = "idle"
    PENDING = "pending"
    OPEN = "open"
    STOPPED = "stopped"


@dataclass(frozen=True)
class PaperTrade:
    side: SignalSide
    entry: float
    exit: float
    quantity: float
    reason: str
    gross_pnl: float
    fees: float
    net_pnl: float


class SingleSymbolPaperExecution:
    def __init__(self, *, balance: float, risk_fraction: float = 0.02,
                 leverage: float = 5.0, fee_rate: float = 0.0006,
                 margin_reserve: float = 0.0):
        self.balance = finite_number('balance', balance, positive=True)
        self.risk_fraction = finite_number('risk_fraction', risk_fraction, positive=True)
        self.leverage = finite_number('leverage', leverage, positive=True)
        self.fee_rate = finite_number('fee_rate', fee_rate)
        self.margin_reserve = finite_number('margin_reserve', margin_reserve)
        if self.risk_fraction > 0.05 or not 1 <= self.leverage <= 15:
            raise ValueError('Live V1 risk/leverage cap exceeded')
        if self.fee_rate < 0 or self.margin_reserve < 0:
            raise ValueError('fee rate and reserve must not be negative')
        self.state = PaperState.IDLE
        self.stop_requested = False
        self.signal: Optional[TradingSignal] = None
        self.quantity = 0.0
        self.entry = 0.0
        self.target = 0.0
        self.trades: list[PaperTrade] = []

    def submit(self, signal: TradingSignal, *, reference_price: float) -> None:
        if self.state != PaperState.IDLE or self.stop_requested:
            raise RuntimeError('Already busy or shutting down')
        if signal.entry_timing != EntryTiming.BREAKOUT or signal.trigger_price is None:
            raise ValueError('Only Channel Rebound breakout entries supported')
        if signal.stop_loss is None or signal.take_profit is None:
            raise ValueError('Protective stop and target are mandatory')
        validate_levels(signal.trigger_price, signal.stop_loss, signal.side, signal.take_profit)
        finite_number('reference_price', reference_price, positive=True)
        self.signal = signal
        self.state = PaperState.PENDING

    def request_stop(self) -> None:
        self.stop_requested = True
        if self.state == PaperState.PENDING:
            self.signal = None
            self.state = PaperState.STOPPED
        elif self.state == PaperState.IDLE:
            self.state = PaperState.STOPPED

    def on_candle(self, candle: Candle) -> Optional[PaperTrade]:
        if self.state in (PaperState.IDLE, PaperState.STOPPED):
            return None
        assert self.signal is not None
        signal = self.signal
        if self.state == PaperState.PENDING:
            trigger = signal.trigger_price
            triggered = candle.high >= trigger if signal.side == SignalSide.LONG else candle.low <= trigger
            if not triggered:
                return None
            # If price gaps beyond the trigger, fill at the worse opening price.
            entry = max(trigger, candle.open) if signal.side == SignalSide.LONG else min(trigger, candle.open)
            if signal.side == SignalSide.LONG and entry >= signal.take_profit:
                self._cancel_pending()
                return None
            if signal.side == SignalSide.SHORT and entry <= signal.take_profit:
                self._cancel_pending()
                return None
            validate_levels(entry, signal.stop_loss, signal.side, signal.take_profit)
            free = max(0.0, self.balance - self.margin_reserve)
            risk_per_unit = abs(entry - signal.stop_loss) + 2 * entry * self.fee_rate
            quantity = min(self.balance * self.risk_fraction / risk_per_unit,
                           free * self.leverage / (entry * (1 + self.fee_rate)))
            if quantity <= 0:
                self._cancel_pending()
                return None
            self.entry, self.quantity = entry, quantity
            self.state = PaperState.OPEN
            # The triggering candle has unknown intrabar sequence. Do not assume
            # a favorable TP fill; conservatively process SL, otherwise wait.
            stop_hit = candle.low <= signal.stop_loss if signal.side == SignalSide.LONG else candle.high >= signal.stop_loss
            if stop_hit:
                return self._close(signal.stop_loss, 'SL')
            return None
        stop_hit = candle.low <= signal.stop_loss if signal.side == SignalSide.LONG else candle.high >= signal.stop_loss
        target_hit = candle.high >= signal.take_profit if signal.side == SignalSide.LONG else candle.low <= signal.take_profit
        if stop_hit:
            return self._close(signal.stop_loss, 'SL')
        if target_hit:
            return self._close(signal.take_profit, 'TP')
        return None

    def _cancel_pending(self):
        self.signal = None
        self.state = PaperState.STOPPED if self.stop_requested else PaperState.IDLE

    def _close(self, price: float, reason: str) -> PaperTrade:
        assert self.signal is not None
        direction = 1 if self.signal.side == SignalSide.LONG else -1
        gross = (price - self.entry) * self.quantity * direction
        fees = (self.entry + price) * self.quantity * self.fee_rate
        trade = PaperTrade(self.signal.side, self.entry, price, self.quantity,
                           reason, gross, fees, gross - fees)
        self.balance += trade.net_pnl
        self.trades.append(trade)
        self.signal = None
        self.quantity = 0.0
        self.entry = 0.0
        self.state = PaperState.STOPPED if self.stop_requested else PaperState.IDLE
        return trade
