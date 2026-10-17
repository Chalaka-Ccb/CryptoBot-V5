"""Safety regression: legacy engine must not be able to submit real orders."""
import unittest
from pathlib import Path
from unittest.mock import Mock

from brokers.live_broker import LiveBroker
from engine.live_engine import LiveEngine


class LegacyDisabledTests(unittest.TestCase):
    def test_legacy_broker_cannot_submit(self):
        exchange = Mock()
        broker = LiveBroker(Mock(enabled=True), exchange=exchange)
        with self.assertRaisesRegex(RuntimeError, 'LEGACY LIVE EXECUTION DISABLED'):
            broker.submit_prepared(Mock(), ('SOL/USDT:USDT', 'market', 'buy', 1, None, {}))
        exchange.create_order.assert_not_called()

    def test_legacy_broker_cannot_change_settings_or_cancel(self):
        exchange = Mock()
        broker = LiveBroker(Mock(enabled=True), exchange=exchange)
        for call in (lambda: broker.configure_symbol('SOL/USDT:USDT'),
                     lambda: broker.update_stop_loss({'symbol':'SOL/USDT:USDT'}, 100),
                     lambda: broker.cancel_order('some-order')):
            with self.assertRaisesRegex(RuntimeError, 'LEGACY LIVE EXECUTION DISABLED'):
                call()
        exchange.set_leverage.assert_not_called()
        exchange.cancel_order.assert_not_called()

    def test_legacy_engine_entry_points_disabled(self):
        # Avoid construction (which opens journal); guards must run before any IO.
        engine = object.__new__(LiveEngine)
        with self.assertRaisesRegex(RuntimeError, 'LEGACY LIVE ENGINE DISABLED'):
            engine.initialize()
        with self.assertRaisesRegex(RuntimeError, 'LEGACY LIVE ENGINE DISABLED'):
            engine.run_once()

    def test_old_live_test_is_quarantined(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / 'test' / 'test_live_engine.py').exists())
        self.assertTrue((root / 'test' / 'legacy_live_engine_test.py').exists())


if __name__ == '__main__':
    unittest.main()
