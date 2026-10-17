import tempfile, unittest
from unittest.mock import Mock
from datetime import datetime,timezone
from types import SimpleNamespace
from live.phase7f_shadow import ShadowEngine
from core.models.signal import EntryTiming,SignalSide

class TestShadow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.gateway=Mock();self.journal=Mock();self.incidents=Mock()
  self.journal.unresolved.return_value=[];self.incidents.unresolved.return_value=[]
  self.gateway.fetch_positions.return_value=[];self.gateway.exchange.fetch_open_orders.return_value=[]
  self.gateway.fetch_closed_candles.return_value=[SimpleNamespace(timestamp=datetime(2026,10,17,tzinfo=timezone.utc))]*250
  self.gateway.fetch_available_balance.return_value=SimpleNamespace(total_usdt=100,free_usdt=100)
  self.strategy=Mock();self.strategy.generate_signal.return_value=None
  self.engine=ShadowEngine(self.gateway,self.journal,self.incidents,db_path=self.tmp.name+'/shadow.db',strategy=self.strategy,safety_check=lambda:True)
  self.addCleanup(self.engine.close)
 def signal(self):
  return SimpleNamespace(strategy='bollinger_channel_rebound',entry_timing=EntryTiming.BREAKOUT,
   side=SignalSide.LONG,trigger_price=100,stop_loss=99,take_profit=102)
 def test_no_signal(self):self.assertEqual(self.engine.tick().status,'NO_SIGNAL')
 def test_dedupe(self):self.engine.tick();self.assertEqual(self.engine.tick().status,'ALREADY_EVALUATED')
 def test_shadow_proposal(self):
  self.strategy.generate_signal.return_value=self.signal();r=self.engine.tick()
  self.assertEqual(r.status,'SHADOW_PROPOSAL');self.assertTrue(r.entry_blocked);self.assertFalse(r.live_execution_authorized)
  self.assertEqual(r.proposal['risk_budget_usdt'],'0.500')
 def test_journal_blocks(self):self.journal.unresolved.return_value=['id'];self.assertEqual(self.engine.tick().status,'BLOCKED_LOCAL_STATE')
 def test_incidents_block(self):self.incidents.unresolved.return_value=['id'];self.assertEqual(self.engine.tick().status,'BLOCKED_LOCAL_STATE')
 def test_unverified_safety_blocks(self):self.engine.safety_check=lambda:False;self.assertEqual(self.engine.tick().status,'BLOCKED_SAFETY_UNVERIFIED')
 def test_open_orders_block(self):self.gateway.exchange.fetch_open_orders.return_value=[{'id':'x'}];self.assertEqual(self.engine.tick().status,'BLOCKED_EXCHANGE_ACTIVITY')
 def test_open_position_blocks(self):self.gateway.fetch_positions.return_value=[{'symbol':'SOL/USDT:USDT','contracts':1}];self.assertEqual(self.engine.tick().status,'BLOCKED_EXCHANGE_ACTIVITY')
 def test_invalid_levels_rejected(self):
  s=self.signal();s.stop_loss=101;self.strategy.generate_signal.return_value=s
  with self.assertRaises(RuntimeError):self.engine.tick()
 def test_insufficient_candles(self):
  self.gateway.fetch_closed_candles.return_value=[]
  with self.assertRaises(RuntimeError):self.engine.tick()
 def test_no_exchange_writes(self):
  self.strategy.generate_signal.return_value=self.signal();self.engine.tick()
  self.gateway.exchange.create_order.assert_not_called();self.journal.reserve.assert_not_called()
if __name__=='__main__':unittest.main()
