import unittest
from live.order_manager import OrderManager
from live.config import LiveConfig
from live.models import Position


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
    def get_protection(self):
        return []


class OrderTests(unittest.TestCase):
    def test_flatten_locks(self):
        exchange, controls = FakeExchange(), FakeControls()
        manager = OrderManager(exchange, controls, FakeRecorder(), LiveConfig())
        self.assertTrue(manager.ensure_flat())
        self.assertEqual(exchange.cancelled, 1)
        self.assertIsNotNone(controls.reason)

    def test_missing_protection_rejected(self):
        manager = OrderManager(FakeExchange(), FakeControls(), FakeRecorder(), LiveConfig())
        position = Position("long", 2, 100)
        self.assertFalse(manager.verify_saved_protection({"sl": 99, "tp": 103}, position))

    def test_matching_protection(self):
        exchange = FakeExchange()
        exchange.get_protection = lambda: [
            {"info": {"planType": "loss_plan"}, "triggerPrice": 99, "side": "sell", "amount": 2},
            {"info": {"planType": "profit_plan"}, "triggerPrice": 103, "side": "sell", "amount": 2},
        ]
        manager = OrderManager(exchange, FakeControls(), FakeRecorder(), LiveConfig())
        self.assertTrue(manager.verify_saved_protection({"sl": 99, "tp": 103},
                                                        Position("long", 2, 100)))


if __name__ == "__main__":
    unittest.main()
