import unittest
from live.bitget_order_request_builder import BitgetOrderRequestBuilder
from live.live_order_lifecycle import OrderIntent


class RequestBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = BitgetOrderRequestBuilder()

    def test_long_breakout_candidate(self):
        i = OrderIntent('long-1', 'SOL/USDT:USDT', 'long', 2, 100, 99, 103)
        result = self.builder.build(i)
        self.assertFalse(result.executable)
        self.assertEqual(result.entry['side'], 'buy')
        self.assertEqual(result.entry['triggerPrice'], '100')
        self.assertEqual(result.stop['planType'], 'loss_plan')
        self.assertEqual(result.target['planType'], 'profit_plan')

    def test_short_breakout_candidate(self):
        i = OrderIntent('short-1', 'SOL/USDT:USDT', 'short', 2, 100, 101, 97)
        result = self.builder.build(i)
        self.assertEqual(result.entry['side'], 'sell')
        self.assertEqual(result.stop['side'], 'buy')
        self.assertEqual(result.target['triggerPrice'], '97')

    def test_never_executes(self):
        i = OrderIntent('long-2', 'SOL/USDT:USDT', 'long', 2, 100, 99, 103)
        self.assertFalse(hasattr(self.builder, 'submit'))
        self.assertFalse(self.builder.build(i).executable)

    def test_reject_non_intent(self):
        with self.assertRaises(TypeError):
            self.builder.build(object())


if __name__ == '__main__':
    unittest.main()
