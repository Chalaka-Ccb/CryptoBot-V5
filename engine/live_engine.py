"""Polling live execution using the existing strategies and risk calculations."""
import hashlib
import json
import logging
import math
import os
import signal
import threading
import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from backtesting.execution import BacktestExecution
from backtesting.runner import BacktestRunner
from brokers.live_broker import LiveBroker
from core.enums.order import OrderSide, OrderStatus, OrderType
from core.enums.position import PositionSide
from core.enums.trade import ExitReason
from core.models.account import Account
from core.models.order import Order
from core.models.signal import EntryTiming
from engine.live_config import LiveConfig
from engine.risk_manager import RiskManager
from risk.daily_drawdown import DailyDrawdownGuard
from risk.limits import RiskLimits

log = logging.getLogger(__name__)


class LiveJournal:
    """Atomic intent journal with an OS lock held for the runner's lifetime."""
    def __init__(self, path, identity):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = open(str(self.path) + ".lock", "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.lock.seek(0)
                self.lock.write(b"0")
                self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.data = json.loads(self.path.read_text()) if self.path.exists() else {
                "identity": identity, "seen": {}, "orders": {}, "day": None,
                "day_equity": None, "drawdown_triggered": False,
            }
            if self.data["identity"] != identity:
                raise ValueError("Journal belongs to a different exchange, mode, or API account")
            for name, default in (("positions", {}), ("history", {}), ("trades", [])):
                self.data.setdefault(name, default)
        except Exception:
            self.lock.close()
            raise

    def save(self):
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w") as output:
            json.dump(self.data, output, indent=2, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)

    def close(self):
        self.lock.close()


class LiveEngine:
    def __init__(self, config, coordinator, broker=None):
        self.config = config
        self.coordinator = coordinator
        self.broker = broker or LiveBroker(config)
        fingerprint = hashlib.sha256(os.getenv(f"{config.exchange.upper()}_API_KEY", "injected-client").encode()).hexdigest()
        self.journal = LiveJournal(config.journal, f"{config.exchange}:{config.sandbox}:{fingerprint}")
        self.account = None
        self.configured = set()
        self.live_positions = {}
        self.open_orders = []
        self.stop_requested = threading.Event()
        self.exit_runner = BacktestRunner(coordinator)
        self.exit_broker = LivePositionAdapter(self)
        # Restore the growing candle series so EMA/ATR seeds survive restarts.
        for key, rows in self.journal.data["history"].items():
            symbol, timeframe = key.rsplit("|", 1)
            self.broker.history[(symbol, timeframe)] = {r[0]: r for r in rows}

    def initialize(self):
        self.broker.initialize()
        for strategies in (self.coordinator.strategies_15m, self.coordinator.strategies_5m):
            for strategy in strategies:
                if not callable(getattr(strategy, "generate_signal", None)):
                    raise ValueError(f"{strategy.name} is unsupported by the existing backtest coordinator")
        self.reconcile()

    @staticmethod
    def _number(value, label):
        value = float(value)
        if not math.isfinite(value):
            raise RuntimeError(f"Invalid exchange {label}")
        return value

    def reconcile(self):
        balance, positions, orders = self.broker.snapshot()
        funds = balance.get("USDT", {})
        equity = self._number(funds.get("total"), "wallet balance")
        if self.config.exchange == "bitget":
            # Classic Bitget reports accountEquity including unrealized PnL.
            raw = balance.get("info", {}).get("data", [])
            if isinstance(raw, list):
                for entry in raw:
                    if entry.get("marginCoin") == "USDT" and entry.get("unrealizedPL") is not None:
                        equity -= self._number(entry["unrealizedPL"], "unrealized PnL")
        free = self._number(funds.get("free"), "free balance")
        used = self._number(funds.get("used"), "used margin")
        if equity <= 0 or free < 0 or used < 0:
            raise RuntimeError("Exchange account has insufficient or invalid funds")
        if self.account is None:
            self.account = Account("live", "USDT", equity, equity)
        # CCXT total is treated conservatively as the sizing/drawdown capital.
        self.account.balance = equity
        self.account.available_balance = free
        self.account.used_margin = used
        busy = {p["symbol"] for p in positions if self._number(p.get("contracts", 0), "position size") != 0}
        busy.update(o["symbol"] for o in orders)
        for client_id, record in list(self.journal.data["orders"].items()):
            busy.add(record["symbol"])
            if not record.get("exchange_order_id"):
                matches = [o for o in orders if o.get("clientOrderId") == client_id]
                if len(matches) != 1:
                    raise RuntimeError(f"Uncertain submission {client_id}: inspect exchange and journal before resuming")
                record["exchange_order_id"] = matches[0]["id"]
                self.journal.save()
            order = self._restore_order(record)
            self.broker.orders[client_id] = order
            self.broker.fetch_order(order)
            record.update(self._record_order(order))
            if record.get("action", "entry") == "entry" and order.filled_quantity > 0:
                if not record.get("timeframe") or record.get("stop_loss") is None:
                    raise RuntimeError("Legacy entry lacks strategy metadata; reconcile it before enabling this runner")
                owned = self.journal.data["positions"].setdefault(order.symbol, {
                    "symbol": order.symbol, "trade_id": client_id, "strategy": order.strategy,
                    "timeframe": record["timeframe"], "side": order.side.value,
                    "quantity": order.filled_quantity, "entry_price": order.average_fill_price or order.price,
                    "stop_loss": record["stop_loss"], "take_profit": record["take_profit"],
                    "confirmed": False, "closing": False,
                })
                owned["quantity"] = order.filled_quantity
            if not order.is_active:
                del self.journal.data["orders"][client_id]
                if record.get("action") == "exit" and order.symbol in self.journal.data["positions"]:
                    owned = self.journal.data["positions"][order.symbol]
                    owned["closing"] = False
                    owned["exit_price"] = order.average_fill_price
                    owned["exit_reason"] = record["exit_reason"]
            self.journal.save()
        # Refresh after querying fills to avoid managing pre-fill quantities.
        positions = self.broker.exchange.fetch_positions(list(self.config.symbols))
        self.live_positions = {p["symbol"]: p for p in positions if self._number(p.get("contracts", 0), "position size") != 0}
        self.open_orders = orders
        for symbol, owned in list(self.journal.data["positions"].items()):
            busy.add(symbol)
            actual = self.live_positions.get(symbol)
            if actual is not None:
                expected = "long" if owned["side"] == "buy" else "short"
                if actual.get("side") != expected or actual.get("hedged"):
                    raise RuntimeError(f"Unexpected position side/mode for managed {symbol}")
                owned["confirmed"] = True
                owned["quantity"] = float(actual["contracts"]) * float(self.broker.exchange.market(symbol).get("contractSize") or 1)
                owned["entry_price"] = actual.get("entryPrice") or owned["entry_price"]
                owned["missing"] = 0
            elif owned["confirmed"] and not any(r["symbol"] == symbol for r in self.journal.data["orders"].values()):
                owned["missing"] = owned.get("missing", 0) + 1
                if owned["missing"] >= 2:
                    owned["closed_at"] = datetime.now(timezone.utc).isoformat()
                    self.journal.data["trades"].append(owned)
                    del self.journal.data["positions"][symbol]
        busy.update(self.live_positions)
        self.journal.save()
        return busy

    @staticmethod
    def _record_order(order):
        return {"order_id": order.order_id, "symbol": order.symbol,
                "side": order.side.value, "order_type": order.order_type.value,
                "quantity": order.quantity, "created_at": order.created_at.isoformat(),
                "price": order.price, "stop_price": order.stop_price,
                "exchange_order_id": order.exchange_order_id,
                "strategy": order.strategy, "reason": order.reason}

    @staticmethod
    def _restore_order(record):
        values = {k: v for k, v in record.items() if k in Order.__dataclass_fields__}
        values["created_at"] = datetime.fromisoformat(values["created_at"])
        values["side"] = OrderSide(values["side"])
        values["order_type"] = OrderType(values["order_type"])
        return Order(**values)

    def _drawdown(self, now):
        if not self.config.drawdown_enabled:
            return False
        data = self.journal.data
        day = now.date().isoformat()
        if data["day"] != day:
            data.update(day=day, day_equity=self.account.equity, drawdown_triggered=False)
        guard = DailyDrawdownGuard(self.config.drawdown_percentage)
        guard.update(data["day_equity"], now.date())
        status = guard.update(self.account.equity, now.date())
        data["drawdown_triggered"] = data["drawdown_triggered"] or status.triggered
        self.journal.save()
        return data["drawdown_triggered"]

    def _submit(self, order, request, metadata):
        record = self._record_order(order) | metadata
        self.journal.data["orders"][order.order_id] = record
        self.journal.save()
        self.broker.submit_prepared(order, request)
        record.update(self._record_order(order))
        self.journal.save()
        log.info("Submitted %s %s %s (%s)", metadata["action"], order.symbol, order.side.value, order.exchange_order_id)
        return order

    def _expire_breakouts(self, now):
        for client_id, record in list(self.journal.data["orders"].items()):
            if not record.get("expires_at") or now < datetime.fromisoformat(record["expires_at"]):
                continue
            if not self.config.enabled:
                log.warning("Expired live breakout %s needs cancellation; trading disabled", client_id)
                continue
            # A fill/cancel race is resolved by cancel_order fetching final state.
            self.broker.cancel_order(client_id)
            log.info("Cancelled expired breakout %s", client_id)
        self.reconcile()

    def _close_managed(self, symbol, reference, reason):
        if not self.config.enabled:
            return None
        for client_id, record in list(self.journal.data["orders"].items()):
            if record["symbol"] == symbol and record.get("action", "entry") == "entry":
                self.broker.cancel_order(client_id)
        self.reconcile()
        position = self.journal.data["positions"].get(symbol)
        if position is None or symbol not in self.live_positions or position["closing"]:
            return None
        order = Order("LIVE-" + uuid4().hex[:28], symbol,
                      OrderSide.SELL if position["side"] == "buy" else OrderSide.BUY,
                      OrderType.MARKET, position["quantity"], datetime.now(timezone.utc),
                      price=reference, strategy=position["strategy"], reason=reason.value)
        request = self.broker.prepare(order, reduce_only=True)
        position["closing"] = True
        return self._submit(order, request, {"action": "exit", "exit_reason": reason.value})

    def _manage_position(self, symbol, c15, c5, new15, boundary):
        position = self.journal.data["positions"].get(symbol)
        if not position or position["closing"] or symbol not in self.live_positions:
            return
        timeframe = position["timeframe"]
        if timeframe == "15m" and not new15:
            return
        # Use the exact backtest exit/trailing policy with a live broker adapter.
        self.exit_runner._manage_strategy_exit(
            self.exit_broker, symbol, timeframe, {"15m": c15, "5m": c5},
            {position["trade_id"]: timeframe}, boundary)

    def _enter(self, symbol, evaluation, c5, boundary, now):
        signal = evaluation.signal
        breakout = signal.entry_timing == EntryTiming.BREAKOUT
        if breakout:
            entry = signal.trigger_price
        elif signal.entry_timing == EntryTiming.NEXT_OPEN:
            entry = self.broker.next_open(symbol, boundary)
        elif signal.entry_timing == EntryTiming.CURRENT_CLOSE:
            # BacktestExecution uses the execution 5m candle close for both TFs.
            entry = c5[-1].close
        else:
            raise ValueError(f"Unsupported entry timing: {signal.entry_timing}")
        risk = RiskManager(self.account, self.config.risk_percentage, self.config.default_risk_reward,
                           limits=RiskLimits(leverage=self.config.leverage))
        preparation = BacktestExecution(None, risk, self.config.default_stop_percentage)
        signal = preparation.prepare_signal(signal, entry)
        decision = risk.evaluate(signal, entry, symbol=symbol)
        if not decision.approved:
            log.info("%s risk rejected: %s", symbol, decision.reason)
            return None
        order = Order("LIVE-" + uuid4().hex[:28], symbol,
                      OrderSide.BUY if signal.side.value == "long" else OrderSide.SELL,
                      OrderType.STOP if breakout else OrderType.MARKET,
                      decision.position_size.position_size, now, price=entry,
                      stop_price=entry if breakout else None, strategy=signal.strategy, reason=signal.reason)
        try:
            request = self.broker.prepare(order, signal.stop_loss, decision.risk_reward.take_profit)
        except ValueError as error:
            log.info("%s exchange sizing rejected: %s", symbol, error)
            return None
        if not self.config.enabled:
            log.info("Trading disabled; validated %s %s entry", symbol, order.side.value)
            return None
        if symbol not in self.configured:
            self.broker.configure_symbol(symbol)
            self.configured.add(symbol)
        return self._submit(order, request, {
            "action": "entry", "timeframe": evaluation.timeframe,
            "stop_loss": request[5]["stopLoss"]["triggerPrice"],
            "take_profit": request[5]["takeProfit"]["triggerPrice"],
            "expires_at": (boundary + timedelta(minutes=5 * self.config.breakout_expiry_candles)).isoformat() if breakout else None,
        })

    def run_once(self, now=None):
        now = now or datetime.now(timezone.utc)
        self.reconcile()
        self._expire_breakouts(now)
        entries_suspended = self._drawdown(now)
        submitted = []
        for symbol in self.config.symbols:
            c15 = self.broker.candles(symbol, "15m", now)
            c5 = self.broker.candles(symbol, "5m", now)
            marker = c5[-1].timestamp.isoformat()
            if self.journal.data["seen"].get(symbol) == marker:
                continue
            boundary = c5[-1].timestamp + timedelta(minutes=5)
            key15 = symbol + ":15m"
            marker15 = c15[-1].timestamp.isoformat()
            new15 = self.journal.data["seen"].get(key15) != marker15 and c15[-1].timestamp + timedelta(minutes=15) == boundary
            # Manage exposure even if entries are disabled by a drawdown latch.
            self._manage_position(symbol, c15, c5, new15, boundary)
            busy = self.reconcile()
            self.journal.data["seen"].update({symbol: marker, key15: marker15})
            for timeframe, candles in (("15m", c15), ("5m", c5)):
                self.journal.data["history"][symbol + "|" + timeframe] = [
                    [int(c.timestamp.timestamp() * 1000), c.open, c.high, c.low, c.close, c.volume] for c in candles]
            self.journal.save()
            if symbol in busy or entries_suspended:
                continue
            # Do not trade missed historical signals after a stalled feed.
            if now - boundary >= timedelta(minutes=5):
                continue
            evaluation = self.coordinator.evaluate(c15 if new15 else [], c5)
            if evaluation.signal is not None:
                order = self._enter(symbol, evaluation, c5, boundary, now)
                if order:
                    submitted.append(order)
        return submitted

    def run(self):
        try:
            self.initialize()
            while not self.stop_requested.is_set():
                self.run_once()
                self.stop_requested.wait(self.config.poll_seconds)
        finally:
            self.close()

    def close(self):
        self.journal.close()


class LivePositionAdapter:
    """Broker operations required by BacktestRunner's strategy-exit policy."""
    def __init__(self, engine):
        self.engine = engine

    def get_open_trade(self, symbol):
        position = self.engine.journal.data["positions"].get(symbol)
        if not position or symbol not in self.engine.live_positions:
            return None
        return SimpleNamespace(trade_id=position["trade_id"], strategy=position["strategy"],
                               side=PositionSide.LONG if position["side"] == "buy" else PositionSide.SHORT)

    def close_trade(self, symbol, exit_price, exit_time, exit_reason):
        return self.engine._close_managed(symbol, exit_price, exit_reason)

    def update_stop_loss(self, symbol, new_stop):
        position = self.engine.journal.data["positions"][symbol]
        old_stop = position["stop_loss"]
        if position["side"] == "buy" and new_stop <= old_stop:
            return
        if position["side"] == "sell" and new_stop >= old_stop:
            return
        if not self.engine.config.enabled:
            return
        position["stop_loss"] = self.engine.broker.update_stop_loss(position, new_stop)
        self.engine.journal.save()


def main():
    # Reuse the existing configured strategy list without changing any strategy.
    from backtesting.strategy_setup import create_strategy_coordinator
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="FFFD live USDT perpetual trading")
    parser.add_argument("--check", action="store_true", help="Validate credentials, funds and candle feeds without placing orders")
    args = parser.parse_args()
    config = LiveConfig.from_env()
    if config.history < 200:
        raise ValueError("FFFD EMA-200 requires LIVE_HISTORY >= 200")
    coordinator = create_strategy_coordinator()
    if any(s.name != "fffd" for s in coordinator.strategies_15m + coordinator.strategies_5m):
        raise ValueError("This live deployment supports only FFFD")
    engine = LiveEngine(replace(config, enabled=False) if args.check else config, coordinator)
    signal.signal(signal.SIGTERM, lambda *_: engine.stop_requested.set())
    log.info("FFFD exchange=%s sandbox=%s enabled=%s symbols=%s", config.exchange, config.sandbox, engine.config.enabled, config.symbols)
    try:
        if args.check:
            try:
                engine.initialize()
                now = datetime.now(timezone.utc)
                for symbol in config.symbols:
                    for timeframe in ("15m", "5m"):
                        candles = engine.broker.candles(symbol, timeframe, now)
                        if len(candles) < 200:
                            raise RuntimeError(f"Insufficient FFFD warmup: {symbol} {timeframe}")
                log.info("Preflight passed: account, markets and closed candle feeds available")
            finally:
                engine.close()
        else:
            engine.run()
    except KeyboardInterrupt:
        log.info("Stopped. Exchange orders and protection remain active.")


if __name__ == "__main__":
    main()
