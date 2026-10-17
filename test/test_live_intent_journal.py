import tempfile
import unittest
from pathlib import Path

from live.live_intent_journal import LiveIntentJournal
from live.live_order_lifecycle import OrderIntent


def intent(client_id):
    return OrderIntent(client_id, 'SOL/USDT:USDT', 'long', 1, 100, 99, 103)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'intents.sqlite'
        self.j = LiveIntentJournal(self.path)

    def tearDown(self):
        self.j.close()
        self.temp.cleanup()

    def test_reservation_survives_restart_and_blocks_other_entry(self):
        self.j.reserve(intent('a'))
        self.j.close()
        self.j = LiveIntentJournal(self.path)
        self.assertEqual(self.j.unresolved(), ['a'])
        with self.assertRaises(RuntimeError):
            self.j.reserve(intent('b'))
        with self.assertRaises(RuntimeError):
            self.j.reserve(intent('a'))

    def test_uncertain_submission_survives_restart(self):
        self.j.reserve(intent('a'))
        self.j.mark_submission_uncertain('a')
        self.j.close()
        self.j = LiveIntentJournal(self.path)
        self.assertEqual(self.j.get('a')['status'], 'submitted_unknown')
        with self.assertRaises(RuntimeError):
            self.j.reserve(intent('b'))

    def test_lifecycle_and_new_entry_only_after_reconciliation(self):
        self.j.reserve(intent('a'))
        self.j.mark_submission_uncertain('a')
        self.j.acknowledge('a', 'exchange-1')
        self.j.mark_protected('a')
        self.j.mark_closed('a')
        self.j.reserve(intent('b'))
        self.assertEqual(self.j.get('a')['exchange_order_id'], 'exchange-1')

    def test_invalid_transitions_and_halt_block(self):
        self.j.reserve(intent('a'))
        with self.assertRaises(RuntimeError):
            self.j.mark_closed('a')
        self.j.halt('a')
        with self.assertRaises(RuntimeError):
            self.j.reserve(intent('b'))
        with self.assertRaises(RuntimeError):
            self.j.mark_cancelled('a')

    def test_cancelled_reservation_allows_new_but_never_reuse_id(self):
        self.j.reserve(intent('a'))
        self.j.mark_cancelled('a')
        self.j.reserve(intent('b'))
        with self.assertRaises(RuntimeError):
            self.j.reserve(intent('a'))


if __name__ == '__main__':
    unittest.main()
