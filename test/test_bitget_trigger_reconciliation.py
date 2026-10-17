import unittest
from decimal import Decimal
from unittest.mock import Mock
from live.bitget_plan_inspector import PlanSnapshot
from live.bitget_trigger_reconciliation import BitgetTriggerReconciler


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.journal=Mock()
        self.journal.get.return_value={'intent':Mock(client_id='abc',symbol='SOL/USDT:USDT',entry=100,contracts=1)}
        self.inspector=Mock()
        self.inspector.fetch_all.return_value=[PlanSnapshot('normal_plan','plan1','SOLUSDT','live','normal_plan',Decimal('100'),Decimal('1'))]
        self.reader=BitgetTriggerReconciler(self.journal,self.inspector)

    def test_pending_does_not_prove_execution(self):
        report=self.reader.pending('abc',verified_plan_order_id='plan1')
        self.assertFalse(report.execution_confirmed)
        self.assertFalse(report.live_execution_authorized)

    def test_missing_plan_requires_history(self):
        self.inspector.fetch_all.return_value=[]
        with self.assertRaises(RuntimeError):self.reader.pending('abc',verified_plan_order_id='plan1')

    def test_wrong_price_rejected(self):
        self.inspector.fetch_all.return_value[0]=PlanSnapshot('normal_plan','plan1','SOLUSDT','live','normal_plan',Decimal('99'),Decimal('1'))
        with self.assertRaises(RuntimeError):self.reader.pending('abc',verified_plan_order_id='plan1')

    def test_wrong_size_rejected(self):
        self.inspector.fetch_all.return_value[0]=PlanSnapshot('normal_plan','plan1','SOLUSDT','live','normal_plan',Decimal('100'),Decimal('2'))
        with self.assertRaises(RuntimeError):self.reader.pending('abc',verified_plan_order_id='plan1')

    def test_wrong_type_rejected(self):
        self.inspector.fetch_all.return_value[0]=PlanSnapshot('profit_loss','plan1','SOLUSDT','live','profit_plan',Decimal('100'),Decimal('1'))
        with self.assertRaises(RuntimeError):self.reader.pending('abc',verified_plan_order_id='plan1')


if __name__=='__main__':
    unittest.main()
