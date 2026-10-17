import unittest
from types import SimpleNamespace
from live.bitget_plan_inspector import BitgetPlanInspector, PLAN_TYPES

class FakeExchange:
    def __init__(self):
        self.calls = []
        self.responses = {}
    def privateMixGetV2MixOrderOrdersPlanPending(self, params):
        self.calls.append(params.copy())
        return self.responses.get(params['planType'], {'code':'00000','data':{'entrustedList':[], 'endId':''}})

class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.exchange = FakeExchange()
        self.gateway = SimpleNamespace(config=SimpleNamespace(symbol='SOL/USDT:USDT'),
            exchange=self.exchange, _market={'id':'SOLUSDT'})
        self.inspector = BitgetPlanInspector(self.gateway)
    def test_null_list_empty_cursor_is_empty(self):
        for kind in PLAN_TYPES:
            self.exchange.responses[kind] = {
                'code': '00000',
                'data': {'entrustedList': None, 'endId': None},
            }
        self.assertEqual(self.inspector.fetch_all(), [])

    def test_null_list_nonempty_cursor_rejected(self):
        self.exchange.responses['normal_plan'] = {
            'code': '00000',
            'data': {'entrustedList': None, 'endId': '123'},
        }
        with self.assertRaisesRegex(RuntimeError, 'Ambiguous null'):
            self.inspector.fetch_all()

    def test_missing_list_still_rejected(self):
        self.exchange.responses['normal_plan'] = {
            'code': '00000', 'data': {'endId': ''},
        }
        with self.assertRaisesRegex(RuntimeError, 'Missing plan-order list'):
            self.inspector.fetch_all()

    def test_empty_all_categories(self):
        self.assertTrue(self.inspector.assert_no_pending_plans())
        self.assertEqual({x['planType'] for x in self.exchange.calls}, set(PLAN_TYPES))
    def test_existing_trigger_blocks(self):
        self.exchange.responses['normal_plan']={'code':'00000','data':{'entrustedList':[
            {'orderId':'a','symbol':'SOLUSDT','status':'not_trigger','planType':'normal_plan','triggerPrice':'100','size':'2'}]}}
        with self.assertRaisesRegex(RuntimeError, 'blocked'):
            self.inspector.assert_no_pending_plans()
    def test_existing_tpsl_blocks(self):
        self.exchange.responses['profit_loss']={'code':'00000','data':{'entrustedList':[
            {'orderId':'a','symbol':'SOLUSDT','status':'not_trigger','planType':'loss_plan'}]}}
        with self.assertRaises(RuntimeError): self.inspector.assert_no_pending_plans()
    def test_bad_code_blocks(self):
        self.exchange.responses['track_plan']={'code':'error','data':{'entrustedList':[]}}
        with self.assertRaises(RuntimeError): self.inspector.fetch_all()
    def test_missing_list_blocks(self):
        self.exchange.responses['normal_plan']={'code':'00000','data':{}}
        with self.assertRaises(RuntimeError): self.inspector.fetch_all()
    def test_wrong_symbol_blocks(self):
        self.exchange.responses['normal_plan']={'code':'00000','data':{'entrustedList':[
            {'orderId':'x','symbol':'BTCUSDT','status':'not_trigger'}]}}
        with self.assertRaises(RuntimeError): self.inspector.fetch_all()
    def test_missing_endpoint_blocks(self):
        self.gateway.exchange = object()
        with self.assertRaises(RuntimeError): self.inspector.fetch_all()
    def test_pagination_failure_blocks(self):
        row={'orderId':'a','symbol':'SOLUSDT','status':'not_trigger'}
        self.exchange.responses['normal_plan']={'code':'00000','data':{'entrustedList':[row]*100}}
        with self.assertRaises(RuntimeError): self.inspector.fetch_all()
    def test_no_write_methods(self):
        self.assertFalse(hasattr(self.inspector,'submit_order'))
        self.assertFalse(hasattr(self.inspector,'cancel_order'))

if __name__=='__main__': unittest.main()
