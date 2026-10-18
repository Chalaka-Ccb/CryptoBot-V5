"""Offline smoke tests for independent research and NR7 OCO."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from backtesting.research import ResearchRunner
from engine.strategy_coordinator import StrategyCoordinator
from strategies.breakout.nr7 import NR7Strategy
from core.models.candle import Candle


class ResearchNR7Tests(unittest.TestCase):
    def test_nr7_emits_two_opposing_signals(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        candles = [Candle(start + timedelta(minutes=i), 10, 11, 9, 10, 100)
                   for i in range(6)]
        candles.append(Candle(start + timedelta(minutes=6), 10, 10.5, 9.5, 10, 100))
        signals = NR7Strategy().generate_signals(candles, 6)
        self.assertEqual(len(signals), 2)
        self.assertEqual({s.side.value for s in signals}, {"long", "short"})
        self.assertTrue(all(s.diagnostics["oco_pair"] for s in signals))

    def test_ambiguous_oco_does_not_fill(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        candles = [Candle(start + timedelta(minutes=i), 10, 11, 9, 10, 100)
                   for i in range(6)]
        candles.append(Candle(start + timedelta(minutes=6), 10, 10.5, 9.5, 10, 100))
        candles.append(Candle(start + timedelta(minutes=7), 10, 11.5, 8.5, 10, 100))
        coordinator = StrategyCoordinator(strategies_15m=[], strategies_5m=[NR7Strategy()])
        data = SimpleNamespace(symbol="SOL/USDT:USDT", candles_5m=candles, candles_15m=[])
        result = ResearchRunner(coordinator, timeframe="1m").run(
            SimpleNamespace(**vars(data), candles_1m=candles))
        self.assertEqual(len(result.trades), 0)
        self.assertEqual(sum(x["status"] == "ambiguous_oco" for x in result.unfilled), 2)


if __name__ == "__main__":
    unittest.main()
