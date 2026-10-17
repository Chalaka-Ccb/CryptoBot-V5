"""CCXT adapter. Quantities in bot models are base units, not contracts."""
import math
import os
from datetime import datetime, timezone

from core.enums.order import OrderStatus, OrderType
from core.models.candle import Candle
from engine.execution_engine import Broker


class LiveBroker(Broker):
    def __init__(self, config, exchange=None):
        self.config = config
        if exchange is None:
            import ccxt
            prefix = config.exchange.upper()
            key, secret = os.getenv(f"{prefix}_API_KEY"), os.getenv(f"{prefix}_API_SECRET")
            password = os.getenv(f"{prefix}_API_PASSPHRASE")
            if not key or not secret or (config.exchange == "bitget" and not password):
                raise ValueError(f"Missing {prefix} exchange credentials")
            exchange = getattr(ccxt, config.exchange)({
                "apiKey": key, "secret": secret, "password": password,
                "enableRateLimit": True, "timeout": 30000,
                "options": {"defaultType": "swap", "maxRetriesOnFailure": 0},
            })
            # Must happen before the first request.
            if config.sandbox:
                exchange.set_sandbox_mode(True)
        self.exchange = exchange
        self.orders = {}
        self.history = {}

    def initialize(self):
        self.exchange.load_markets()
        for symbol in self.config.symbols:
            market = self.exchange.market(symbol)
            if not (market.get("swap") and market.get("linear") and market.get("settle") == "USDT"):
                raise ValueError(f"Only linear USDT perpetuals are supported: {symbol}")
            if market.get("active") is False:
                raise ValueError(f"Inactive market: {symbol}")
            for feature in ("stopLoss", "takeProfit", "triggerPrice"):
                if not self.exchange.feature_value(symbol, "createOrder", feature):
                    raise ValueError(f"{symbol} does not support {feature} in this CCXT version")

    def configure_symbol(self, symbol):
        raise RuntimeError("LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only")
        # Runner calls this only after proving the symbol has no exposure.
        from ccxt import NoChange
        operations = (
            lambda: self.exchange.set_position_mode(False, symbol),
            lambda: self.exchange.set_margin_mode(self.config.margin_mode, symbol),
            lambda: self.exchange.set_leverage(self.config.leverage, symbol, {"marginMode": self.config.margin_mode}),
        )
        for operation in operations:
            try:
                operation()
            except NoChange:
                # Bybit reports an already configured setting as an API error.
                pass

    def candles(self, symbol, timeframe, now):
        duration = self.exchange.parse_timeframe(timeframe) * 1000
        cutoff = now.timestamp() * 1000
        key = (symbol, timeframe)
        stored = self.history.setdefault(key, {})
        count = self.config.history * (3 if timeframe == "5m" else 1)
        since = max(stored) + duration if stored else int(cutoff // duration * duration - count * duration)
        while since + duration <= cutoff:
            rows = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=min(1000, count))
            closed = [r for r in rows if since <= r[0] and r[0] + duration <= cutoff]
            if not closed:
                break
            stored.update({r[0]: r for r in closed})
            following = max(r[0] for r in closed) + duration
            if following <= since:
                break
            since = following
        closed = [stored[t] for t in sorted(stored)]
        if not closed or cutoff - (closed[-1][0] + duration) > duration:
            raise RuntimeError(f"Stale {timeframe} candles for {symbol}")
        if any(b[0] - a[0] != duration for a, b in zip(closed, closed[1:])):
            raise RuntimeError(f"Missing {timeframe} candles for {symbol}")
        return [Candle(datetime.fromtimestamp(r[0] / 1000, timezone.utc), *map(float, r[1:6])) for r in closed]

    def next_open(self, symbol, boundary):
        rows = self.exchange.fetch_ohlcv(symbol, "5m", since=int(boundary.timestamp() * 1000), limit=1)
        if not rows or rows[0][0] != int(boundary.timestamp() * 1000):
            raise RuntimeError(f"Next 5m opening price is unavailable for {symbol}")
        return float(rows[0][1])

    def snapshot(self):
        balance = self.exchange.fetch_balance()
        positions = self.exchange.fetch_positions(list(self.config.symbols))
        orders = []
        for symbol in self.config.symbols:
            orders.extend(self.exchange.fetch_open_orders(symbol))
            if self.config.exchange == "bitget":
                orders.extend(self.exchange.fetch_open_orders(symbol, params={"trigger": True}))
                orders.extend(self.exchange.fetch_open_orders(symbol, params={"trigger": True, "planType": "profit_loss"}))
        return balance, positions, orders

    def prepare(self, order, stop_loss=None, take_profit=None, reduce_only=False):
        market = self.exchange.market(order.symbol)
        contract = float(market.get("contractSize") or 1)
        from ccxt import InvalidOrder
        try:
            amount = float(self.exchange.amount_to_precision(order.symbol, order.quantity / contract))
        except InvalidOrder as error:
            raise ValueError("Quantity is below exchange precision") from error
        if not math.isfinite(amount) or amount <= 0 or amount * contract > order.quantity * (1 + 1e-12):
            raise ValueError("Invalid quantity after exchange precision conversion")
        reference = order.stop_price or order.price
        if reference is None or not math.isfinite(reference) or reference <= 0:
            raise ValueError("A positive reference price is required")
        for name, value in (("amount", amount), ("cost", amount * contract * reference)):
            limits = market.get("limits", {}).get(name, {})
            if limits.get("min") is not None and value < limits["min"]:
                raise ValueError(f"Order below exchange minimum {name}")
            if limits.get("max") is not None and value > limits["max"]:
                raise ValueError(f"Order above exchange maximum {name}")
        params = {"clientOrderId": order.order_id, "marginMode": self.config.margin_mode, "hedged": False}
        if reduce_only:
            params["reduceOnly"] = True
        else:
            if stop_loss is None or take_profit is None:
                raise ValueError("Live entries require attached stop-loss and take-profit")
            from risk.risk_reward import validate_levels
            from core.models.signal import SignalSide
            sl = float(self.exchange.price_to_precision(order.symbol, stop_loss))
            tp = float(self.exchange.price_to_precision(order.symbol, take_profit))
            validate_levels(reference, sl, SignalSide.LONG if order.side.value == "buy" else SignalSide.SHORT, tp)
            params.update(stopLoss={"triggerPrice": sl}, takeProfit={"triggerPrice": tp})
            # Backtests use candle high/low (last traded prices), not mark prices.
            if self.config.exchange == "bitget":
                params["stopLoss"]["type"] = "fill_price"
                params["takeProfit"]["type"] = "fill_price"
                params["triggerType"] = "fill_price"
            else:
                params.update(slTriggerBy="LastPrice", tpTriggerBy="LastPrice", triggerBy="LastPrice", tpslMode="Full", positionIdx=0)
        kind = "market"
        price = None
        if order.order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT}:
            kind = "limit"
            price = float(self.exchange.price_to_precision(order.symbol, order.price))
        if order.order_type in {OrderType.STOP, OrderType.STOP_LIMIT}:
            params["triggerPrice"] = float(self.exchange.price_to_precision(order.symbol, order.stop_price))
            params["triggerDirection"] = "ascending" if order.side.value == "buy" else "descending"
        order.quantity = amount * contract
        return (order.symbol, kind, order.side.value, amount, price, params)

    def submit_prepared(self, order, request):
        raise RuntimeError('LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only')
        if not self.config.enabled:
            raise RuntimeError("Set LIVE_TRADING_ENABLED=true to submit orders")
        self.orders[order.order_id] = order
        result = self.exchange.create_order(*request)
        order.exchange_order_id = result.get("id")
        if not order.exchange_order_id:
            raise RuntimeError("Exchange did not return an order ID; reconcile before resuming")
        self.update_order(order, result)
        return order

    def submit_order(self, order):
        # Plain submission cannot accidentally open an unprotected position.
        raise RuntimeError('LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only')
        return self.submit_prepared(order, self.prepare(order))

    def update_order(self, order, result):
        contract = float(self.exchange.market(order.symbol).get("contractSize") or 1)
        order.filled_quantity = float(result.get("filled") or 0) * contract
        order.average_fill_price = result.get("average")
        statuses = {"closed": OrderStatus.FILLED, "canceled": OrderStatus.CANCELLED,
                    "rejected": OrderStatus.REJECTED, "expired": OrderStatus.EXPIRED}
        order.status = statuses.get(result.get("status"), OrderStatus.PARTIALLY_FILLED if order.filled_quantity else OrderStatus.OPEN)

    def fetch_order(self, order):
        if self.config.exchange == "bitget" and order.order_type in {OrderType.STOP, OrderType.STOP_LIMIT}:
            params = {"trigger": True, "planType": "normal_plan", "clientOrderId": order.order_id}
            results = self.exchange.fetch_open_orders(order.symbol, params=params)
            matches = [r for r in results if r.get("id") == order.exchange_order_id]
            if not matches:
                results = self.exchange.fetch_canceled_and_closed_orders(order.symbol, since=int(order.created_at.timestamp() * 1000), params=params)
                matches = [r for r in results if r.get("id") == order.exchange_order_id]
            if len(matches) != 1:
                raise RuntimeError(f"Cannot reconcile Bitget trigger {order.exchange_order_id}")
            result = matches[0]
            if result.get("status") == "closed":
                # A triggered plan is not a fill. Follow the actual child order.
                response = self.exchange.privateMixGetV2MixOrderPlanSubOrder({
                    "productType": "USDT-FUTURES", "planType": "normal_plan",
                    "planOrderId": order.exchange_order_id,
                })
                children = [r for r in response.get("data", []) if r.get("orderId") and r.get("status") in {"success", "in_progress"}]
                if len(children) != 1:
                    raise RuntimeError("Bitget triggered plan has no unique execution order")
                result = self.exchange.fetch_order(children[0]["orderId"], order.symbol)
        else:
            result = self.exchange.fetch_order(order.exchange_order_id, order.symbol)
        self.update_order(order, result)
        return order

    def update_stop_loss(self, position, price):
        raise RuntimeError('LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only')
        if not self.config.enabled:
            raise RuntimeError("Live trading is disabled")
        symbol = position["symbol"]
        market = self.exchange.market(symbol)
        stop = self.exchange.price_to_precision(symbol, price)
        if self.config.exchange == "bybit":
            self.exchange.privatePostV5PositionTradingStop({
                "category": "linear", "symbol": market["id"], "positionIdx": 0,
                "tpslMode": "Full", "stopLoss": stop, "slTriggerBy": "LastPrice",
                "takeProfit": self.exchange.price_to_precision(symbol, position["take_profit"]),
                "tpTriggerBy": "LastPrice",
            })
        else:
            orders = self.exchange.fetch_open_orders(symbol, params={"trigger": True, "planType": "profit_loss"})
            side = "sell" if position["side"] == "buy" else "buy"
            stops = [o for o in orders if o.get("info", {}).get("planType") in {"loss_plan", "pos_loss"}
                     and (o.get("info", {}).get("holdSide") in {position["side"], "long" if position["side"] == "buy" else "short"}
                          or o.get("side") == side)]
            if len(stops) != 1:
                raise RuntimeError("Cannot identify a unique Bitget position stop for amendment")
            old = stops[0]
            self.exchange.privateMixPostV2MixOrderModifyTpslOrder({
                "orderId": old["id"], "marginCoin": "USDT", "productType": "USDT-FUTURES",
                "symbol": market["id"], "triggerPrice": stop, "triggerType": "fill_price",
                "executePrice": "0", "size": "" if old["info"]["planType"] == "pos_loss" else self.exchange.amount_to_precision(symbol, float(old["amount"])),
            })
        return float(stop)

    def cancel_order(self, order_id):
        raise RuntimeError('LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only')
        if not self.config.enabled:
            raise RuntimeError("Live trading is disabled")
        order = self.orders[order_id]
        params = {"trigger": True} if self.config.exchange == "bitget" and order.stop_price else {}
        self.exchange.cancel_order(order.exchange_order_id, order.symbol, params=params)
        # Cancellation acknowledgement is not proof of the final fill quantity.
        self.fetch_order(order)
