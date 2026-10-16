import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from core.models.signal import TradingSignal, SignalSide, EntryTiming
from live.paper_execution import SingleSymbolPaperExecution, PaperState
from live.paper_state_store import save_checkpoint, load_checkpoint


def runner():
    return SimpleNamespace(paper=SingleSymbolPaperExecution(balance=100), last_5m=datetime(2026, 1, 1, tzinfo=timezone.utc),
                           last_15m=datetime(2026, 1, 1, tzinfo=timezone.utc), started=True)


class CheckpointTests(unittest.TestCase):
    def test_idle_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = runner(), runner()
            a.paper.balance = 125
            path = Path(d) / 'state.json'
            save_checkpoint(path, a)
            load_checkpoint(path, b)
            self.assertEqual(b.paper.balance, 125)
            self.assertEqual(b.last_5m, a.last_5m)

    def test_pending_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = runner(), runner()
            a.paper.submit(TradingSignal('bollinger_channel_rebound', SignalSide.LONG, 1, EntryTiming.BREAKOUT, 101, 99, 105), reference_price=100)
            path = Path(d) / 'state.json'
            save_checkpoint(path, a)
            load_checkpoint(path, b)
            self.assertEqual(b.paper.state, PaperState.PENDING)
            self.assertEqual(b.paper.signal.trigger_price, 101)

    def test_reject_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = runner(), runner()
            b.paper.leverage = 10
            path = Path(d) / 'state.json'
            save_checkpoint(path, a)
            with self.assertRaises(ValueError):
                load_checkpoint(path, b)

    def test_reject_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'state.json'
            path.write_text('{bad', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_checkpoint(path, runner())

if __name__ == '__main__':
    unittest.main()
