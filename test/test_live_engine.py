import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from core.models.candle import Candle
from live.config import LiveConfig
from live.controls import Controls
from live.engine import LiveEngine
from live.state import StateStore
from live.models import Balance


class FakeExchange:
    def __init__(self):
        self.position = None
        self.current = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)
    def get_position(self):
        return self.position
    def get_balance(self):
        return Balance(1000, 1000)
    def get_candles(self, timeframe):
        return [Candle(self.current, 100, 101, 99, 100)]
    def get_price(self):
        return 100


class FakeRecorder:
    def event(self, *args, **kwargs):
        pass


class FakeOrders:
    def __init__(self):
        self.flattens = 0
    def ensure_flat(self):
        self.flattens += 1
    def verify_saved_protection(self, saved, position):
        return True


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.controls = Controls(self.temp.name)
        self.exchange = FakeExchange()
        self.orders = FakeOrders()
        self.engine = LiveEngine(self.exchange, self.orders, FakeRecorder(),
            StateStore(Path(self.temp.name) / "state.json"), self.controls, LiveConfig())

    def test_flatten(self):
        (Path(self.temp.name) / "FLATTEN").touch()
        self.engine.tick()
        self.assertEqual(self.orders.flattens, 1)

    def test_pending_expires_after_three_candles(self):
        self.engine.state["pending"] = {"created": self.exchange.current.isoformat(),
                                         "side": "long", "trigger": 200}
        self.exchange.current += timedelta(minutes=15)
        self.engine._expire_pending(Candle(self.exchange.current, 100, 100, 100, 100))
        self.assertIsNone(self.engine.state["pending"])

    def test_daily_drawdown_locks(self):
        self.engine.state["stats"] = {"day": datetime.now(timezone.utc).date().isoformat(),
                                      "start_equity": 1100}
        self.assertFalse(self.engine._daily_risk())
        self.assertTrue(self.controls.locked())

    def test_restart_inflight_locks(self):
        self.engine.state["entry_in_flight"] = True
        self.engine.tick()
        self.assertTrue(self.controls.locked())


if __name__ == "__main__":
    unittest.main()
