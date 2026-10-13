from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from backtesting.fee_config import FeeConfig
from core.enums.position import PositionSide
from core.enums.trade import ExitReason
from core.models.trade import Trade


@dataclass
class BacktestBroker:
    balance: float
    trade_counter: int = 0
    fee_config: FeeConfig = field(default_factory=FeeConfig)
    total_fees: float = 0.0
    current_trades: dict[str, Trade] = field(default_factory=dict)
    trailing_stop_trades: set[str] = field(default_factory=set)

    def has_open_trade(self, symbol: str) -> bool:
        trade = self.current_trades.get(symbol)
        return trade is not None and trade.is_open

    def get_open_trade(self, symbol: str) -> Optional[Trade]:
        trade = self.current_trades.get(symbol)
        return trade if trade is not None and trade.is_open else None

    def open_trade(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        strategy: str,
        timestamp: datetime,
    ) -> Trade:

        if self.has_open_trade(symbol):
            raise ValueError(
                f"An active trade already exists for {symbol}"
            )

        if quantity <= 0 or entry_price <= 0:
            raise ValueError("Invalid quantity or entry price")

        if stop_loss is not None:
            if stop_loss <= 0:
                raise ValueError("Invalid stop-loss price")
            if side == PositionSide.LONG and stop_loss >= entry_price:
                raise ValueError("LONG stop must be below entry")
            if side == PositionSide.SHORT and stop_loss <= entry_price:
                raise ValueError("SHORT stop must be above entry")

        if take_profit is not None:
            if take_profit <= 0:
                raise ValueError("Invalid take-profit price")
            if side == PositionSide.LONG and take_profit <= entry_price:
                raise ValueError("LONG TP must be above entry")
            if side == PositionSide.SHORT and take_profit >= entry_price:
                raise ValueError("SHORT TP must be below entry")

        self.trade_counter += 1
        entry_notional = quantity * entry_price
        entry_fee = entry_notional * self.fee_config.taker_rate

        if self.balance < entry_fee:
            raise ValueError("Insufficient balance for entry fee")

        trade = Trade(
            trade_id=f"BT-{self.trade_counter:06d}",
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=timestamp,
            strategy=strategy,
            stop_loss=stop_loss,
            take_profit=take_profit,
            fees=entry_fee,
            entry_fee=entry_fee,
        )

        self.current_trades[symbol] = trade
        self.balance -= entry_fee
        self.total_fees += entry_fee

        print("\n===== TRADE OPENED =====")
        print(f"Trade ID: {trade.trade_id}")
        print(f"Strategy: {trade.strategy}")
        print(f"Side: {trade.side.value}")
        print(f"Entry: {trade.entry_price}")
        print(f"Quantity: {trade.quantity}")
        print(f"SL: {trade.stop_loss}")
        print(f"TP: {trade.take_profit}")
        print(f"Time: {trade.entry_time}")
        print(f"Entry fee: {entry_fee:.4f}")
        print(f"Balance after entry fee: {self.balance:.4f}")

        return trade

    def update_stop_loss(
        self,
        symbol: str,
        new_stop: float,
    ) -> bool:

        trade = self.get_open_trade(symbol)

        if trade is None or new_stop <= 0:
            return False

        if trade.side == PositionSide.LONG:
            if trade.stop_loss is not None and new_stop <= trade.stop_loss:
                return False

        elif trade.side == PositionSide.SHORT:
            if trade.stop_loss is not None and new_stop >= trade.stop_loss:
                return False

        else:
            return False

        old_stop = trade.stop_loss
        trade.stop_loss = new_stop

        self.trailing_stop_trades.add(trade.trade_id)

        print("\n===== TRAILING STOP UPDATED =====")
        print(f"Trade ID: {trade.trade_id}")
        print(f"Old SL: {old_stop}")
        print(f"New SL: {new_stop}")

        return True

    def process_candle(
        self,
        symbol: str,
        candle,
    ) -> Optional[Trade]:

        trade = self.get_open_trade(symbol)

        if trade is None:
            return None

        stop = trade.stop_loss
        target = trade.take_profit

        stop_reason = (
            ExitReason.TRAILING_STOP
            if trade.trade_id in self.trailing_stop_trades
            else ExitReason.STOP_LOSS
        )

        if trade.side == PositionSide.LONG:

            # Opening gaps are resolved before intrabar checks.
            if stop is not None and candle.open <= stop:
                return self.close_trade(
                    symbol, candle.open, candle.timestamp, stop_reason
                )

            if target is not None and candle.open >= target:
                return self.close_trade(
                    symbol, candle.open, candle.timestamp,
                    ExitReason.TAKE_PROFIT
                )

            # Conservative rule: SL before TP if both are hit.
            if stop is not None and candle.low <= stop:
                return self.close_trade(
                    symbol, stop, candle.timestamp, stop_reason
                )

            if target is not None and candle.high >= target:
                return self.close_trade(
                    symbol, target, candle.timestamp,
                    ExitReason.TAKE_PROFIT
                )

        elif trade.side == PositionSide.SHORT:

            if stop is not None and candle.open >= stop:
                return self.close_trade(
                    symbol, candle.open, candle.timestamp, stop_reason
                )

            if target is not None and candle.open <= target:
                return self.close_trade(
                    symbol, candle.open, candle.timestamp,
                    ExitReason.TAKE_PROFIT
                )

            if stop is not None and candle.high >= stop:
                return self.close_trade(
                    symbol, stop, candle.timestamp, stop_reason
                )

            if target is not None and candle.low <= target:
                return self.close_trade(
                    symbol, target, candle.timestamp,
                    ExitReason.TAKE_PROFIT
                )

        return None

    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_time: datetime,
        exit_reason: ExitReason,
    ) -> Trade:

        trade = self.get_open_trade(symbol)

        if trade is None:
            raise ValueError(f"No open trade for {symbol}")

        if exit_price <= 0:
            raise ValueError("Invalid exit price")

        exit_notional = trade.quantity * exit_price
        exit_fee = exit_notional * self.fee_config.taker_rate

        trade.close(
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=exit_reason,
            fees=exit_fee,
        )

        self.total_fees += exit_fee

        # Entry fee was already deducted at opening.
        # Therefore, only gross P&L minus exit fee is applied here.
        gross_pnl = trade.gross_pnl
        assert gross_pnl is not None

        self.balance += gross_pnl - exit_fee

        pnl = trade.net_pnl
        assert pnl is not None
        self.trailing_stop_trades.discard(trade.trade_id)

        print("\n===== TRADE CLOSED =====")
        print(f"Trade ID: {trade.trade_id}")
        print(f"Strategy: {trade.strategy}")
        print(f"Gross PnL: {gross_pnl:.4f}")
        print(f"Entry fee: {trade.entry_fee:.4f}")
        print(f"Exit fee: {trade.exit_fee:.4f}")
        print(f"Total fees: {trade.fees:.4f}")
        print(f"Net PnL: {pnl:.4f}")
        print(f"Reason: {trade.exit_reason.value}")
        print(f"Balance: {self.balance:.4f}")

        return trade