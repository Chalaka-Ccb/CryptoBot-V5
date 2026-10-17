import unittest
from unittest.mock import Mock
from decimal import Decimal
from live.bitget_fill_history import BitgetFillHistory
class Tests(unittest.TestCase):
    def setUp(self):
        g=Mock();g.config.symbol='SOL/USDT:USDT';g.exchange.has={'fetchMyTrades':True}
        g.exchange.fetch_my_trades.return_value=[]
        self.g=g;self.reader=BitgetFillHistory(g)
        self.kw=dict(since_ms=1000,until_ms=2000)
    def trade(self,**changes):
        x=dict(id='f1',order='o1',symbol='SOL/USDT:USDT',side='buy',amount=2,price=100,timestamp=1500,fee={'cost':0.1,'currency':'USDT'})
        x.update(changes);return x
    def test_empty_not_complete(self):
        r=self.reader.inspect('o1','buy',**self.kw)
        self.assertFalse(r.history_complete);self.assertFalse(r.live_execution_authorized)
    def test_match_and_fee(self):
        self.g.exchange.fetch_my_trades.return_value=[self.trade(),self.trade(id='f2',order='other')]
        r=self.reader.inspect('o1','buy',**self.kw)
        self.assertEqual(r.amount,Decimal(2));self.assertEqual(r.fee_usdt,Decimal('0.1'))
    def test_duplicate_rejected(self):
        self.g.exchange.fetch_my_trades.return_value=[self.trade(),self.trade()]
        with self.assertRaises(RuntimeError):self.reader.inspect('o1','buy',**self.kw)
    def test_full_page_rejected(self):
        self.g.exchange.fetch_my_trades.return_value=[self.trade()]
        with self.assertRaises(RuntimeError):self.reader.inspect('o1','buy',limit=1,**self.kw)
    def test_side_mismatch_rejected(self):
        self.g.exchange.fetch_my_trades.return_value=[self.trade(side='sell')]
        with self.assertRaises(RuntimeError):self.reader.inspect('o1','buy',**self.kw)
    def test_missing_order_id_rejected(self):
        self.g.exchange.fetch_my_trades.return_value=[self.trade(order=None)]
        with self.assertRaises(RuntimeError):self.reader.inspect('o1','buy',**self.kw)
    def test_nan_fee_rejected(self):
        self.g.exchange.fetch_my_trades.return_value=[self.trade(fee={'cost':float('nan'),'currency':'USDT'})]
        with self.assertRaises(RuntimeError):self.reader.inspect('o1','buy',**self.kw)
if __name__=='__main__':unittest.main()
