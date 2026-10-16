import unittest
from datetime import datetime, timezone
from core.models.candle import Candle
from core.models.signal import TradingSignal, EntryTiming, SignalSide
from live.paper_execution import SingleSymbolPaperExecution, PaperState


def candle(o, h, l, c):
    return Candle(datetime.now(timezone.utc), o, h, l, c, 100)


def signal(side=SignalSide.LONG):
    return TradingSignal('bollinger_channel_rebound', side, 1, EntryTiming.BREAKOUT,
                         101 if side == SignalSide.LONG else 99,
                         99 if side == SignalSide.LONG else 101,
                         105 if side == SignalSide.LONG else 95)


class PaperExecutionTests(unittest.TestCase):
    def test_pending_does_not_fill_early(self):
        p = SingleSymbolPaperExecution(balance=100)
        p.submit(signal(), reference_price=100)
        self.assertIsNone(p.on_candle(candle(100, 100.5, 99.5, 100)))
        self.assertEqual(p.state, PaperState.PENDING)

    def test_fill_then_target(self):
        p = SingleSymbolPaperExecution(balance=100)
        p.submit(signal(), reference_price=100)
        p.on_candle(candle(100, 102, 100, 101))
        self.assertEqual(p.state, PaperState.OPEN)
        trade = p.on_candle(candle(102, 106, 101, 105))
        self.assertEqual(trade.reason, 'TP')
        self.assertGreater(trade.net_pnl, 0)
        self.assertEqual(p.state, PaperState.IDLE)

    def test_stop_first_when_both_hit(self):
        p = SingleSymbolPaperExecution(balance=100)
        p.submit(signal(), reference_price=100)
        p.on_candle(candle(100, 102, 100, 101))
        trade = p.on_candle(candle(101, 106, 98, 102))
        self.assertEqual(trade.reason, 'SL')

    def test_graceful_stop_while_open(self):
        p = SingleSymbolPaperExecution(balance=100)
        p.submit(signal(), reference_price=100)
        p.on_candle(candle(100, 102, 100, 101))
        p.request_stop()
        self.assertEqual(p.state, PaperState.OPEN)
        with self.assertRaises(RuntimeError):
            p.submit(signal(), reference_price=100)
        p.on_candle(candle(101, 105, 100, 104))
        self.assertEqual(p.state, PaperState.STOPPED)

    def test_stop_cancels_pending(self):
        p = SingleSymbolPaperExecution(balance=100)
        p.submit(signal(), reference_price=100)
        p.request_stop()
        self.assertEqual(p.state, PaperState.STOPPED)

    def test_caps(self):
        for kwargs in ({'risk_fraction': .051}, {'leverage': 16}):
            with self.assertRaises(ValueError):
                SingleSymbolPaperExecution(balance=100, **kwargs)

    def test_short(self):
        p = SingleSymbolPaperExecution(balance=100)
        p.submit(signal(SignalSide.SHORT), reference_price=100)
        p.on_candle(candle(100, 100, 98, 99))
        trade = p.on_candle(candle(99, 100, 94, 96))
        self.assertEqual(trade.reason, 'TP')


if __name__ == '__main__':
    unittest.main()
