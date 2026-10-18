"""Bitget gateway. Validate Bitget account mode and protection APIs on demo."""
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
            "apiKey": cfg.api_key, "secret": cfg.api_secret, "password": cfg.api_passphrase,
            "enableRateLimit": True, "timeout": 15000,
            "options": {"defaultType": "swap"},
        })
        if cfg.demo and client is None:
            self.client.set_sandbox_mode(True)
        self.markets_loaded = False

    def _call(self, name, *args, retry=False, **kwargs):
        for attempt in range(3 if retry else 1):
            try:
                result = getattr(self.client, name)(*args, **kwargs)
                self.recorder.order_call(name, status="ok", symbol=self.cfg.symbol)
                return result
            except Exception as error:
                self.recorder.order_call(name, status="error", error_type=type(error).__name__,
                                         symbol=self.cfg.symbol)
                if not retry or attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def load_markets(self):
        markets = self._call("load_markets", retry=True)
        if self.cfg.symbol not in markets:
            raise RuntimeError("Symbol unavailable")
        self.markets_loaded = True
        return markets[self.cfg.symbol]

    def setup_account(self):
        if self.get_position() is not None:
            self.recorder.event("account_setup_skipped", reason="existing_position")
            return
        self._call("set_position_mode", False, self.cfg.symbol)
        self._call("set_margin_mode", self.cfg.margin_mode, self.cfg.symbol)
        self._call("set_leverage", self.cfg.leverage, self.cfg.symbol)

    def get_candles(self, timeframe, limit=500):
        if timeframe not in ("5m", "15m"):
            raise ValueError("Invalid timeframe")
        rows = self._call("fetch_ohlcv", self.cfg.symbol, timeframe, None, limit, retry=True)
        now = self.client.milliseconds()
        interval = 300000 if timeframe == "5m" else 900000
        # Exclude the currently forming candle; immutable inputs avoid stale caches.
        return [Candle(datetime.fromtimestamp(row[0] / 1000, timezone.utc),
                       float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
                for row in rows if row[0] + interval <= now - 3000]

    def get_price(self):
        ticker = self._call("fetch_ticker", self.cfg.symbol, retry=True)
        price = float(ticker.get("last") or 0)
        if price <= 0:
            raise RuntimeError("No usable last price")
        return price

    def get_balance(self):
        data = self._call("fetch_balance", {"type": "swap"}, retry=True)
        usdt = data.get("USDT") or {}
        if usdt.get("total") is None or usdt.get("free") is None:
            raise RuntimeError("USDT balance missing")
        return Balance(float(usdt["total"]), float(usdt["free"]))

    def get_position(self):
        positions = self._call("fetch_positions", [self.cfg.symbol], retry=True)
        active = [p for p in positions if float(p.get("contracts") or 0) > 0]
        if len(active) > 1:
            raise RuntimeError("Multiple positions found")
        if not active:
            return None
        p = active[0]
        return Position(p["side"], float(p["contracts"]), float(p.get("entryPrice") or 0),
                        float(p["liquidationPrice"]) if p.get("liquidationPrice") else None)

    def market_limits(self):
        if not self.markets_loaded:
            self.load_markets()
        m = self.client.market(self.cfg.symbol)
        amount = m.get("limits", {}).get("amount", {})
        cost = m.get("limits", {}).get("cost", {})
        precision = m.get("precision", {}).get("amount")
        # CCXT precision may represent decimal places OR tick size.
        if self.client.precisionMode == ccxt.TICK_SIZE:
            step = float(precision) if precision is not None else None
        elif self.client.precisionMode == ccxt.DECIMAL_PLACES:
            step = 10 ** (-int(precision)) if precision is not None else None
        else:
            raise RuntimeError("Unsupported CCXT precision mode")
        return QuantityLimits(minimum=amount.get("min"), maximum=amount.get("max"),
                              step=step, min_notional=cost.get("min"))

    def get_protection(self):
        # Must be validated against Bitget classic/UTA response format.
        return self._call("fetch_open_orders", self.cfg.symbol, None, None,
                          {"trigger": True}, retry=True)

    def place_entry(self, plan):
        self.cfg.require_trading_confirmation()
        params = {"marginMode": self.cfg.margin_mode,
                  "stopLoss": {"triggerPrice": plan.sl},
                  "takeProfit": {"triggerPrice": plan.tp},
                  "clientOrderId": plan.client_order_id}
        return self._call("create_order", self.cfg.symbol, "market",
                          "buy" if plan.side == "long" else "sell", plan.qty, None, params)

    def cancel_all(self):
        self.cfg.require_trading_confirmation()
        # Never blindly retry cancellation failures; inspect orders before retrying.
        self._call("cancel_all_orders", self.cfg.symbol)
        self._call("cancel_all_orders", self.cfg.symbol, {"trigger": True})

    def close_position(self, position):
        self.cfg.require_trading_confirmation()
        return self._call("create_order", self.cfg.symbol, "market",
                          "sell" if position.side == "long" else "buy", position.qty,
                          None, {"reduceOnly": True})
