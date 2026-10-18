"""Independent signal research: unlimited virtual positions, never used for live orders."""
from dataclasses import dataclass, field, replace
from datetime import timedelta
from types import SimpleNamespace
import csv
import json

from backtesting.fee_config import FeeConfig
from core.models.signal import EntryTiming, SignalSide
from engine.strategy_coordinator import StrategyCoordinator
from risk.limits import RiskLimits
from risk.position_sizing import calculate_position_size
from risk.risk_reward import calculate_take_profit, validate_levels


@dataclass
class ResearchTrade:
    trade_id: int
    strategy: str
    timeframe: str
    symbol: str
    side: str
    signal_time: object
    entry_time: object
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    reason: str
    diagnostics: dict
    exit_time: object = None
    exit_price: float | None = None
    exit_reason: str | None = None
    gross_pnl: float = 0.0
    fees: float = 0.0

    @property
    def net_pnl(self):
        return self.gross_pnl - self.fees


@dataclass
class ResearchResult:
    trades: list[ResearchTrade] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)
    unfilled: list[dict] = field(default_factory=list)

    def export(self, prefix="research"):
        rows = []
        for t in self.trades:
            row = vars(t).copy()
            row["diagnostics"] = json.dumps(row["diagnostics"], default=str)
            rows.append(row)
        if rows:
            with open(prefix + "_trades.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        with open(prefix + "_signals.json", "w", encoding="utf-8") as f:
            json.dump({"signals": self.signals, "unfilled": self.unfilled}, f, indent=2, default=str)


@dataclass
class ResearchRunner:
    strategy_coordinator: StrategyCoordinator
    reference_capital: float = 10000.0
    risk_percentage: float = 0.02
    leverage: float = 5.0
    default_stop_percentage: float = 0.01
    default_risk_reward: float = 3.0
    breakout_expiry_candles: int = 3
    fee_config: FeeConfig = field(default_factory=FeeConfig)
    timeframe: str = "5m"

    def run(self, market_data):
        if self.reference_capital <= 0 or not 0 < self.risk_percentage <= 1:
            raise ValueError("Invalid reference capital or risk")
        if not 0 < self.default_stop_percentage < 1 or self.breakout_expiry_candles < 1:
            raise ValueError("Invalid stop or expiry")
        RiskLimits(leverage=self.leverage)
        if self.timeframe not in ("1m", "5m", "15m"):
            raise ValueError("Unsupported research timeframe")
        result = ResearchResult()
        pending = []
        active = []
        closed = {"5m": [], "15m": []}
        if self.timeframe != "5m":
            closed = {self.timeframe: []}
        fifteen = {c.timestamp + timedelta(minutes=15): c for c in market_data.candles_15m}
        strategies = {"5m": self.strategy_coordinator.strategies_5m,
                      "15m": self.strategy_coordinator.strategies_15m}
        if self.timeframe != "5m":
            strategies = {self.timeframe: self.strategy_coordinator.strategies_5m}
        next_id = 0

        def fill(item, price, timestamp):
            nonlocal next_id
            signal = item["signal"]
            stop = signal.stop_loss
            if stop is None:
                stop = price * (1 - self.default_stop_percentage if signal.side == SignalSide.LONG
                                else 1 + self.default_stop_percentage)
            try:
                validate_levels(price, stop, signal.side, signal.take_profit)
                size = calculate_position_size(
                    self.reference_capital, self.risk_percentage, price, stop,
                    available_margin=self.reference_capital, leverage=self.leverage)
                target = (signal.take_profit if signal.take_profit is not None else
                          calculate_take_profit(price, stop, signal.side,
                                                self.default_risk_reward).take_profit)
                quantity = size.position_size
                if quantity <= 0:
                    raise ValueError("Zero quantity")
            except (ValueError, ArithmeticError) as exc:
                result.unfilled.append({**item["event"], "status": "rejected", "reason": str(exc)})
                return None
            next_id += 1
            trade = ResearchTrade(next_id, signal.strategy, item["timeframe"], market_data.symbol,
                                  signal.side.value, item["event"]["timestamp"], timestamp,
                                  price, quantity, stop, target, signal.reason,
                                  dict(getattr(signal, "diagnostics", {}) or {}),
                                  fees=price * quantity * self.fee_config.taker_rate)
            result.trades.append(trade)
            active.append(trade)
            item["event"]["status"] = "filled"
            item["event"]["trade_id"] = next_id
            return trade

        def close_trade(trade, price, timestamp, reason):
            trade.exit_price = price
            trade.exit_time = timestamp
            trade.exit_reason = reason
            direction = 1 if trade.side == "long" else -1
            trade.gross_pnl = (price - trade.entry_price) * direction * trade.quantity
            trade.fees += price * trade.quantity * self.fee_config.taker_rate
            active.remove(trade)

        def process(trade, candle, synthetic=False):
            stop, target = trade.stop_loss, trade.take_profit
            opening = trade.entry_price if synthetic else candle.open
            if trade.side == "long":
                if opening <= stop: price, why = opening, "stop_loss"
                elif opening >= target: price, why = opening, "take_profit"
                elif candle.low <= stop: price, why = stop, "stop_loss"
                elif candle.high >= target: price, why = target, "take_profit"
                else: return
            else:
                if opening >= stop: price, why = opening, "stop_loss"
                elif opening <= target: price, why = opening, "take_profit"
                elif candle.high >= stop: price, why = stop, "stop_loss"
                elif candle.low <= target: price, why = target, "take_profit"
                else: return
            close_trade(trade, price, candle.timestamp, why)

        step = timedelta(minutes=int(self.timeframe[:-1]))
        source = (market_data.candles_5m if self.timeframe == "5m"
                  else market_data.candles_15m if self.timeframe == "15m"
                  else getattr(market_data, "candles_" + self.timeframe))
        for candle in source:
            close_time = candle.timestamp + step
            for item in list(pending):
                if item["signal"].entry_timing == EntryTiming.NEXT_OPEN:
                    fill(item, candle.open, candle.timestamp)
                    pending.remove(item)
            for trade in list(active):
                process(trade, candle)
            for item in list(pending):
                signal = item["signal"]
                if signal.entry_timing != EntryTiming.BREAKOUT:
                    continue
                item["age"] += 1
                trigger = signal.trigger_price
                if trigger is not None and trigger > 0 and (
                    (signal.side == SignalSide.LONG and candle.high >= trigger) or
                    (signal.side == SignalSide.SHORT and candle.low <= trigger)
                ):
                    price = (max(candle.open, trigger) if signal.side == SignalSide.LONG
                             else min(candle.open, trigger))
                    trade = fill(item, price, candle.timestamp)
                    pending.remove(item)
                    if trade is not None:
                        process(trade, SimpleNamespace(timestamp=close_time, open=price,
                                                       high=candle.high, low=candle.low,
                                                       close=candle.close), synthetic=True)
                elif item["age"] >= self.breakout_expiry_candles:
                    item["event"]["status"] = "expired"
                    result.unfilled.append(item["event"])
                    pending.remove(item)

            closed["5m"].append(candle)
            fifteen_candle = fifteen.get(close_time) if self.timeframe == "5m" else None
            if fifteen_candle:
                closed["15m"].append(fifteen_candle)
            for timeframe in (("15m", "5m") if self.timeframe == "5m" else (self.timeframe,)):
                if timeframe == "15m" and self.timeframe == "5m" and not fifteen_candle:
                    continue
                if self.timeframe == "15m":
                    closed["15m"].append(candle)
                elif self.timeframe in ("1m",):
                    closed[timeframe].append(candle)
                candles = closed[timeframe]
                index = len(candles) - 1
                for trade in list(active):
                    if trade.timeframe != timeframe:
                        continue
                    strategy = next((s for s in strategies[timeframe]
                                     if s.name == trade.strategy), None)
                    if strategy is None:
                        continue
                    method = getattr(strategy, "should_exit_long" if trade.side == "long"
                                     else "should_exit_short", None)
                    if callable(method) and method(candles, index):
                        close_trade(trade, candles[-1].close, close_time, "strategy_exit")
                        continue
                    trailing = getattr(strategy, "trailing_stop", None)
                    if callable(trailing):
                        new_stop = trailing(candles, index)
                        if new_stop is not None:
                            if trade.side == "long" and trade.stop_loss < new_stop < candles[-1].close:
                                trade.stop_loss = new_stop
                            elif trade.side == "short" and candles[-1].close < new_stop < trade.stop_loss:
                                trade.stop_loss = new_stop
                for strategy in strategies[timeframe]:
                    signals = (strategy.generate_signals(candles, index) if hasattr(strategy, "generate_signals") else [strategy.generate_signal(candles, index)])
                    for signal in signals:
                        if signal is None:
                            continue
                        event = {"timestamp": close_time, "timeframe": timeframe,
                                 "strategy": signal.strategy, "side": signal.side.value,
                                 "reason": signal.reason,
                                 "diagnostics": dict(getattr(signal, "diagnostics", {}) or {}),
                                 "status": "pending"}
                        result.signals.append(event)
                        item = {"signal": signal, "timeframe": timeframe,
                                "event": event, "age": 0, "oco": (timeframe, strategy.name, close_time) if len(signals) > 1 else None}
                        if signal.entry_timing == EntryTiming.CURRENT_CLOSE:
                            fill(item, candle.close, close_time)
                        elif signal.entry_timing in (EntryTiming.NEXT_OPEN, EntryTiming.BREAKOUT):
                            pending.append(item)
                        else:
                            event["status"] = "unsupported"
                            result.unfilled.append(event)
            for item in pending:
            item["event"]["status"] = "end_of_data"
            result.unfilled.append(item["event"])
        return result
