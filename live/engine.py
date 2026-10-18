"""Closed-candle Channel Rebound engine, with restart-safe pending entries."""
import time
from datetime import timedelta, datetime, timezone
from core.models.signal import EntryTiming, TradingSignal, SignalSide
from backtesting.strategy_setup import create_strategy_coordinator
from live.sizing import size_trade
from live.ledger import closed_trade_record


class LiveEngine:
    def __init__(self, exchange, order_manager, recorder, state, controls, cfg):
        self.exchange, self.orders, self.recorder = exchange, order_manager, recorder
        self.store, self.controls, self.cfg = state, controls, cfg
        self.coordinator = create_strategy_coordinator()
        for strategies in (self.coordinator.strategies_15m, self.coordinator.strategies_5m):
            if len(strategies) != 1 or strategies[0].name != "bollinger_channel_rebound":
                raise RuntimeError("Only Channel Rebound may run in Live V1")
        self.state = self.store.load()
        saved_symbol = self.state.get("symbol")
        if saved_symbol and saved_symbol != cfg.symbol:
            raise RuntimeError("Saved live state belongs to another symbol; use a separate DATA_DIR")
        saved_trade = self.state.get("trade") or {}
        if saved_trade.get("symbol") and saved_trade["symbol"] != cfg.symbol:
            raise RuntimeError("Saved open trade belongs to another symbol")
        self.state["symbol"] = cfg.symbol
        self.store.save(self.state)
        self.running = True

    def stop(self):
        self.running = False

    def _save(self):
        self.store.save(self.state)

    def _daily_risk(self):
        balance = self.exchange.get_balance()
        day = datetime.now(timezone.utc).date().isoformat()
        stats = self.state.setdefault("stats", {})
        if stats.get("day") != day:
            stats.update(day=day, start_equity=balance.equity)
            self._save()
        start = float(stats["start_equity"])
        if start <= 0 or balance.equity <= 0:
            self.controls.lock("Invalid account equity")
            return False
        if (start - balance.equity) / start >= self.cfg.daily_drawdown_limit:
            self.controls.lock("Daily drawdown limit reached")
            self.recorder.event("daily_drawdown_lock", level="ERROR", equity=balance.equity, start=start)
            return False
        return True

    def _reconcile_position(self, position):
        saved = self.state.get("trade")
        if position is None:
            if saved:
                self.recorder.event("position_closed", reason="exchange_flat", side=saved.get("side"))
                try:
                    if not saved.get("ledger_written"):
                        record = closed_trade_record(saved, self.exchange.get_fills(saved.get("entry_ts")))
                        if record is None:
                            self.controls.lock("Closed trade fills or fees unresolved")
                            self.recorder.event("ledger_unresolved", level="ERROR")
                            return True
                        self.recorder.trade_closed(**record)
                        saved["ledger_written"] = True
                        self._save()
                except Exception as error:
                    self.controls.lock("Trade ledger reconciliation failed")
                    self.recorder.event("ledger_error", level="ERROR", error_type=type(error).__name__)
                    return True
                self.state["trade"] = None
                self._save()
            return False
        if not saved or saved.get("adopted"):
            self.controls.lock("Existing position needs manual protection reconciliation")
            self.recorder.event("position_adopted", level="ERROR", side=position.side, qty=position.qty)
            self.state["trade"] = {"adopted": True, "side": position.side, "qty": position.qty}
            self._save()
            return True
        if saved["side"] != position.side or abs(float(saved["qty"]) - position.qty) > 1e-8:
            self.controls.lock("Position differs from persisted state")
            return True
        # Re-check protection on every poll. A missing or unverifiable SL/TP
        # must never leave the engine free to open another position.
        if not self.orders.verify_saved_protection(saved, position):
            self.orders.kill_switch("Open position protection lost")
        return True

    def _expire_pending(self, candle):
        pending = self.state.get("pending")
        if not pending:
            return
        # Candle timestamp is OPEN time. Count completed 5m candles AFTER signal.
        created = datetime.fromisoformat(pending["created"])
        age = int((candle.timestamp - created).total_seconds() // 300)
        if age >= self.cfg.breakout_expiry_candles:
            self.recorder.event("pending_expired", age=age, side=pending["side"])
            self.state["pending"] = None
            self._save()

    def _pending_trigger(self):
        p = self.state.get("pending")
        if not p or self.controls.entries_blocked():
            return
        price = self.exchange.get_price()
        trigger = float(p["trigger"])
        crossed = price >= trigger if p["side"] == "long" else price <= trigger
        if not crossed:
            return
        deviation = (price - trigger) / trigger if p["side"] == "long" else (trigger - price) / trigger
        if deviation > self.cfg.max_entry_slippage:
            self.recorder.event("entry_skipped", reason="slippage", deviation=deviation)
            self.state["pending"] = None
            self._save()
            return
        signal = TradingSignal("bollinger_channel_rebound", SignalSide(p["side"]), 0,
                               EntryTiming.BREAKOUT, trigger, p["sl"], p["tp"])
        try:
            plan = size_trade(signal, p["timeframe"], price, self.exchange.get_balance(),
                              self.exchange.market_limits(), self.cfg)
        except ValueError as error:
            self.recorder.event("entry_skipped", reason=str(error))
            self.state["pending"] = None
            self._save()
            return
        # Persist an entry-in-flight marker before exchange side effects.
        entry_sent_at = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.state["pending"] = None
        self.state["entry_in_flight"] = True
        self._save()
        try:
            position = self.orders.open_trade(plan)
            if position is not None:
                self.state["trade"] = {"side": position.side, "qty": position.qty,
                                       "entry": position.entry, "sl": plan.sl, "tp": plan.tp,
                                       "entry_ts": entry_sent_at,
                                       "timeframe": plan.timeframe, "symbol": self.cfg.symbol}
        finally:
            self.state["entry_in_flight"] = False
            self._save()

    def tick(self):
        if self.controls.flatten_requested():
            self.orders.ensure_flat()
            return
        position = self.exchange.get_position()
        if self._reconcile_position(position):
            return
        if self.state.get("entry_in_flight"):
            self.controls.lock("Unresolved entry after restart; inspect Bitget orders")
            return
        if not self._daily_risk():
            return
        candles5 = self.exchange.get_candles("5m")
        if not candles5:
            return
        latest = candles5[-1]
        candle_id = latest.timestamp.isoformat()
        self._expire_pending(latest)
        if self.state.get("last_processed_candle") == candle_id:
            self._pending_trigger()
            return
        # New completed candle. Pending from the previous candle may have
        # triggered while the engine was offline; do not backfill fills.
        self.state["last_processed_candle"] = candle_id
        self._save()
        self._pending_trigger()
        if self.controls.entries_blocked() or self.state.get("pending") or self.state.get("trade"):
            return
        candles15 = self.exchange.get_candles("15m")
        close_time = latest.timestamp + timedelta(minutes=5)
        fifteen = bool(candles15 and candles15[-1].timestamp + timedelta(minutes=15) == close_time)
        evaluation = self.coordinator.evaluate(candles15 if fifteen else [], candles5)
        signal = evaluation.signal
        if signal is None:
            return
        if signal.entry_timing != EntryTiming.BREAKOUT or signal.strategy != "bollinger_channel_rebound":
            raise RuntimeError("Unexpected signal type")
        self.recorder.event("signal", timeframe=evaluation.timeframe, side=signal.side.value,
                            trigger=signal.trigger_price, sl=signal.stop_loss, tp=signal.take_profit)
        self.state["pending"] = {"side": signal.side.value, "timeframe": evaluation.timeframe,
                                  "trigger": signal.trigger_price, "sl": signal.stop_loss,
                                  "tp": signal.take_profit, "created": candle_id}
        self._save()

    def run(self):
        self.recorder.event("startup", symbol=self.cfg.symbol, demo=self.cfg.demo)
        errors = 0
        while self.running:
            try:
                self.tick()
                errors = 0
            except Exception as exc:
                errors += 1
                self.recorder.event("error", level="ERROR", error_type=type(exc).__name__)
                if errors >= 3:
                    self.controls.lock("Repeated live engine errors")
            time.sleep(min(60, self.cfg.poll_seconds * (2 ** min(errors, 4))))
        self.recorder.event("shutdown")
