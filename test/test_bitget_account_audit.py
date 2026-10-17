import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from live.bitget_account_audit import AccountModeEvidence, BitgetAccountAudit


def evidence(margin='isolated', mode='one_way', source='verified_exchange_response'):
    return AccountModeEvidence(margin, mode, source)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Mock()
        self.gateway.config = SimpleNamespace(symbol='SOL/USDT:USDT')
        self.gateway.connect.return_value = dict(swap=True, linear=True, settle='USDT', active=True)
        self.gateway.fetch_positions.return_value = []
        self.orders = Mock()
        self.orders.fetch_open_orders.return_value = []
        self.plans = Mock()
        self.plans.fetch_all.return_value = []
        self.audit = BitgetAccountAudit(self.gateway, order_adapter=self.orders, plan_inspector=self.plans)

    def test_clean_account_only_review_ready(self):
        result = self.audit.run(evidence())
        self.assertTrue(result.ready_for_review)
        self.assertFalse(result.live_execution_authorized)

    def test_missing_mode_evidence(self):
        with self.assertRaises(RuntimeError): self.audit.run(None)

    def test_unverified_mode_evidence(self):
        with self.assertRaises(RuntimeError): self.audit.run(evidence(source='assumed'))

    def test_cross_margin_rejected(self):
        with self.assertRaises(RuntimeError): self.audit.run(evidence(margin='cross'))

    def test_hedge_mode_rejected(self):
        with self.assertRaises(RuntimeError): self.audit.run(evidence(mode='hedge'))

    def test_existing_order_rejected(self):
        self.orders.fetch_open_orders.return_value = [object()]
        with self.assertRaises(RuntimeError): self.audit.run(evidence())

    def test_existing_plan_rejected(self):
        self.plans.fetch_all.return_value = [object()]
        with self.assertRaises(RuntimeError): self.audit.run(evidence())

    def test_existing_position_rejected(self):
        self.gateway.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts':1.0}]
        with self.assertRaises(RuntimeError): self.audit.run(evidence())

    def test_unknown_position_rejected(self):
        self.gateway.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','contracts':None}]
        with self.assertRaises(RuntimeError): self.audit.run(evidence())

    def test_invalid_market_rejected(self):
        self.gateway.connect.return_value['linear'] = False
        with self.assertRaises(RuntimeError): self.audit.run(evidence())


if __name__ == '__main__':
    unittest.main()
