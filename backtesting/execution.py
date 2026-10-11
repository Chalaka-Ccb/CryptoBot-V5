# from dataclasses import dataclass, replace
# from datetime import datetime
# from datetime import datetime, timedelta
# from backtesting.broker import BacktestBroker
# from core.enums.position import PositionSide
# from core.models.signal import (
#     TradingSignal,
#     SignalSide,
#     EntryTiming,
# )
# from engine.risk_manager import RiskManager
#
#
# @dataclass
# class PendingEntry:
#     signal: TradingSignal
#     symbol: str
#     timeframe: str
#
#
# class BacktestExecution:
#
#     def __init__(
#             self,
#             broker: BacktestBroker,
#             risk_manager: RiskManager,
#             default_stop_percentage: float = 0.01,
#     ):
#         if not 0 < default_stop_percentage < 1:
#             raise ValueError(
#                 "default_stop_percentage must be between 0 and 1"
#             )
#
#         self.broker = broker
#         self.risk_manager = risk_manager
#         self.default_stop_percentage = default_stop_percentage
#
#     def prepare_signal(
#             self,
#             signal: TradingSignal,
#             entry_price: float,
#     ) -> TradingSignal:
#
#         if signal.stop_loss is not None:
#             return signal
#
#         if signal.side == SignalSide.LONG:
#             stop_loss = entry_price * (
#                     1 - self.default_stop_percentage
#             )
#
#         elif signal.side == SignalSide.SHORT:
#             stop_loss = entry_price * (
#                     1 + self.default_stop_percentage
#             )
#
#         else:
#             raise ValueError("Unsupported signal side")
#
#         return replace(
#             signal,
#             stop_loss=stop_loss,
#         )
#
#     def can_enter(self, symbol: str) -> bool:
#         return not self.broker.has_open_trade(symbol)
#
#     def sync_account(self) -> None:
#         account = self.risk_manager.account
#         account.balance = self.broker.balance
#         account.available_balance = self.broker.balance
#
#     def create_pending_entry(
#         self,
#         signal: TradingSignal,
#         symbol: str,
#         timeframe: str,
#     ) -> PendingEntry:
#
#         return PendingEntry(
#             signal=signal,
#             symbol=symbol,
#             timeframe=timeframe,
#         )
#
#     def execute_entry(
#         self,
#         pending: PendingEntry,
#         entry_price: float,
#         timestamp: datetime,
#     ):
#         signal = pending.signal
#
#         if not self.can_enter(pending.symbol):
#             return None
#
#         if entry_price <= 0:
#             return None
#
#         signal = self.prepare_signal(
#             signal=pending.signal,
#             entry_price=entry_price,
#         )
#
#         if entry_price <= 0:
#             return None
#
#         # Validate stop-loss direction.
#         if signal.side == SignalSide.LONG:
#             if signal.stop_loss >= entry_price:
#                 return None
#             side = PositionSide.LONG
#
#         elif signal.side == SignalSide.SHORT:
#             if signal.stop_loss <= entry_price:
#                 return None
#             side = PositionSide.SHORT
#
#         else:
#             return None
#
#         # Validate strategy-provided TP.
#         if signal.take_profit is not None:
#             if (
#                 signal.side == SignalSide.LONG
#                 and signal.take_profit <= entry_price
#             ):
#                 return None
#
#             if (
#                 signal.side == SignalSide.SHORT
#                 and signal.take_profit >= entry_price
#             ):
#                 return None
#
#         # Position sizing uses latest realized balance.
#         self.sync_account()
#
#         try:
#             decision = self.risk_manager.evaluate(
#                 signal=signal,
#                 entry_price=entry_price,
#             )
#         except (ValueError, ZeroDivisionError) as error:
#             print(
#                 f"ENTRY REJECTED: {signal.strategy}: {error}"
#             )
#             return None
#
#         if not decision.approved:
#             print(
#                 f"ENTRY REJECTED: {signal.strategy}: "
#                 f"{decision.reason}"
#             )
#             return None
#
#         if (
#             decision.position_size is None
#             or decision.risk_reward is None
#         ):
#             return None
#
#         quantity = decision.position_size.position_size
#
#         if quantity <= 0:
#             return None
#
#         # RiskManager already preserves strategy TP,
#         # or calculates the default 3:1 target.
#         take_profit = decision.risk_reward.take_profit
#
#         trade = self.broker.open_trade(
#             symbol=pending.symbol,
#             side=side,
#             quantity=quantity,
#             entry_price=entry_price,
#             stop_loss=signal.stop_loss,
#             take_profit=take_profit,
#             strategy=signal.strategy,
#             timestamp=timestamp,
#         )
#
#         return trade
#
#     def execute_current_close(
#             self,
#             pending: PendingEntry,
#             candle,
#     ):
#         if pending.signal.entry_timing != EntryTiming.CURRENT_CLOSE:
#             return None
#
#         # All CURRENT_CLOSE executions use our 5m
#         # execution candle, regardless of whether
#         # the signal originated from 15m or 5m.
#         close_time = candle.timestamp + timedelta(minutes=5)
#
#         return self.execute_entry(
#             pending=pending,
#             entry_price=candle.close,
#             timestamp=close_time,
#         )
#
#     def execute_next_open(
#         self,
#         pending: PendingEntry,
#         candle,
#     ):
#         if pending.signal.entry_timing != EntryTiming.NEXT_OPEN:
#             return None
#
#         return self.execute_entry(
#             pending=pending,
#             entry_price=candle.open,
#             timestamp=candle.timestamp,
#         )
#
#     def execute_breakout(
#         self,
#         pending: PendingEntry,
#         candle,
#     ):
#         signal = pending.signal
#
#         if signal.entry_timing != EntryTiming.BREAKOUT:
#             return None
#
#         trigger = signal.trigger_price
#
#         if trigger is None or trigger <= 0:
#             return None
#
#         # LONG stop entry
#         if signal.side == SignalSide.LONG:
#             if candle.high < trigger:
#                 return None
#
#             # Gap through trigger: fill at opening price.
#             entry_price = max(candle.open, trigger)
#
#         # SHORT stop entry
#         elif signal.side == SignalSide.SHORT:
#             if candle.low > trigger:
#                 return None
#
#             entry_price = min(candle.open, trigger)
#
#         else:
#             return None
#
#         return self.execute_entry(
#             pending=pending,
#             entry_price=entry_price,
#             timestamp=candle.timestamp,
#         )

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from backtesting.broker import BacktestBroker
from core.enums.position import PositionSide
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from engine.risk_manager import RiskManager
from risk.validation import finite_number


