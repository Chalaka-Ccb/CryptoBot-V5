"""Phase 6S: offline audit of candidate Bitget Classic V2 order contracts.

No API writes. Intentionally rejects legacy 6K payloads that mix endpoint
schemas; does NOT certify that a corrected payload would execute safely.
"""
from dataclasses import dataclass
from live.bitget_order_request_builder import BitgetOrderRequestBuilder


@dataclass(frozen=True)
class ContractFinding:
    name: str
    reason: str


@dataclass(frozen=True)
class ContractAudit:
    findings: tuple[ContractFinding, ...]
    executable: bool = False

    @property
    def passed(self):
        return not self.findings


class BitgetOrderContractAuditor:
    def __init__(self, builder=None):
        self.builder = builder or BitgetOrderRequestBuilder()

    def audit(self, intent):
        candidate = self.builder.build(intent)
        findings = []
        entry = candidate.entry
        # Classic V2 normal plan entry uses planType='normal_plan' and
        # executePrice; 6K's hybrid entry combines regular limit fields
        # with trigger fields and must not be sent as-is.
        if entry.get('triggerPrice') is not None and entry.get('planType') != 'normal_plan':
            findings.append(ContractFinding('entry', 'Trigger entry lacks normal_plan endpoint discriminator'))
        if entry.get('triggerPrice') is not None and 'executePrice' not in entry:
            findings.append(ContractFinding('entry', 'Trigger entry lacks executePrice'))
        if entry.get('tradeSide') == 'open':
            findings.append(ContractFinding('entry', 'tradeSide=open must not be assumed valid in one-way mode'))
        for label, payload in (('stop', candidate.stop), ('target', candidate.target)):
            if payload.get('planType') in ('loss_plan', 'profit_plan'):
                findings.append(ContractFinding(label, 'Do not assume plan subtype is valid submission planType'))
            if payload.get('holdSide') is not None and payload.get('side') is not None:
                findings.append(ContractFinding(label, 'Mixed side/holdSide semantics require endpoint-specific validation'))
        if candidate.executable:
            findings.append(ContractFinding('safety', 'Candidate must remain non-executable'))
        return ContractAudit(tuple(findings))
