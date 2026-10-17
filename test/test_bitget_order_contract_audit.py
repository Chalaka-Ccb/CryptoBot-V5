import unittest
from live.live_order_lifecycle import OrderIntent
from live.bitget_order_contract_audit import BitgetOrderContractAuditor


class ContractAuditTests(unittest.TestCase):
    def intent(self, side):
        return OrderIntent('phase6s-test', 'SOL/USDT:USDT', side, 1.0, 100.0,
                           99.0 if side == 'long' else 101.0,
                           103.0 if side == 'long' else 97.0)

    def test_long_flags_legacy_payload(self):
        audit = BitgetOrderContractAuditor().audit(self.intent('long'))
        self.assertFalse(audit.passed)
        self.assertFalse(audit.executable)
        self.assertTrue(any(f.name == 'entry' for f in audit.findings))

    def test_short_flags_legacy_payload(self):
        audit = BitgetOrderContractAuditor().audit(self.intent('short'))
        self.assertFalse(audit.passed)
        self.assertTrue(any(f.name == 'stop' for f in audit.findings))

    def test_protection_flagged(self):
        audit = BitgetOrderContractAuditor().audit(self.intent('long'))
        self.assertTrue(any(f.name == 'target' for f in audit.findings))


if __name__ == '__main__':
    unittest.main()
