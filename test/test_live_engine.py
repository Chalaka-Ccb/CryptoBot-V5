import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ccxt

from brokers.live_broker import LiveBroker
from core.enums.order import OrderSide, OrderStatus, OrderType
from core.models.candle import Candle
from core.models.order import Order
from core.models.signal import EntryTiming, SignalSide, TradingSignal
from engine.live_config import LiveConfig
from engine.live_engine import LiveEngine, LiveJournal

SYMBOL = "BTC/USDT:USDT"
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


def market(contract_size=1):
    return dict(id="BTCUSDT", symbol=SYMBOL, base="BTC", quote="USDT", settle="USDT",
                baseId="BTC", quoteId="USDT", settleId="USDT", type="swap", swap=True,
                spot=False, future=False, option=False, contract=True, linear=True,
                inverse=False, active=True, contractSize=contract_size,
                precision={"amount": 0.001, "price": 0.1},
                limits={"amount": {"min": 0.001}, "cost": {"min": 5}}, info={})


def client(name="bitget", contract_size=1):
    exchange = getattr(ccxt, name)()
    exchange.set_markets([market(contract_size)])
    exchange.load_markets = Mock(return_value=exchange.markets)
    exchange.fetch_balance = Mock(return_value={"USDT": {"total": 1000, "free": 1000, "used": 0}})
    exchange.fetch_positions = Mock(return_value=[])
    exchange.fetch_open_orders = Mock(return_value=[])
    exchange.set_position_mode = Mock()
    exchange.set_margin_mode = Mock()
    exchange.set_leverage = Mock()
    exchange.create_order = Mock(return_value={"id": "ex1", "status": "open", "filled": 0})
    exchange.fetch_order = Mock(return_value={"id": "ex1", "status": "open", "filled": 0})
    return exchange


