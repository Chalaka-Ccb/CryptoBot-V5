import unittest
from live.order_manager import OrderManager
from live.config import LiveConfig

class FakeControls:
    def __init__(self):
        self.reason = None
    def entries_blocked(self):
        return False
    def lock(self, reason):
        self.reason = reason

class FakeRecorder:
    def event(self, *args, **kwargs):
        pass

class FakeExchange:
    def __init__(self):
        self.position = None
        self.cancelled = 0
    def get_position(self):
        return self.position
    def cancel_all(self):
        self.cancelled += 1
    def close_position(self, position):
        self.position = None

class OrderTests(unittest.TestCase):
    def test_flatten_locks(self):
        exchange = FakeExchange()
        controls = FakeControls()
        manager = OrderManager(exchange, controls, FakeRecorder(), LiveConfig())
        self.assertTrue(manager.ensure_flat())
        self.assertEqual(exchange.cancelled, 1)
        self.assertIsNotNone(controls.reason)

if __name__ == "__main__":
    unittest.main()
