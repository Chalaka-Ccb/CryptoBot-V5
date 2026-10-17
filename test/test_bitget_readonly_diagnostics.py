import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from live.bitget_readonly_diagnostics import BitgetReadOnlyDiagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.exchange = SimpleNamespace(
            id='bitget', version='test-version',
            fetch_positions=lambda: None,
            fetch_open_orders=lambda: None,
            privateMixGetV2MixOrderOrdersPlanPending=lambda: None)
        self.gateway = Mock()
        self.gateway.config = SimpleNamespace(symbol='SOL/USDT:USDT')
        self.gateway.exchange = self.exchange
        self.gateway.connect.return_value = dict(
            id='SOLUSDT', swap=True, linear=True, settle='USDT', active=True)

    def test_reports_methods_without_calling_them(self):
        report = BitgetReadOnlyDiagnostics(self.gateway).inspect()
        self.assertEqual(len(report.read_methods), 3)
        self.assertFalse(report.live_execution_authorized)

    def test_missing_method_reported(self):
        self.exchange.privateMixGetV2MixOrderOrdersPlanPending = None
        report = BitgetReadOnlyDiagnostics(self.gateway).inspect()
        self.assertIn('privateMixGetV2MixOrderOrdersPlanPending', report.missing_methods)

    def test_wrong_exchange_fails(self):
        self.exchange.id = 'binance'
        with self.assertRaises(RuntimeError):
            BitgetReadOnlyDiagnostics(self.gateway).inspect()

    def test_wrong_market_fails(self):
        self.gateway.connect.return_value['linear'] = False
        with self.assertRaises(RuntimeError):
            BitgetReadOnlyDiagnostics(self.gateway).inspect()

    def test_wrong_symbol_fails(self):
        self.gateway.config.symbol = 'BTC/USDT:USDT'
        with self.assertRaises(RuntimeError):
            BitgetReadOnlyDiagnostics(self.gateway).inspect()

    def test_missing_market_id_fails(self):
        del self.gateway.connect.return_value['id']
        with self.assertRaises(RuntimeError):
            BitgetReadOnlyDiagnostics(self.gateway).inspect()


if __name__ == '__main__':
    unittest.main()
