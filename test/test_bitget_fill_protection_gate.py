import unittest
from unittest.mock import Mock
from live.live_order_lifecycle import OrderIntent
from live.bitget_fill_protection_gate import BitgetFillProtectionGate


class FillGateTests(unittest.TestCase):
    def setUp(self):
        self.intent = OrderIntent('phase6u','SOL/USDT:USDT','long',2,100,99,103)
        self.gateway = Mock()
        self.gateway.fetch_positions.return_value = [{'symbol':'SOL/USDT:USDT','side':'long','contracts':1}]
        self.verifier = Mock()
        self.verifier.verify.return_value = {'covered_contracts':'1','stop_order_id':'sl1','target_order_id':'tp1'}
        self.gate = BitgetFillProtectionGate(self.gateway,self.verifier)

    def test_partial_fill_covered(self):
        result = self.gate.check(self.intent,1)
        self.assertTrue(result.read_only)
        self.assertFalse(result.live_execution_authorized)

    def test_zero_fill_rejected(self):
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,0)

    def test_overfill_rejected(self):
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,3)

    def test_wrong_position_side_rejected(self):
        self.gateway.fetch_positions.return_value[0]['side']='short'
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)

    def test_wrong_position_size_rejected(self):
        self.gateway.fetch_positions.return_value[0]['contracts']=2
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)

    def test_missing_position_rejected(self):
        self.gateway.fetch_positions.return_value=[]
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)

    def test_missing_protection_rejected(self):
        self.verifier.verify.side_effect=RuntimeError('SL missing')
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)

    def test_wrong_coverage_rejected(self):
        self.verifier.verify.return_value['covered_contracts']='0.5'
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)

    def test_same_protection_ids_rejected(self):
        self.verifier.verify.return_value['target_order_id']='sl1'
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)

    def test_unreliable_quantity_rejected(self):
        self.gateway.fetch_positions.return_value[0]['contracts']=float('nan')
        with self.assertRaises(RuntimeError): self.gate.check(self.intent,1)


if __name__ == '__main__':
    unittest.main()
