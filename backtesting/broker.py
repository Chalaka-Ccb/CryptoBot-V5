from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.enums.position import PositionSide
from core.enums.trade import ExitReason
from core.models.trade import Trade


@dataclass
class BacktestBroker:
    balance: float
    trade_counter: int = 0

    # One active trade per symbol.
    current_trades: dict[str, Trade] = field(default_factory=dict)

    def has_open_trade(self, symbol: str) -> bool:
        trade = self.current_trades.get(symbol)

        return (
            trade is not None
            and trade.is_open
        )

    def get_open_trade(self, symbol: str) -> Optional[Trade]:
        trade = self.current_trades.get(symbol)

        if trade is not None and trade.is_open:
            return trade

        return None

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
                f"Cannot open a new trade for {symbol} "
                f"while another trade is open."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than 0"
            )

        if entry_price <= 0:
            raise ValueError(
                "entry_price must be greater than 0"
            )

        self.trade_counter += 1

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
        )

        self.current_trades[symbol] = trade

        print()
        print("===== TRADE OPENED =====")
        print(f"Trade ID: {trade.trade_id}")
        print(f"Symbol: {trade.symbol}")
        print(f"Strategy: {trade.strategy}")
        print(f"Side: {trade.side}")
        print(f"Entry: {trade.entry_price}")
        print(f"Quantity: {trade.quantity}")
        print(f"Stop loss: {trade.stop_loss}")
        print(f"Take profit: {trade.take_profit}")
        print(f"Time: {trade.entry_time}")

        return trade

    def process_candle(
        self,
        symbol: str,
        candle,
    ) -> Optional[Trade]:

        trade = self.get_open_trade(symbol)

        if trade is None:
            return None

        if trade.side == PositionSide.LONG:

            if (
                trade.stop_loss is not None
                and candle.low <= trade.stop_loss
            ):
                return self.close_trade(
                    symbol=symbol,
                    exit_price=trade.stop_loss,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.STOP_LOSS,
                )

            if (
                trade.take_profit is not None
                and candle.high >= trade.take_profit
            ):
                return self.close_trade(
                    symbol=symbol,
                    exit_price=trade.take_profit,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.TAKE_PROFIT,
                )

        elif trade.side == PositionSide.SHORT:

            if (
                trade.stop_loss is not None
                and candle.high >= trade.stop_loss
            ):
                return self.close_trade(
                    symbol=symbol,
                    exit_price=trade.stop_loss,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.STOP_LOSS,
                )

            if (
                trade.take_profit is not None
                and candle.low <= trade.take_profit
            ):
                return self.close_trade(
                    symbol=symbol,
                    exit_price=trade.take_profit,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.TAKE_PROFIT,
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
            raise ValueError(
                f"There is no open trade for {symbol}."
            )

        trade.close(
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=exit_reason,
        )

        pnl = trade.net_pnl or 0.0

        self.balance += pnl

        print()
        print("===== TRADE CLOSED =====")
        print(f"Trade ID: {trade.trade_id}")
        print(f"Symbol: {trade.symbol}")
        print(f"Exit: {trade.exit_price}")
        print(f"Reason: {trade.exit_reason}")
        print(f"PnL: {pnl}")
        print(f"Balance: {self.balance}")

        return trade