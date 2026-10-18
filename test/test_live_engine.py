import tempfile
import unittest
from pathlib import Path
from live.config import LiveConfig
from live.controls import Controls
from live.engine import LiveEngine
from live.state import StateStore
from core.models.candle import Candle
from datetime import datetime, timezone

class FakeExchange:
    def __init__(self):
        self.position = None
        self.calls = 0
    def get_position(self):
        return self.position
    def get_candles(self, timeframe):
        self.calls += 1
        return [Candle(datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc), 100, 101, 99, 100)]
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

class EngineTests(unittest.TestCase):
    def test_stop_and_flatten(self):
        with tempfile.TemporaryDirectory() as d:
            controls = Controls(d)
            orders = FakeOrders()
            engine = LiveEngine(FakeExchange(), orders, FakeRecorder(),
                                StateStore(Path(d) / "state.json"), controls, LiveConfig())
            (Path(d) / "FLATTEN").touch()
            engine.tick()
            self.assertEqual(orders.flattens, 1)
            self.assertTrue(controls.entries_blocked())

if __name__ == "__main__":
    unittest.main()
