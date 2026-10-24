
from dataclasses import dataclass
import csv
from pathlib import Path
from collections import Counter
from indicators.hilo_activator import calculate_hilo_activator, HiLoTrend
from datetime import timedelta
from types import SimpleNamespace

from backtesting.broker import BacktestBroker
from backtesting.execution import BacktestExecution
from backtesting.market_data import BacktestMarketData
from backtesting.result import BacktestResult, BacktestTrade

from core.enums.position import PositionSide
from core.enums.trade import ExitReason
from core.models.account import Account
from core.models.signal import EntryTiming
from engine.risk_manager import RiskManager
from engine.strategy_coordinator import StrategyCoordinator


@dataclass
class BacktestRunner:
    strategy_coordinator: StrategyCoordinator

    initial_balance: float = 10_000.0
    risk_percentage: float = 0.05
    default_risk_reward: float = 3.0
    default_stop_percentage: float = 0.01

    # Number of future 5m candles allowed for breakout.
    breakout_expiry_candles: int = 3
    diagnostic_csv: str | None = None

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

    def _manage_strategy_exit(
        self,
        broker,
        symbol,
        timeframe,
        closed_candles,
        trade_timeframes,
        timestamp,
    ):
        trade = broker.get_open_trade(symbol)

        if trade is None:
            return None

        if trade_timeframes.get(trade.trade_id) != timeframe:
            return None

        candles = closed_candles[timeframe]

        if not candles:
            return None

        index = len(candles) - 1

        strategies = (
            self.strategy_coordinator.strategies_15m
            if timeframe == "15m"
            else self.strategy_coordinator.strategies_5m
        )

        strategy = next(
            (
                item
                for item in strategies
                if getattr(item, "name", None) == trade.strategy
            ),
            None,
        )

        if strategy is None:
            raise ValueError(
                f"Strategy '{trade.strategy}' not registered "
                f"on {timeframe}"
            )

        if trade.side == PositionSide.LONG:
            exit_method = getattr(
                strategy, "should_exit_long", None
            )
        else:
            exit_method = getattr(
                strategy, "should_exit_short", None
            )

        if callable(exit_method):
            if exit_method(candles, index):
                return broker.close_trade(
                    symbol=symbol,
                    exit_price=candles[index].close,
                    exit_time=timestamp,
                    exit_reason=ExitReason.STRATEGY_EXIT,
                )

        trailing_method = getattr(
            strategy, "trailing_stop", None
        )

        if callable(trailing_method):
            new_stop = trailing_method(candles, index)

            if new_stop is not None:
                price = candles[index].close

                if (
                    trade.side == PositionSide.LONG
                    and 0 < new_stop < price
                ):
                    broker.update_stop_loss(symbol, new_stop)

                elif (
                    trade.side == PositionSide.SHORT
                    and new_stop > price
                ):
                    broker.update_stop_loss(symbol, new_stop)

        return None

    def run(
        self,
        market_data: BacktestMarketData,
    ) -> BacktestResult:

        if self.breakout_expiry_candles < 1:
            raise ValueError(
                "breakout_expiry_candles must be >= 1"
            )

        if not market_data.candles_5m:
            raise ValueError(
                "5m execution candles are required"
            )

        symbol = market_data.symbol

        broker = BacktestBroker(
            balance=self.initial_balance
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
            default_stop_percentage=self.default_stop_percentage,
        )

        closed_candles = {
            "15m": [],
            "5m": [],
        }

        # Index 15m candles by their closing time.
        fifteen_by_close = {
            candle.timestamp + timedelta(minutes=15): candle
            for candle in market_data.candles_15m
        }

        pending_entry = None
        pending_age = 0

        completed_trades = []
        trade_timeframes = {}

        signal_count = 0
        diagnostic_rows = []

        print("\n===== BACKTEST STARTED =====")
        print(f"Symbol: {symbol}")
        print(f"Start: {market_data.start_time}")
        print(f"End: {market_data.end_time}")
        print(f"5m execution candles: {len(market_data.candles_5m)}")
        print(f"Default SL: {self.default_stop_percentage * 100:.2f}%")
        print(f"Default RR: {self.default_risk_reward}:1")

        for candle in market_data.candles_5m:

            open_time = candle.timestamp
            close_time = open_time + timedelta(minutes=5)

            # -----------------------------------------
            # 1. FILL NEXT_OPEN AT 5M OPEN
            # -----------------------------------------

            entered_at_open = False

            if (
                pending_entry is not None
                and pending_entry.signal.entry_timing
                == EntryTiming.NEXT_OPEN
            ):
                if execution.can_enter(symbol):
                    trade = execution.execute_next_open(
                        pending=pending_entry,
                        candle=candle,
                    )

                    if trade is not None:
                        trade_timeframes[trade.trade_id] = (
                            pending_entry.timeframe
                        )
                        entered_at_open = True

                pending_entry = None
                pending_age = 0

            # -----------------------------------------
            # 2. PROCESS EXISTING POSITION
            # -----------------------------------------

            # An entry at this candle's open is exposed
            # to this candle's full high/low range.
            # An older trade is processed the same way.

            if broker.has_open_trade(symbol):

                closed_trade = broker.process_candle(
                    symbol=symbol,
                    candle=candle,
                )

                if closed_trade is not None:
                    completed_trades.append(closed_trade)

            # -----------------------------------------
            # 3. PROCESS PENDING BREAKOUT
            # -----------------------------------------

            if (
                pending_entry is not None
                and pending_entry.signal.entry_timing
                == EntryTiming.BREAKOUT
            ):

                pending_age += 1

                if execution.can_enter(symbol):

                    trade = execution.execute_breakout(
                        pending=pending_entry,
                        candle=candle,
                    )

                    if trade is not None:

                        trade_timeframes[trade.trade_id] = (
                            pending_entry.timeframe
                        )

                        # Conservative same-candle check.
                        #
                        # The entry may have occurred
                        # anywhere inside this 5m candle.
                        # We cannot know whether its low
                        # or high happened before entry.
                        #
                        # We assume an adverse stop touch
                        # happened after entry.
                        #
                        # Using entry_price as the synthetic
                        # open prevents the broker from
                        # interpreting pre-entry candle.open
                        # as a post-entry opening gap.

                        post_entry_candle = SimpleNamespace(
                            timestamp=close_time,
                            open=trade.entry_price,
                            high=candle.high,
                            low=candle.low,
                            close=candle.close,
                        )

                        closed_trade = broker.process_candle(
                            symbol=symbol,
                            candle=post_entry_candle,
                        )

                        if closed_trade is not None:
                            completed_trades.append(closed_trade)

                        pending_entry = None
                        pending_age = 0

                if (
                    pending_entry is not None
                    and pending_age >= self.breakout_expiry_candles
                ):
                    print("\n===== BREAKOUT EXPIRED =====")
                    print(
                        f"Strategy: {pending_entry.signal.strategy}"
                    )

                    pending_entry = None
                    pending_age = 0

            # -----------------------------------------
            # 4. CLOSE 5M CANDLE
            # -----------------------------------------

            closed_candles["5m"].append(candle)

            # -----------------------------------------
            # 5. CLOSE 15M CANDLE IF AVAILABLE
            # -----------------------------------------

            fifteen_closed = (
                fifteen_by_close.get(close_time)
            )

            if fifteen_closed is not None:
                closed_candles["15m"].append(
                    fifteen_closed
                )

            # -----------------------------------------
            # 6. STRATEGY EXITS
            # -----------------------------------------

            # 15m strategy exits first when a 15m
            # candle closes at this boundary.

            if fifteen_closed is not None:
                closed_trade = self._manage_strategy_exit(
                    broker=broker,
                    symbol=symbol,
                    timeframe="15m",
                    closed_candles=closed_candles,
                    trade_timeframes=trade_timeframes,
                    timestamp=close_time,
                )

                if closed_trade is not None:
                    completed_trades.append(closed_trade)

            # 5m strategy exits.
            closed_trade = self._manage_strategy_exit(
                broker=broker,
                symbol=symbol,
                timeframe="5m",
                closed_candles=closed_candles,
                trade_timeframes=trade_timeframes,
                timestamp=close_time,
            )

            if closed_trade is not None:
                completed_trades.append(closed_trade)

            # Diagnostics are sampled even while a position is open.
            # These rows are observations, NOT necessarily executable signals.
            if self.diagnostic_csv:
                for timeframe, ready in (("15m", fifteen_closed is not None), ("5m", True)):
                    if not ready:
                        continue
                    history = closed_candles[timeframe]
                    strategies = (
                        self.strategy_coordinator.strategies_15m if timeframe == "15m"
                        else self.strategy_coordinator.strategies_5m
                    )
                    for strategy in strategies:
                        if not hasattr(strategy, "diagnostic_row"):
                            continue
                        row = strategy.diagnostic_row(history, len(history) - 1)
                        row["timeframe"] = timeframe
                        row["strategy"] = strategy.name
                        row["evaluated_at"] = close_time.isoformat()
                        row["position_open"] = broker.has_open_trade(symbol)
                        row["pending_order"] = pending_entry is not None
                        row["htf_confirmation_enabled"] = (
                            timeframe == "5m" and self.strategy_coordinator.require_15m_hilo_for_5m
                        )
                        if timeframe == "5m" and closed_candles["15m"]:
                            htf = calculate_hilo_activator(
                                closed_candles["15m"],
                                period=self.strategy_coordinator.confirmation_hilo_period,
                            )[-1]
                            row["htf_hilo_trend"] = htf.trend.value if htf else None
                            row["htf_hilo_line"] = htf.line if htf else None
                            row["htf_pass"] = (
                                htf is not None and htf.trend == HiLoTrend.BULLISH
                                and closed_candles["15m"][-1].close > htf.line
                            )
                        else:
                            row["htf_hilo_trend"] = None
                            row["htf_hilo_line"] = None
                            row["htf_pass"] = None
                        row["htf_rejected"] = (
                            row["signal_candidate"] and row["htf_confirmation_enabled"]
                            and row["htf_pass"] is not True
                        )
                        diagnostic_rows.append(row)

            # -----------------------------------------
            # 7. ONE ORDER/POSITION PER SYMBOL
            # -----------------------------------------

            if broker.has_open_trade(symbol):
                continue

            if pending_entry is not None:
                continue

            # -----------------------------------------
            # 8. EVALUATE 15M FIRST, THEN 5M
            # -----------------------------------------

            evaluation = None

            if fifteen_closed is not None:
                evaluation = (
                    self.strategy_coordinator.evaluate(
                        candles_15m=closed_candles["15m"],
                        candles_5m=[],
                    )
                )

            if (
                evaluation is None
                or evaluation.signal is None
            ):
                evaluation = (
                    self.strategy_coordinator.evaluate_5m_with_15m_confirmation(
                        candles_5m=closed_candles["5m"],
                        closed_candles_15m=closed_candles["15m"],
                    )
                )

            signal = evaluation.signal

            if signal is None:
                continue

            signal_count += 1

            print("\n===== SIGNAL =====")
            print(f"Time: {close_time}")
            print(f"Timeframe: {evaluation.timeframe}")
            print(f"Strategy: {signal.strategy}")
            print(f"Side: {signal.side.value}")
            print(f"Entry timing: {signal.entry_timing.value}")
            print(f"Trigger: {signal.trigger_price}")
            print(f"SL: {signal.stop_loss}")
            print(f"TP: {signal.take_profit}")

            pending = execution.create_pending_entry(
                signal=signal,
                symbol=symbol,
                timeframe=evaluation.timeframe,
            )

            # -----------------------------------------
            # 9. ENTRY DECISION
            # -----------------------------------------

            if signal.entry_timing == EntryTiming.CURRENT_CLOSE:

                trade = execution.execute_current_close(
                    pending=pending,
                    candle=candle,
                )

                if trade is not None:
                    trade_timeframes[trade.trade_id] = (
                        evaluation.timeframe
                    )

            elif signal.entry_timing in (
                EntryTiming.NEXT_OPEN,
                EntryTiming.BREAKOUT,
            ):
                # This order becomes eligible on
                # the NEXT 5m execution candle.
                pending_entry = pending
                pending_age = 0

            else:
                print(
                    f"Unsupported entry timing: "
                    f"{signal.entry_timing}"
                )

        # -----------------------------------------
        # 10. FINAL RESULTS
        # -----------------------------------------

        if self.diagnostic_csv and diagnostic_rows:
            destination = Path(self.diagnostic_csv)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(diagnostic_rows[0].keys()), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(diagnostic_rows)
            failures = Counter()
            for row in diagnostic_rows:
                failures.update(row["failed_filters"].split("|") if row["failed_filters"] else [])
            print(f"Diagnostics CSV: {destination.resolve()}")
            print(f"Diagnostic candles: {len(diagnostic_rows)}")
            print(f"Raw entry candidates: {sum(bool(r['signal_candidate']) for r in diagnostic_rows)}")
            print(f"Rejected by 15m HiLo: {sum(bool(r['htf_rejected']) for r in diagnostic_rows)}")
            print(f"Filter failure counts (overlap allowed): {dict(failures)}")

        print("\n===== BACKTEST FINISHED =====")
        print(f"Signals: {signal_count}")
        print(f"Closed trades: {len(completed_trades)}")
        print(f"Final balance: {broker.balance:.2f}")

        open_trade = broker.get_open_trade(symbol)

        if open_trade is not None:
            print(
                f"Unrealized position excluded: "
                f"{open_trade.trade_id}"
            )

        return BacktestResult(
            symbol=symbol,
            initial_balance=self.initial_balance,
            final_balance=broker.balance,
            trades=[
                self._convert_trade(trade)
                for trade in completed_trades
            ],
        )
