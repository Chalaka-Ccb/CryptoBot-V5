import unittest
from live.bitget_mock_transport import MockBitgetTransport
from live.bitget_order_request_builder import BitgetOrderRequestBuilder
from live.live_order_lifecycle import OrderIntent


def candidate(cid='test-1'):
    intent = OrderIntent(cid, 'SOL/USDT:USDT', 'long', 2, 100, 99, 103)
    return BitgetOrderRequestBuilder().build(intent)


class MockTransportTests(unittest.TestCase):
    def test_valid_acknowledgment(self):
        t = MockBitgetTransport()
        t.queue_response('test-1', {'code':'00000','data':{'orderId':'123','clientOid':'test-1'}})
        ack = t.submit_candidate(candidate())
        self.assertEqual(ack.order_id, '123')

    def test_missing_response_fails_uncertain(self):
        t = MockBitgetTransport()
        with self.assertRaises(TimeoutError): t.submit_candidate(candidate())
        with self.assertRaises(RuntimeError): t.submit_candidate(candidate())

    def test_bad_code_rejected(self):
        t = MockBitgetTransport()
        t.queue_response('test-1', {'code':'40001','data':{}})
        with self.assertRaises(RuntimeError): t.submit_candidate(candidate())

    def test_mismatched_client_id_rejected(self):
        t = MockBitgetTransport()
        t.queue_response('test-1', {'code':'00000','data':{'orderId':'123','clientOid':'other'}})
        with self.assertRaises(RuntimeError): t.submit_candidate(candidate())

    def test_missing_order_id_rejected(self):
        t = MockBitgetTransport()
        t.queue_response('test-1', {'code':'00000','data':{'clientOid':'test-1'}})
        with self.assertRaises(RuntimeError): t.submit_candidate(candidate())

    def test_network_timeout_blocks_retry(self):
        t = MockBitgetTransport()
        t.fail_next = TimeoutError('mock timeout')
        with self.assertRaises(TimeoutError): t.submit_candidate(candidate())
        with self.assertRaises(RuntimeError): t.submit_candidate(candidate())

    def test_no_network_or_exchange_methods(self):
        t = MockBitgetTransport()
        self.assertFalse(hasattr(t, 'exchange'))
        self.assertFalse(hasattr(t, 'create_order'))
        self.assertFalse(hasattr(t, 'cancel_order'))


if __name__ == '__main__':
    unittest.main()
