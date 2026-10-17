import tempfile
import unittest
from pathlib import Path
from live.bitget_mock_transport import MockBitgetTransport
from live.bitget_offline_bridge import make_offline_controller, MockSubmissionAdapter
from live.live_intent_journal import LiveIntentJournal
from live.live_order_lifecycle import OrderIntent, OrderState


def intent(cid='offline-1'):
    return OrderIntent(cid, 'SOL/USDT:USDT', 'long', 2, 100, 99, 103)


class OfflineBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'journal.db'
        self.journal = LiveIntentJournal(self.path)
        self.transport = MockBitgetTransport()
        self.controller = make_offline_controller(self.journal, self.transport)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def queue_ack(self, cid='offline-1'):
        self.transport.queue_response(cid, {'code':'00000', 'data':{'orderId':'mock-123','clientOid':cid}})

    def test_full_offline_cycle(self):
        self.queue_ack()
        self.assertEqual(self.controller.start(intent()), 'mock-123')
        self.assertEqual(self.journal.get('offline-1')['status'], 'acknowledged')
        self.assertEqual(self.controller.update_fill(1), OrderState.PARTIAL)
        self.assertEqual(self.controller.update_fill(2), OrderState.FILLED_UNPROTECTED)
        self.controller.simulator.protections['offline-1'] = dict(
            contracts=2, stop_loss=99, take_profit=103,
            stop_confirmed=True, target_confirmed=True)
        self.assertEqual(self.controller.verify_protection(), OrderState.PROTECTED)
        self.controller.simulator.flat.add('offline-1')
        self.controller.finish()
        self.assertEqual(self.journal.unresolved(), [])

    def test_timeout_persists_uncertainty_and_blocks_restart(self):
        with self.assertRaises(TimeoutError):
            self.controller.start(intent())
        self.assertEqual(self.journal.get('offline-1')['status'], 'submitted_unknown')
        with self.assertRaises(RuntimeError):
            make_offline_controller(self.journal, MockBitgetTransport())

    def test_duplicate_entry_rejected(self):
        self.queue_ack()
        self.controller.start(intent())
        with self.assertRaises(RuntimeError):
            self.controller.start(intent('offline-2'))

    def test_unverified_protection_halts(self):
        self.queue_ack()
        self.controller.start(intent())
        self.controller.update_fill(2)
        with self.assertRaises(RuntimeError):
            self.controller.verify_protection()
        self.assertEqual(self.journal.get('offline-1')['status'], 'halted')

    def test_unverified_flat_halts(self):
        self.queue_ack()
        self.controller.start(intent())
        self.controller.update_fill(2)
        self.controller.simulator.protections['offline-1'] = dict(
            contracts=2, stop_loss=99, take_profit=103,
            stop_confirmed=True, target_confirmed=True)
        self.controller.verify_protection()
        with self.assertRaises(RuntimeError):
            self.controller.finish()
        self.assertEqual(self.journal.get('offline-1')['status'], 'halted')

    def test_real_transport_rejected(self):
        with self.assertRaises(TypeError):
            MockSubmissionAdapter(object())

if __name__ == '__main__':
    unittest.main()
