"""Phase 6M: connect existing offline controller to mocked Bitget requests.

NO REAL EXCHANGE WRITES. Mock transport is not a live exchange adapter.
"""
from live.bitget_order_request_builder import BitgetOrderRequestBuilder
from live.bitget_mock_transport import MockBitgetTransport
from live.live_execution_controller import OfflineExecutionController


class MockSubmissionAdapter:
    """Expose simulator.submit(intent) using builder and mocked acknowledgments."""
    def __init__(self, transport: MockBitgetTransport, builder=None):
        if not isinstance(transport, MockBitgetTransport):
            raise TypeError('MockBitgetTransport required; live transport prohibited')
        self.transport = transport
        self.builder = builder or BitgetOrderRequestBuilder()
        self.protections = {}
        self.flat = set()

    def submit(self, intent):
        candidate = self.builder.build(intent)
        if candidate.executable:
            raise RuntimeError('Execution-enabled request prohibited')
        ack = self.transport.submit_candidate(candidate)
        if ack.client_id != intent.client_id:
            raise RuntimeError('Acknowledgment client ID mismatch')
        return ack.order_id

    def protection(self, client_id):
        if client_id not in self.protections:
            raise RuntimeError('No independently mocked protection evidence')
        return self.protections[client_id]

    def is_flat_and_clear(self, client_id):
        return client_id in self.flat


def make_offline_controller(journal, transport):
    """Fail closed on unresolved journal entries, including after restart."""
    return OfflineExecutionController(journal, MockSubmissionAdapter(transport))
