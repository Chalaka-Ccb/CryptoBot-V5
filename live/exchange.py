"""Bitget CCXT gateway. All exchange I/O is isolated here."""
import time
from datetime import datetime, timezone
import ccxt
from core.models.candle import Candle
from live.models import Balance, Position
from risk.limits import QuantityLimits


class BitgetExchange:
    def __init__(self, cfg, recorder, client=None):
        self.cfg, self.recorder = cfg, recorder
        self.client = client or ccxt.bitget({
            "apiKey": cfg.api_key, "secret": cfg.api_secret,
            "password": cfg.api_passphrase,
            "enableRateLimit": True,
            "timeout": 15000,
            "options": {"defaultType": "swap"},
        })
        if cfg.demo and client is None:
            self.client.set_sandbox_mode(True)
        self.markets_loaded = False

    def _call(self, name, *args, retry=False, **kwargs):
        attempts = 3 if retry else 1
        for attempt in range(attempts):
            try:
                result = getattr(self.client, name)(*args, **kwargs)
                self.recorder.order_call(name, status="ok", symbol=self.cfg.symbol)
                return result
            except Exception as exc:
                self.recorder.order_call(name, status="error", error_type=type(exc).__name__,
                                         symbol=self.cfg.symbol)
                if attempt + 1 == attempts:
                    raise
                time.sleep(min(2 ** attempt, 4))

    def load_markets(self):
        markets = self._call("load_markets", retry=True)
        if self.cfg.symbol not in markets:
            raise ValueError("Configured symbol is unavailable on this Bitget account")
        self.markets_loaded = True
        return markets[self.cfg.symbol]

    def setup_account(self):
        # Do not mutate account settings if an existing position is present.
        if self.get_position() is not None:
            self.recorder.event("account_setup_skipped", reason="existing_position")
            return
        for name, args in (
            ("set_position_mode", (False, self.cfg.symbol)),
            ("set_margin_mode", (self.cfg.margin_mode, self.cfg.symbol)),
            ("set_leverage", (self.cfg.leverage, self.cfg.symbol)),
        ):
            self._call(name, *args)
        self.recorder.event("account_setup", leverage=self.cfg.leverage, margin=self.cfg.margin_mode)

    def get_candles(self, timeframe, limit=500):
        if timeframe not in ("5m", "15m"):
            raise ValueError("Unsupported timeframe")
        rows = self._call("fetch_ohlcv", self.cfg.symbol, timeframe, None, limit, retry=True)
        now_ms = self.client.milliseconds()
        duration_ms = (300000 if timeframe == "5m" else 900000)
        return [Candle(datetime.fromtimestamp(row[0] / 1000, timezone.utc),
                       float(row[1]), float(row[2]), float(row[3]),
                       float(row[4]), float(row[5]))
                for row in rows if row[0] + duration_ms <= now_ms - 3000]

    def get_price(self):
        ticker = self._call("fetch_ticker", self.cfg.symbol, retry=True)
        price = ticker.get("last")
        if price is None or float(price) <= 0:
            raise RuntimeError("Missing live price")
        return float(price)

    def get_balance(self):
        data = self._call("fetch_balance", {"type": "swap"}, retry=True)
        usdt = data.get("USDT") or {}
        equity = usdt.get("total")
        available = usdt.get("free")
        if equity is None or available is None:
            raise RuntimeError("Bitget did not provide USDT equity/free margin")
        return Balance(float(equity), float(available))

    def get_position(self):
        positions = self._call("fetch_positions", [self.cfg.symbol], retry=True)
        active = [p for p in positions if float(p.get("contracts") or 0) > 0]
        if len(active) > 1:
            raise RuntimeError("Multiple positions detected: one-way mode required")
        if not active:
            return None
        p = active[0]
        return Position(p["side"], float(p["contracts"]),
                        float(p.get("entryPrice") or 0),
                        float(p["liquidationPrice"]) if p.get("liquidationPrice") else None)

    def market_limits(self):
        if not self.markets_loaded:
            self.load_markets()
        m = self.client.market(self.cfg.symbol)
        amount = m.get("limits", {}).get("amount", {})
        cost = m.get("limits", {}).get("cost", {})
        precision = m.get("precision", {}).get("amount")
        step = float(10 ** -precision) if isinstance(precision, int) and precision >= 0 else (
            float(precision) if precision is not None and float(precision) < 1 else None)
        return QuantityLimits(minimum=amount.get("min"), maximum=amount.get("max"),
                              step=step, min_notional=cost.get("min"))

    def get_protection(self):
        # Fail closed if Bitget's plan-order endpoint is unsupported.
        return self._call("fetch_open_orders", self.cfg.symbol, None, None,
                          {"trigger": True, "planType": "profit_loss"}, retry=True)

    def place_entry(self, plan):
        self.cfg.require_trading_confirmation()
        side = "buy" if plan.side == "long" else "sell"
        params = {"marginMode": self.cfg.margin_mode, "hedged": False,
                  "stopLoss": {"triggerPrice": plan.sl},
                  "takeProfit": {"triggerPrice": plan.tp},
                  "clientOrderId": plan.client_order_id}
        # Ambiguous entry responses MUST NOT be retried.
        return self._call("create_order", self.cfg.symbol, "market", side,
                          plan.qty, None, params)

    def place_protection(self, position, kind, price):
        self.cfg.require_trading_confirmation()
        if kind not in ("stopLossPrice", "takeProfitPrice"):
            raise ValueError("Invalid protection type")
        side = "sell" if position.side == "long" else "buy"
        return self._call("create_order", self.cfg.symbol, "market", side,
                          position.qty, None, {kind: price, "reduceOnly": True, "hedged": False})

    def cancel_order(self, order_id):
        self.cfg.require_trading_confirmation()
        return self._call("cancel_order", order_id, self.cfg.symbol, retry=True)

    def cancel_all(self):
        self.cfg.require_trading_confirmation()
        self._call("cancel_all_orders", self.cfg.symbol, retry=True)
        self._call("cancel_all_orders", self.cfg.symbol, {"trigger": True}, retry=True)

    def close_position(self, position):
        self.cfg.require_trading_confirmation()
        side = "sell" if position.side == "long" else "buy"
        return self._call("create_order", self.cfg.symbol, "market", side,
                          position.qty, None, {"reduceOnly": True, "hedged": False})
