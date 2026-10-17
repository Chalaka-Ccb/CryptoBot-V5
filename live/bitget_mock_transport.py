"""Phase 6L: strictly offline mocked Bitget response transport.

Not an exchange client. Never accesses credentials, CCXT, or the network.
Candidate request payloads are NOT verified against live Bitget endpoints.
"""
from dataclasses import dataclass
from live.bitget_order_request_builder import CandidateOrderRequests


@dataclass(frozen=True)
class MockAcknowledgment:
    order_id: str
    client_id: str


class MockBitgetTransport:
    def __init__(self):
        self.requests = {}
        self.responses = {}
        self.fail_next = None

    def queue_response(self, client_id, response):
        if client_id in self.responses:
            raise RuntimeError("Duplicate mocked response")
        self.responses[client_id] = response

    def submit_candidate(self, candidate: CandidateOrderRequests):
        if not isinstance(candidate, CandidateOrderRequests) or candidate.executable:
            raise RuntimeError("Only disabled candidate requests allowed")
        cid = candidate.entry.get('clientOid')
        if not isinstance(cid, str) or not cid:
            raise RuntimeError("Missing client order ID")
        if cid in self.requests:
            raise RuntimeError("Duplicate client ID: no retry")
        self.requests[cid] = candidate
        if self.fail_next is not None:
            failure = self.fail_next
            self.fail_next = None
            raise failure
        if cid not in self.responses:
            raise TimeoutError("No mocked acknowledgment; submission uncertain")
        raw = self.responses.pop(cid)
        if not isinstance(raw, dict) or raw.get('code') != '00000':
            raise RuntimeError("Mocked Bitget rejected/ambiguous response")
        data = raw.get('data')
        if not isinstance(data, dict):
            raise RuntimeError("Missing acknowledgment data")
        oid = data.get('orderId')
        response_cid = data.get('clientOid')
        if not isinstance(oid, str) or not oid.strip() or response_cid != cid:
            raise RuntimeError("Mismatched or missing acknowledgment identifiers")
        return MockAcknowledgment(oid, cid)
