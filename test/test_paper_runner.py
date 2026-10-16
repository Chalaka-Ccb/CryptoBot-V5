import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from core.models.candle import Candle
from core.models.signal import TradingSignal, EntryTiming, SignalSide
from live.paper_execution import SingleSymbolPaperExecution, PaperState
from live.paper_runner import PaperRunner

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

def candle(minutes):
    return Candle(BASE + timedelta(minutes=minutes), 100, 100.5, 99.5, 100, 1)

class Gateway:
    def __init__(self):
        self.five = [candle(0)]
        self.fifteen = [candle(0)]
    def fetch_closed_candles(self, tf):
        return self.five if tf == '5m' else self.fifteen

class PaperRunnerTests(unittest.TestCase):
    def setUp(self):
        self.g = Gateway()
        self.paper = SingleSymbolPaperExecution(balance=100)
        self.strategy15 = Mock()
        self.strategy5 = Mock()
        self.strategy15.generate_signal.return_value = None
        self.strategy5.generate_signal.return_value = None
        self.runner = PaperRunner(self.g, self.paper, SimpleNamespace(
            strategies_15m=[self.strategy15], strategies_5m=[self.strategy5]),
            stop_file='/tmp/cryptobot-test-stop-file-should-not-exist')

    def test_startup_does_not_replay(self):
        self.runner.tick()
        self.assertEqual(self.strategy5.generate_signal.call_count, 0)

    def test_only_new_candle_evaluated(self):
        self.runner.tick()
        self.runner.tick()
        self.assertEqual(self.strategy5.generate_signal.call_count, 0)
        self.g.five.append(candle(5))
        self.runner.tick()
        self.assertEqual(self.strategy5.generate_signal.call_count, 1)
        self.runner.tick()
        self.assertEqual(self.strategy5.generate_signal.call_count, 1)

    def test_15m_priority(self):
        self.runner.tick()
        self.g.five.append(candle(5))
        self.g.fifteen.append(candle(15))
        self.strategy15.generate_signal.return_value = TradingSignal(
            'bollinger_channel_rebound', SignalSide.LONG, 1, EntryTiming.BREAKOUT, 101, 99, 105)
        self.runner.tick()
        self.assertEqual(self.paper.state, PaperState.PENDING)
        self.assertEqual(self.strategy5.generate_signal.call_count, 0)

    def test_missed_candle_fails_closed(self):
        self.runner.tick()
        self.g.five.append(candle(15))
        with self.assertRaises(RuntimeError):
            self.runner.tick()

    def test_idle_stop(self):
        self.runner.request_stop()
        self.assertEqual(self.paper.state, PaperState.STOPPED)

if __name__ == '__main__':
    unittest.main()
