import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from live.bitget_verified_account_mode import BitgetVerifiedAccountMode


class AccountModeTests(unittest.TestCase):
    def setUp(self):
        self.gateway = Mock()
        self.gateway.config = SimpleNamespace(symbol='SOL/USDT:USDT')
        self.gateway.connect.return_value = {'id':'SOLUSDT'}
        self.gateway.exchange.privateMixGetV2MixAccountAccount.return_value = {
            'code':'00000', 'data':{'marginCoin':'USDT','marginMode':'isolated','posMode':'one_way_mode'}}
        self.reader = BitgetVerifiedAccountMode(self.gateway)

    def test_valid(self):
        result = self.reader.fetch()
        self.assertEqual(result.position_mode,'one_way')
        self.assertFalse(result.live_execution_authorized)
        self.gateway.exchange.privateMixGetV2MixAccountAccount.assert_called_once_with({
            'symbol':'SOLUSDT','productType':'USDT-FUTURES','marginCoin':'USDT'})

    def test_cross_rejected(self):
        self.gateway.exchange.privateMixGetV2MixAccountAccount.return_value['data']['marginMode']='crossed'
        with self.assertRaises(RuntimeError):self.reader.fetch()

    def test_hedge_rejected(self):
        self.gateway.exchange.privateMixGetV2MixAccountAccount.return_value['data']['posMode']='hedge_mode'
        with self.assertRaises(RuntimeError):self.reader.fetch()

    def test_missing_field_rejected(self):
        del self.gateway.exchange.privateMixGetV2MixAccountAccount.return_value['data']['posMode']
        with self.assertRaises(RuntimeError):self.reader.fetch()

    def test_api_error_rejected(self):
        self.gateway.exchange.privateMixGetV2MixAccountAccount.return_value['code']='40001'
        with self.assertRaises(RuntimeError):self.reader.fetch()

    def test_wrong_coin_rejected(self):
        self.gateway.exchange.privateMixGetV2MixAccountAccount.return_value['data']['marginCoin']='BTC'
        with self.assertRaises(RuntimeError):self.reader.fetch()

    def test_missing_endpoint_rejected(self):
        self.gateway.exchange.privateMixGetV2MixAccountAccount=None
        with self.assertRaises(RuntimeError):self.reader.fetch()

    def test_wrong_market_rejected(self):
        self.gateway.connect.return_value['id']='BTCUSDT'
        with self.assertRaises(RuntimeError):self.reader.fetch()


if __name__=='__main__':
    unittest.main()
