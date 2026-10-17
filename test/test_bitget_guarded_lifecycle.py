import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from live.live_intent_journal import LiveIntentJournal
from live.live_order_lifecycle import OrderIntent, OrderState
from live.bitget_guarded_lifecycle import GuardedLifecycle


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = LiveIntentJournal(Path(self.tmp.name)/'intents.sqlite')
        self.gate = Mock()
        self.gate.check.return_value = Mock(filled_contracts='1')
        self.controller = GuardedLifecycle(self.journal,self.gate)
        self.intent = OrderIntent('phase6v','SOL/USDT:USDT','long',2,100,99,103)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def start(self):
        self.controller.reserve_and_acknowledge_mock(self.intent,'mock-order')

    def test_partial_fill_and_verified_protection(self):
        self.start()
        self.assertEqual(self.controller.observe_fill(1),OrderState.PARTIAL)
        self.controller.confirm_protection()
        self.assertEqual(self.journal.get('phase6v')['status'],'protected')

    def test_no_fill_cannot_be_protected(self):
        self.start()
        with self.assertRaises(RuntimeError):self.controller.confirm_protection()

    def test_missing_protection_halts(self):
        self.start()
        self.controller.observe_fill(1)
        self.gate.check.side_effect=RuntimeError('missing SL')
        with self.assertRaises(RuntimeError):self.controller.confirm_protection()
        self.assertEqual(self.journal.get('phase6v')['status'],'halted')

    def test_restart_blocks_unresolved(self):
        self.start()
        with self.assertRaises(RuntimeError):GuardedLifecycle(self.journal,self.gate)

    def test_overfill_halts(self):
        self.start()
        with self.assertRaises(RuntimeError):self.controller.observe_fill(3)
        self.assertEqual(self.journal.get('phase6v')['status'],'halted')


if __name__=='__main__':
    unittest.main()
