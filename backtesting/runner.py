from dataclasses import dataclass
from datetime import datetime
from engine.risk_manager import RiskManager
from backtesting.broker import BacktestBroker
from core.enums.position import PositionSide
from backtesting.context import build_context
from backtesting.market_data import BacktestMarketData
from backtesting.result import BacktestResult
from core.models.candle import Candle
from engine.strategy_coordinator import StrategyCoordinator
from core.models.account import Account
from backtesting.broker import BacktestBroker
from backtesting.execution import BacktestExecution
from core.models.account import Account
from engine.risk_manager import RiskManager
from backtesting.result import BacktestTrade

@dataclass
@dataclass
class BacktestRunner:
    strategy_coordinator: StrategyCoordinator
    initial_balance: float = 10_000.0
    risk_percentage: float = 0.02
    default_risk_reward: float = 3.0

    def _create_account(self) -> Account:
        return Account(
            account_id="BACKTEST",
            currency="USDT",
            initial_balance=self.initial_balance,
            balance=self.initial_balance,
        )

    @staticmethod
    def _convert_trade(trade) -> BacktestTrade:

        return BacktestTrade(
            symbol=trade.symbol,
            strategy=trade.strategy or "unknown",
            side=trade.side.value,
            entry_time=trade.entry_time,
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            exit_time=trade.exit_time,
            exit_price=trade.exit_price,
            exit_reason=(
                trade.exit_reason.value
                if trade.exit_reason is not None
                else None
            ),
            pnl=trade.net_pnl or 0.0,
        )

    def run(
        self,
        market_data: BacktestMarketData,

    ) -> BacktestResult:

        broker = BacktestBroker(
            balance=self.initial_balance,
        )

        account = Account(
            account_id="BACKTEST",
            currency="USDT",
            initial_balance=self.initial_balance,
            balance=self.initial_balance,
        )

        risk_manager = RiskManager(
            account=account,
            risk_percentage=self.risk_percentage,
            default_risk_reward=self.default_risk_reward,
        )

        execution = BacktestExecution(
            broker=broker,
            risk_manager=risk_manager,
        )
        pending_entry = None
        completed_trades = []

        print()
        print("===== BACKTEST STARTED =====")

        print(
            f"Symbol: {market_data.symbol}"
        )

        print(
            f"Start: {market_data.start_time}"
        )

        print(
            f"End:   {market_data.end_time}"
        )

        timeline = self._build_timeline(
            market_data
        )

        print(
            f"Timeline events: {len(timeline)}"
        )

        signal_count = 0

        for timestamp, timeframe, candle in timeline:


            context = build_context(
                candles_15m=market_data.candles_15m,
                candles_5m=market_data.candles_5m,
                current_timestamp=timestamp,
            )
            if timeframe == "15m":

                evaluation = self.strategy_coordinator.evaluate(
                    candles_15m=context.candles_15m,
                    candles_5m=[],
                )

            else:

                evaluation = self.strategy_coordinator.evaluate(
                    candles_15m=[],
                    candles_5m=context.candles_5m,
                )

            evaluation = (
                self.strategy_coordinator.evaluate(
                    candles_15m=context.candles_15m,
                    candles_5m=context.candles_5m,
                )
            )
            if pending_entry is not None:

                if pending_entry.timeframe == timeframe:

                    if execution.can_enter(pending_entry.symbol):

                        trade = execution.execute_next_open(
                            pending=pending_entry,
                            candle=candle,
                        )

                        if trade is not None:
                            print(
                                f"Trade entered at "
                                f"{trade.entry_price} "
                                f"on {trade.entry_time}"
                            )

                    else:
                        print()
                        print("===== SIGNAL IGNORED =====")
                        print(
                            f"Symbol already has an active trade: "
                            f"{pending_entry.symbol}"
                        )

                    pending_entry = None

                    if trade is not None:
                        print(
                            f"Trade entered at {trade.entry_price} "
                            f"on {trade.entry_time}"
                        )
            closed_trade = broker.process_candle(candle)

            if closed_trade is not None:
                completed_trades.append(closed_trade)

            if evaluation.signal is not None:

                signal_count += 1

                signal = evaluation.signal

                print()
                print("===== SIGNAL =====")
                print(f"Timeframe: {evaluation.timeframe}")
                print(f"Strategy: {signal.strategy}")
                print(f"Side: {signal.side}")
                print(f"Candle: {signal.candle_index}")
                print(f"Entry timing: {signal.entry_timing}")
                print(f"Trigger: {signal.trigger_price}")
                print(f"Stop loss: {signal.stop_loss}")
                print(f"Take profit: {signal.take_profit}")
                print(f"Reason: {signal.reason}")

                if signal.entry_timing.value == "next_open":
                    pending_entry = execution.create_pending_entry(
                        signal=signal,
                        symbol=market_data.symbol,
                        timeframe=evaluation.timeframe,
                    )

        print()
        print("===== BACKTEST FINISHED =====")

        print(
            f"Signals found: {signal_count}"
        )

        return BacktestResult(
            symbol=market_data.symbol,
            initial_balance=self.initial_balance,
            final_balance=broker.balance,
            trades=[
                self._convert_trade(trade)
                for trade in completed_trades
            ],
        )


    @staticmethod
    def _build_timeline(
        market_data: BacktestMarketData,
    ) -> list[
        tuple[datetime, str, Candle]
    ]:

        timeline = []

        for candle in market_data.candles_15m:

            timeline.append(
                (
                    candle.timestamp,
                    "15m",
                    candle,
                )
            )

        for candle in market_data.candles_5m:

            timeline.append(
                (
                    candle.timestamp,
                    "5m",
                    candle,
                )
            )

        timeframe_priority = {
            "15m": 0,
            "5m": 1,
        }

        timeline.sort(
            key=lambda event: (
                event[0],
                timeframe_priority[event[1]],
            )
        )

        return timeline