@dataclass
class PendingEntry:
    signal: TradingSignal
    symbol: str
    timeframe: str


class BacktestExecution:
    def __init__(self, broker: BacktestBroker, risk_manager: RiskManager,
                 default_stop_percentage: float = 0.01):
        stop = finite_number('default_stop_percentage', default_stop_percentage, positive=True)
        if stop >= 1:
            raise ValueError('default_stop_percentage must be between 0 and 1')
        self.broker = broker
        self.risk_manager = risk_manager
        self.default_stop_percentage = stop

    def prepare_signal(self, signal, entry_price):
        if signal.stop_loss is not None:
            return signal
        if signal.side == SignalSide.LONG:
            stop = entry_price * (1 - self.default_stop_percentage)
        elif signal.side == SignalSide.SHORT:
            stop = entry_price * (1 + self.default_stop_percentage)
        else:
            raise ValueError('Unsupported signal side')
        return replace(signal, stop_loss=stop)

    def can_enter(self, symbol):
        return not self.broker.has_open_trade(symbol)

    def sync_account(self):
        account = self.risk_manager.account
        balance = finite_number('broker balance', self.broker.balance)
        # Fixed leverage for this backtest run. Derive reservations from OPEN
        # trades so closing a trade automatically releases its margin.
        margin = 0.0
        for trade in self.broker.current_trades.values():
            if trade.is_open:
                quantity = finite_number('open quantity', trade.quantity, positive=True)
                entry = finite_number('open entry', trade.entry_price, positive=True)
                margin += quantity * entry / self.risk_manager.limits.leverage
        finite_number('used_margin', margin)
        account.balance = balance
        account.used_margin = margin
        account.available_balance = max(0.0, balance - margin)
        # Preserve unrealized PnL if the runner supplies current marks.
        # Without mark updates, this remains a realized-balance backtest.
        account.total_realized_pnl = balance - account.initial_balance

    def create_pending_entry(self, signal, symbol, timeframe):
        return PendingEntry(signal, symbol, timeframe)

    def execute_entry(self, pending, entry_price, timestamp):
        if not self.can_enter(pending.symbol):
            return None
        try:
            finite_number('entry_price', entry_price, positive=True)
            signal = self.prepare_signal(pending.signal, entry_price)
            self.sync_account()
            decision = self.risk_manager.evaluate(signal, entry_price, symbol=pending.symbol)
            if not decision.approved:
                print(f'ENTRY REJECTED: {signal.strategy}: {decision.reason}')
                return None
            if decision.position_size is None or decision.risk_reward is None:
                return None
            side = PositionSide.LONG if signal.side == SignalSide.LONG else PositionSide.SHORT
            trade = self.broker.open_trade(
                symbol=pending.symbol, side=side,
                quantity=decision.position_size.position_size,
                entry_price=entry_price, stop_loss=signal.stop_loss,
                take_profit=decision.risk_reward.take_profit,
                strategy=signal.strategy, timestamp=timestamp,
            )
        except (ValueError, ArithmeticError) as error:
            print(f'ENTRY REJECTED: {pending.signal.strategy}: {error}')
            return None
        self.sync_account()
        return trade

    def execute_current_close(self, pending, candle):
        if pending.signal.entry_timing != EntryTiming.CURRENT_CLOSE:
            return None
        return self.execute_entry(pending, candle.close,
                                  candle.timestamp + timedelta(minutes=5))

    def execute_next_open(self, pending, candle):
        if pending.signal.entry_timing != EntryTiming.NEXT_OPEN:
            return None
        return self.execute_entry(pending, candle.open, candle.timestamp)

    def execute_breakout(self, pending, candle):
        signal = pending.signal
        if signal.entry_timing != EntryTiming.BREAKOUT:
            return None
        try:
            trigger = finite_number('trigger_price', signal.trigger_price, positive=True)
        except ValueError:
            return None
        if signal.side == SignalSide.LONG:
            if candle.high < trigger:
                return None
            entry = max(candle.open, trigger)
        elif signal.side == SignalSide.SHORT:
            if candle.low > trigger:
                return None
            entry = min(candle.open, trigger)
        else:
            return None
        return self.execute_entry(pending, entry, candle.timestamp)
