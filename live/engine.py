"""Single live loop. Only completed candles generate signals."""
import time
from datetime import timedelta
from core.models.signal import EntryTiming
from backtesting.strategy_setup import create_strategy_coordinator
from live.sizing import size_trade


class LiveEngine:
    def __init__(self, exchange, order_manager, recorder, state, controls, cfg):
        self.exchange, self.orders, self.recorder = exchange, order_manager, recorder
        self.store, self.controls, self.cfg = state, controls, cfg
        self.coordinator = create_strategy_coordinator()
        for strategies in (self.coordinator.strategies_15m, self.coordinator.strategies_5m):
            if len(strategies) != 1 or strategies[0].name != "bollinger_channel_rebound":
                raise RuntimeError("Live V1 requires Channel Rebound exclusively")
        self.state = self.store.load()
        self.running = True

    def stop(self):
        self.running = False

    def tick(self):
        if self.controls.flatten_requested():
            self.orders.ensure_flat()
            return
        position = self.exchange.get_position()
        if position is not None:
            # Never place another entry while a position exists.
            if not self.state.get("trade"):
                self.recorder.event("position_adopted", side=position.side, qty=position.qty)
                self.state["trade"] = {"adopted": True}
                self.store.save(self.state)
            # Do not trade while protection status is unknown.
            self.recorder.event("protection_check", status="position_monitoring_requires_verified_plan")
            return
        if self.state.get("trade"):
            self.recorder.event("position_closed", reason="exchange_flat")
            self.state["trade"] = None
            self.store.save(self.state)
        candles5 = self.exchange.get_candles("5m")
        if not candles5:
            return
        latest = candles5[-1]
        candle_id = latest.timestamp.isoformat()
        last = self.state.get("last_processed_candle")
        if last == candle_id:
            self.check_pending()
            return
        # Process pending eligibility BEFORE evaluating signals from the new closed candle.
        self.check_pending()
        candles15 = self.exchange.get_candles("15m")
        self.state["last_processed_candle"] = candle_id
        self.store.save(self.state)
        self.recorder.event("candle_closed", timestamp=candle_id, close=latest.close)
        if self.controls.entries_blocked() or self.state.get("pending") or self.state.get("trade"):
            return
        # The 15m candle closes on the same boundary as the current 5m candle.
        close_time = latest.timestamp + timedelta(minutes=5)
        fifteen = bool(candles15 and candles15[-1].timestamp + timedelta(minutes=15) == close_time)
        evaluation = None
        if fifteen:
            evaluation = self.coordinator.evaluate(candles15, [])
        if evaluation is None or evaluation.signal is None:
            evaluation = self.coordinator.evaluate([], candles5)
        signal = evaluation.signal
        if signal is None:
            return
        self.recorder.event("signal", side=signal.side.value, timeframe=evaluation.timeframe,
                            trigger=signal.trigger_price, sl=signal.stop_loss, tp=signal.take_profit)
        if signal.entry_timing != EntryTiming.BREAKOUT:
            raise RuntimeError("Unexpected Channel Rebound entry timing")
        self.state["pending"] = {
            "side": signal.side.value, "timeframe": evaluation.timeframe,
            "trigger": signal.trigger_price, "sl": signal.stop_loss,
            "tp": signal.take_profit, "age": 0, "created": candle_id,
        }
        self.store.save(self.state)

    def check_pending(self):
        pending = self.state.get("pending")
        if not pending or self.controls.entries_blocked():
            return
        # Price polling cannot recreate historical intrabar high/low; use a
        # live trigger and never fill retrospectively.
        price = self.exchange.get_price()
        triggered = (price >= pending["trigger"] if pending["side"] == "long"
                     else price <= pending["trigger"])
        if not triggered:
            return
        trigger = pending["trigger"]
        deviation = ((price - trigger) / trigger if pending["side"] == "long"
                     else (trigger - price) / trigger)
        if deviation > self.cfg.max_entry_slippage:
            self.recorder.event("entry_skipped", reason="slippage", deviation=deviation)
            self.state["pending"] = None
            self.store.save(self.state)
            return
        from core.models.signal import TradingSignal, SignalSide
        signal = TradingSignal("bollinger_channel_rebound", SignalSide(pending["side"]),
                               0, EntryTiming.BREAKOUT, trigger, pending["sl"], pending["tp"])
        try:
            plan = size_trade(signal, pending["timeframe"], price,
                              self.exchange.get_balance(), self.exchange.market_limits(), self.cfg)
            self.state["pending"] = None
            self.store.save(self.state)
            position = self.orders.open_trade(plan)
            if position is not None:
                self.state["trade"] = {"side": position.side, "qty": position.qty,
                                       "entry": position.entry, "sl": plan.sl, "tp": plan.tp}
                self.store.save(self.state)
        except ValueError as exc:
            self.recorder.event("entry_skipped", reason=str(exc))
            self.state["pending"] = None
            self.store.save(self.state)

    def run(self):
        self.recorder.event("startup", symbol=self.cfg.symbol, demo=self.cfg.demo)
        errors = 0
        while self.running:
            try:
                self.tick()
                errors = 0
            except Exception as exc:
                errors += 1
                self.recorder.event("error", level="ERROR", error_type=type(exc).__name__,
                                    message=str(exc))
            time.sleep(min(60, self.cfg.poll_seconds * (2 ** min(errors, 4))))
        self.recorder.event("shutdown")
