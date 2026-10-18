import tempfile
import unittest
from pathlib import Path
from live.config import LiveConfig
from live.state import StateStore
from live.controls import Controls
from live.recorder import Recorder

class FoundationTests(unittest.TestCase):
    def test_defaults_and_limits(self):
        cfg = LiveConfig()
        cfg.validate()
        self.assertEqual((cfg.symbol, cfg.risk_percentage, cfg.leverage), ("SONIC/USDT:USDT", 0.05, 12))
        with self.assertRaises(ValueError):
            LiveConfig(leverage=13).validate()
        with self.assertRaises(RuntimeError):
            cfg.require_trading_confirmation()

    def test_state_and_controls(self):
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(Path(d) / "data" / "state.json")
            store.save({"pending": {"age": 2}})
            self.assertEqual(store.load()["pending"]["age"], 2)
            controls = Controls(d)
            self.assertFalse(controls.entries_blocked())
            (Path(d) / "STOP").touch()
            self.assertTrue(controls.entries_blocked())
            (Path(d) / "STOP").unlink()
            controls.lock("test")
            self.assertTrue(controls.locked())
            rec = Recorder(Path(d) / "data", Path(d) / "logs")
            rec.event("test_event", api_secret="do_not_log")
            self.assertNotIn("do_not_log", (Path(d) / "data" / "events.jsonl").read_text())
            rec.close()

if __name__ == "__main__":
    unittest.main()
