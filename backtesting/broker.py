


from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from backtesting.result import BacktestTrade
from core.enums.position import PositionSide
from core.enums.trade import ExitReason
from core.models.trade import Trade


@dataclass
class BacktestBroker:
    balance: float
    trade_counter: int = 0
    current_trade: Optional[Trade] = None

    def has_open_trade(self) -> bool:
        return (
            self.current_trade is not None
            and self.current_trade.is_open
        )

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

        if self.has_open_trade():
            raise ValueError(
                "Cannot open a new trade while another trade is open."
            )

        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")

        if entry_price <= 0:
            raise ValueError("entry_price must be greater than 0")

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

        self.current_trade = trade

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

    def process_candle(self, candle) -> Optional[Trade]:

        trade = self.current_trade

        if trade is None or not trade.is_open:
            return None

        if trade.side == PositionSide.LONG:

            if (
                trade.stop_loss is not None
                and candle.low <= trade.stop_loss
            ):
                return self.close_trade(
                    exit_price=trade.stop_loss,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.STOP_LOSS,
                )

            if (
                trade.take_profit is not None
                and candle.high >= trade.take_profit
            ):
                return self.close_trade(
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
                    exit_price=trade.stop_loss,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.STOP_LOSS,
                )

            if (
                trade.take_profit is not None
                and candle.low <= trade.take_profit
            ):
                return self.close_trade(
                    exit_price=trade.take_profit,
                    exit_time=candle.timestamp,
                    exit_reason=ExitReason.TAKE_PROFIT,
                )

        return None

    def close_trade(
        self,
        exit_price: float,
        exit_time: datetime,
        exit_reason: ExitReason,
    ) -> Trade:

        trade = self.current_trade

        if trade is None or not trade.is_open:
            raise ValueError("There is no open trade.")

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
        print(f"Exit: {trade.exit_price}")
        print(f"Reason: {trade.exit_reason}")
        print(f"PnL: {pnl}")
        print(f"Balance: {self.balance}")

        return trade