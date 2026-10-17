import unittest
from decimal import Decimal
from unittest.mock import Mock
from live.bitget_plan_inspector import PlanSnapshot
from live.bitget_protection_verifier import BitgetProtectionVerifier
from live.live_order_lifecycle import OrderIntent


def plan(subtype, price, size=2, oid=None, category='profit_loss'):
    return PlanSnapshot(category, oid or subtype, 'SOLUSDT', 'live', subtype,
                        Decimal(str(price)), Decimal(str(size)))


class ProtectionVerifierTests(unittest.TestCase):
    def setUp(self):
        self.intent = OrderIntent('test-1', 'SOL/USDT:USDT', 'long', 2, 100, 99, 103)
        self.inspector = Mock()
        self.verifier = BitgetProtectionVerifier(self.inspector)

    def test_valid_explicit_pair(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99), plan('profit_plan', 103)]
        result = self.verifier.verify(self.intent, 2)
        self.assertEqual(result['covered_contracts'], '2')

    def test_partial_fill_coverage(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99, 1), plan('profit_plan', 103, 1)]
        self.verifier.verify(self.intent, 1)

    def test_missing_tp(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99)]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, 2)

    def test_wrong_price(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 98), plan('profit_plan', 103)]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, 2)

    def test_undercoverage(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99, 1), plan('profit_plan', 103)]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, 2)

    def test_ambiguous_subtype(self):
        self.inspector.fetch_all.return_value = [plan('stop_loss', 99), plan('profit_plan', 103)]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, 2)

    def test_other_pending_plan_blocks(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99, category='normal_plan'), plan('profit_plan', 103)]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, 2)

    def test_duplicate_ids(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99, oid='same'), plan('profit_plan', 103, oid='same')]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, 2)

    def test_nan_fill_rejected(self):
        self.inspector.fetch_all.return_value = [plan('loss_plan', 99), plan('profit_plan', 103)]
        with self.assertRaises(RuntimeError): self.verifier.verify(self.intent, float('nan'))


if __name__ == '__main__':
    unittest.main()