class LiveTests(unittest.TestCase):
    def test_configured_fffd_entry_protection_and_restart(self):
        from backtesting.strategy_setup import create_strategy_coordinator
        coordinator = create_strategy_coordinator()
        for strategy in coordinator.strategies_15m + coordinator.strategies_5m:
            self.assertEqual(strategy.name, "fffd")
            self.assertTrue(strategy.use_macd_exhaustion)
            self.assertTrue(strategy.use_long_ema_filter)
            self.assertEqual(strategy.min_reward_risk, 2)
        exchange = client()
        broker = LiveBroker(self.config, exchange)
        candles = [Candle(NOW - timedelta(minutes=5 * (220 - i)), 90, 91, 89, 90, 1) for i in range(220)]
        candles[-1] = Candle(NOW - timedelta(minutes=5), 94, 96, 94, 95, 1)
        broker.candles = Mock(side_effect=lambda s, t, n: candles if t == "5m" else [Candle(NOW - timedelta(minutes=30), 90, 91, 89, 90, 1)])
        engine = LiveEngine(self.config, coordinator, broker)
        self.addCleanup(engine.close)
        engine.initialize()
        bands = [SimpleNamespace(lower=92, upper=128, middle=110)] * len(candles)
        macd = [SimpleNamespace(histogram=-2)] * len(candles)
        macd[-1] = SimpleNamespace(histogram=-1)
        with patch("strategies.bollinger.fffd.calculate_bollinger_bands", return_value=bands), patch("strategies.bollinger.fffd.calculate_macd", return_value=macd):
            orders = engine.run_once(NOW)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].strategy, "fffd")
        params = exchange.create_order.call_args.args[5]
        self.assertEqual(params["takeProfit"]["triggerPrice"], 110)
        self.assertLess(params["stopLoss"]["triggerPrice"], 89)
        exchange.fetch_order.return_value = {"id": "ex1", "status": "closed", "filled": orders[0].quantity, "average": 95}
        exchange.fetch_positions.return_value = [{"symbol": SYMBOL, "contracts": orders[0].quantity, "side": "long", "entryPrice": 95}]
        engine.reconcile()
        self.assertTrue(engine.journal.data["positions"][SYMBOL]["confirmed"])
        engine.close()
        restarted = LiveEngine(self.config, create_strategy_coordinator(), LiveBroker(self.config, exchange))
        self.addCleanup(restarted.close)
        restarted.initialize()
        self.assertIn(SYMBOL, restarted.live_positions)
        exchange.create_order.assert_called_once()
        exchange.fetch_positions.return_value = []
        restarted.reconcile()
        restarted.reconcile()
        self.assertNotIn(SYMBOL, restarted.journal.data["positions"])
        self.assertEqual(restarted.journal.data["trades"][0]["strategy"], "fffd")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = LiveConfig(exchange="bitget", symbols=(SYMBOL,), enabled=True, journal=Path(self.directory.name) / "state.json")

    def order(self, kind=OrderType.MARKET):
        return Order("LIVE-test", SYMBOL, OrderSide.BUY, kind, 0.12345, NOW,
                     price=100, stop_price=110 if kind == OrderType.STOP else None)

    def engine(self, exchange=None):
        exchange = exchange or client()
        broker = LiveBroker(self.config, exchange)
        broker.candles = Mock(side_effect=lambda s, t, n: [
            Candle(NOW - timedelta(minutes=15 if t == "15m" else 5), 100, 101, 99, 100, 1)])
        signal = TradingSignal("unchanged", SignalSide.LONG, 0, EntryTiming.CURRENT_CLOSE, None, 90)
        coordinator = Mock()
        coordinator.strategies_15m = []
        coordinator.strategies_5m = []
        coordinator.evaluate.return_value = SimpleNamespace(signal=signal, timeframe="5m")
        engine = LiveEngine(self.config, coordinator, broker)
        self.addCleanup(engine.close)
        engine.initialize()
        return engine, exchange

    def test_both_exchanges_map_attached_protection_and_contract_units(self):
        for name in ("bitget", "bybit"):
            config = LiveConfig(exchange=name, symbols=(SYMBOL,), enabled=True)
            broker = LiveBroker(config, client(name, contract_size=0.01))
            broker.initialize()
            order = self.order(OrderType.STOP)
            request = broker.prepare(order, 90, 170)
            self.assertAlmostEqual(request[3], 12.345)
            self.assertEqual(request[5]["stopLoss"]["triggerPrice"], 90)
            self.assertEqual(request[5]["takeProfit"]["triggerPrice"], 170)
            self.assertEqual(request[5]["triggerDirection"], "ascending")
            self.assertEqual(request[5]["triggerPrice"], 110)
            # Exercise the real installed CCXT request serializer without HTTP.
            if name == "bitget":
                payload = broker.exchange.create_order_request(*request)
                self.assertEqual(float(payload["stopLossTriggerPrice"]), 90)
            else:
                payload = broker.exchange.create_order_request(*request)
                self.assertEqual(float(payload["stopLoss"]), 90)

    def test_unprotected_or_subminimum_entry_rejected(self):
        broker = LiveBroker(self.config, client())
        with self.assertRaises(ValueError):
            broker.submit_order(self.order())
        order = self.order()
        order.quantity = 0.00001
        with self.assertRaises(ValueError):
            broker.prepare(order, 90, 130)
        broker.exchange.create_order.assert_not_called()

    def test_pending_order_blocks_duplicate_and_survives_restart(self):
        engine, exchange = self.engine()
        self.assertEqual(len(engine.run_once(NOW)), 1)
        self.assertEqual(engine.run_once(NOW + timedelta(minutes=5)), [])
        exchange.create_order.assert_called_once()
        engine.close()
        restarted, _ = self.engine(exchange)
        self.assertEqual(restarted.run_once(NOW + timedelta(minutes=10)), [])
        exchange.create_order.assert_called_once()

    def test_timeout_is_never_retried(self):
        engine, exchange = self.engine()
        exchange.create_order.side_effect = TimeoutError("unknown outcome")
        with self.assertRaises(TimeoutError):
            engine.run_once(NOW)
        with self.assertRaisesRegex(RuntimeError, "Uncertain submission"):
            engine.run_once(NOW + timedelta(minutes=5))
        exchange.create_order.assert_called_once()
        self.assertEqual(len(engine.journal.data["orders"]), 1)

    def test_partial_fill_keeps_symbol_busy(self):
        engine, exchange = self.engine()
        engine.run_once(NOW)
        exchange.fetch_order.return_value = {"id": "ex1", "status": "open", "filled": 0.02, "average": 101}
        self.assertEqual(engine.run_once(NOW + timedelta(minutes=5)), [])
        order = next(iter(engine.broker.orders.values()))
        self.assertEqual(order.status, OrderStatus.PARTIALLY_FILLED)
        self.assertAlmostEqual(order.filled_quantity, 0.02)

    def test_disabled_mode_never_changes_exchange(self):
        self.config = replace(self.config, enabled=False)
        engine, exchange = self.engine()
        self.assertEqual(engine.run_once(NOW), [])
        exchange.create_order.assert_not_called()
        exchange.set_position_mode.assert_not_called()

    def test_same_closed_candle_is_evaluated_once(self):
        engine, exchange = self.engine()
        engine.coordinator.evaluate.return_value = SimpleNamespace(signal=None, timeframe="none")
        engine.run_once(NOW)
        engine.run_once(NOW)
        engine.coordinator.evaluate.assert_called_once()

    def test_already_configured_exchange_settings_allow_entry(self):
        exchange = client()
        exchange.set_position_mode.side_effect = ccxt.NoChange("Position mode is not modified")
        engine, exchange = self.engine(exchange)
        self.assertEqual(len(engine.run_once(NOW)), 1)
        exchange.set_leverage.assert_called_once()

    def test_cancelled_partial_fill_remains_blocked_by_position(self):
        engine, exchange = self.engine()
        engine.run_once(NOW)
        exchange.fetch_order.return_value = {"id": "ex1", "status": "canceled", "filled": 0.02}
        exchange.fetch_positions.return_value = [{"symbol": SYMBOL, "contracts": 0.02, "side": "long"}]
        self.assertEqual(engine.run_once(NOW + timedelta(minutes=5)), [])
        self.assertEqual(engine.journal.data["orders"], {})
        exchange.create_order.assert_called_once()

    def test_existing_position_prevents_configuration_and_entry(self):
        exchange = client()
        exchange.fetch_positions.return_value = [{"symbol": SYMBOL, "contracts": 0.1}]
        engine, exchange = self.engine(exchange)
        self.assertEqual(engine.run_once(NOW), [])
        exchange.create_order.assert_not_called()
        exchange.set_position_mode.assert_not_called()

    def test_drawdown_persists_across_restart(self):
        self.config = replace(self.config, drawdown_enabled=True)
        engine, exchange = self.engine()
        engine.coordinator.evaluate.return_value = SimpleNamespace(signal=None, timeframe="none")
        engine.run_once(NOW)
        exchange.fetch_balance.return_value = {"USDT": {"total": 940, "free": 940, "used": 0}}
        self.assertEqual(engine.run_once(NOW + timedelta(minutes=5)), [])
        engine.close()
        restarted, _ = self.engine(exchange)
        self.assertEqual(restarted.run_once(NOW + timedelta(minutes=10)), [])
        exchange.create_order.assert_not_called()

    def test_journal_lock_prevents_second_runner(self):
        journal = LiveJournal(self.config.journal, "account")
        self.addCleanup(journal.close)
        with self.assertRaises(OSError):
            LiveJournal(self.config.journal, "account")

    def test_candles_exclude_incomplete_and_reject_stale_data(self):
        exchange = client()
        exchange.fetch_ohlcv = Mock(return_value=[
            [int((NOW - timedelta(minutes=5)).timestamp() * 1000), 100, 101, 99, 100, 1],
            [int(NOW.timestamp() * 1000), 100, 101, 99, 100, 1]])
        broker = LiveBroker(self.config, exchange)
        self.assertEqual(len(broker.candles(SYMBOL, "5m", NOW)), 1)
        with self.assertRaisesRegex(RuntimeError, "Stale"):
            broker.candles(SYMBOL, "5m", NOW + timedelta(minutes=20))


if __name__ == "__main__":
    unittest.main()
