import tempfile
import unittest
from pathlib import Path
from live.live_intent_journal import LiveIntentJournal
from live.live_order_lifecycle import OrderIntent, OrderState
from live.live_execution_controller import OfflineExecutionController, SimulatedExchange


def intent(cid='trial1'):
    return OrderIntent(cid, 'SOL/USDT:USDT', 'long', 2.0, 100.0, 99.0, 103.0)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'orders.db'
        self.journal = LiveIntentJournal(self.path)
        self.sim = SimulatedExchange()
        self.controller = OfflineExecutionController(self.journal, self.sim)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def test_complete_simulated_trade(self):
        self.assertEqual(self.controller.start(intent()), 'sim-trial1')
        self.assertEqual(self.controller.update_fill(1), OrderState.PARTIAL)
        self.assertEqual(self.controller.update_fill(2), OrderState.FILLED_UNPROTECTED)
        self.sim.protections['trial1'] = dict(contracts=2, stop_loss=99, take_profit=103,
                                               stop_confirmed=True, target_confirmed=True)
        self.assertEqual(self.controller.verify_protection(), OrderState.PROTECTED)
        self.sim.flat.add('trial1')
        self.controller.finish()
        self.assertEqual(self.journal.unresolved(), [])
        self.controller.start(intent('trial2'))

    def test_restart_blocks_uncertain_submission(self):
        self.sim.fail_submit = True
        with self.assertRaises(TimeoutError):
            self.controller.start(intent())
        with self.assertRaises(RuntimeError):
            OfflineExecutionController(self.journal, SimulatedExchange())
        self.assertEqual(self.journal.get('trial1')['status'], 'submitted_unknown')

    def test_protection_mismatch_halts(self):
        self.controller.start(intent())
        self.controller.update_fill(2)
        self.sim.protections['trial1'] = dict(contracts=2, stop_loss=98, take_profit=103,
                                               stop_confirmed=True, target_confirmed=True)
        with self.assertRaisesRegex(RuntimeError, 'mismatch'):
            self.controller.verify_protection()
        self.assertEqual(self.journal.get('trial1')['status'], 'halted')

    def test_insufficient_protection_halts(self):
        self.controller.start(intent())
        self.controller.update_fill(2)
        self.sim.protections['trial1'] = dict(contracts=1, stop_loss=99, take_profit=103,
                                               stop_confirmed=True, target_confirmed=True)
        with self.assertRaises(RuntimeError):
            self.controller.verify_protection()
        self.assertEqual(self.journal.get('trial1')['status'], 'halted')

    def test_close_requires_flat_and_no_plans(self):
        self.controller.start(intent())
        self.controller.update_fill(2)
        self.sim.protections['trial1'] = dict(contracts=2, stop_loss=99, take_profit=103,
                                               stop_confirmed=True, target_confirmed=True)
        self.controller.verify_protection()
        with self.assertRaisesRegex(RuntimeError, 'not reconciled'):
            self.controller.finish()
        self.assertEqual(self.journal.get('trial1')['status'], 'halted')

    def test_second_order_blocked(self):
        self.controller.start(intent())
        with self.assertRaises(RuntimeError):
            self.controller.start(intent('trial2'))


if __name__ == '__main__':
    unittest.main()
