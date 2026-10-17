"""Phase 7F: local shadow evaluation only. No orders or intent reservations."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from live.config import LiveConfig
from live.bitget_gateway import BitgetGateway
from engine.strategy_coordinator import StrategyCoordinator
from strategies.bollinger.channel_rebound import ChannelReboundStrategy
from core.models.signal import EntryTiming


def dec(v):
    try: d = Decimal(str(v))
    except (ValueError, TypeError, InvalidOperation): raise ValueError('Invalid numeric input') from None
    if not d.is_finite() or d <= 0: raise ValueError('Expected positive finite number')
    return d


@dataclass(frozen=True)
class ShadowResult:
    status: str
    candle_timestamp: str | None
    proposal: dict | None
    entry_blocked: bool = True
    live_execution_authorized: bool = False


class ShadowEngine:
    def __init__(self, gateway, journal, incidents, *, db_path, config=None, strategy=None, safety_check=None):
        self.config = config or LiveConfig(mode='paper', risk_percentage=0.005, leverage=5)
        if self.config.mode != 'paper' or self.config.risk_percentage > .005 or self.config.leverage > 5:
            raise ValueError('Phase 7F enforces paper mode, <=0.5% risk and <=5x leverage')
        self.gateway, self.journal, self.incidents = gateway, journal, incidents
        self.strategy = strategy or ChannelReboundStrategy()
        self.safety_check = safety_check
        path=Path(db_path);path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(str(path),timeout=10,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS shadow_events (candle_ts TEXT PRIMARY KEY, outcome TEXT NOT NULL, proposal_json TEXT, created_utc TEXT NOT NULL)')

    def close(self): self.db.close()

    def tick(self):
        # Never evaluate if any source of account state cannot be verified.
        if self.journal.unresolved() or self.incidents.unresolved():
            return ShadowResult('BLOCKED_LOCAL_STATE',None,None)
        if self.safety_check is None or self.safety_check() is not True:
            return ShadowResult('BLOCKED_SAFETY_UNVERIFIED',None,None)
        positions=self.gateway.fetch_positions()
        orders=self.gateway.exchange.fetch_open_orders(self.config.symbol)
        if not isinstance(positions,list) or not isinstance(orders,list):
            raise RuntimeError('Unreliable exchange account state')
        if any(not isinstance(p,dict) or p.get('symbol') != self.config.symbol for p in positions):
            raise RuntimeError('Unexpected position scope')
        if any(dec(p.get('contracts')) > 0 for p in positions if p.get('contracts') is not None) or orders:
            return ShadowResult('BLOCKED_EXCHANGE_ACTIVITY',None,None)
        # Pending plan orders must be checked by safety_check (Phase 7E).
        candles=self.gateway.fetch_closed_candles('15m',250)
        if len(candles)<200: raise RuntimeError('Insufficient closed 15m candle history')
        timestamp=candles[-1].timestamp.isoformat()
        if self.db.execute('SELECT 1 FROM shadow_events WHERE candle_ts=?',(timestamp,)).fetchone():
            return ShadowResult('ALREADY_EVALUATED',timestamp,None)
        evaluation=StrategyCoordinator([self.strategy],[]).evaluate(candles,[])
        proposal=None
        if evaluation.signal is not None:
            s=evaluation.signal
            if s.strategy != 'bollinger_channel_rebound' or s.entry_timing != EntryTiming.BREAKOUT:
                raise RuntimeError('Unexpected strategy signal')
            entry,sl,tp=map(dec,(s.trigger_price,s.stop_loss,s.take_profit))
            if (s.side.value=='long' and not sl<entry<tp) or (s.side.value=='short' and not tp<entry<sl):
                raise RuntimeError('Invalid protective levels')
            balance=self.gateway.fetch_available_balance()
            equity=dec(balance.total_usdt);free=dec(balance.free_usdt)
            risk=equity*dec(self.config.risk_percentage)
            amount=risk/abs(entry-sl)
            # Cap notional by available margin * 5x. Decimal calculations remain indicative;
            # exchange contract size/precision and min order requirements are NOT validated.
            amount=min(amount,free*dec(self.config.leverage)/entry)
            if amount<=0: raise RuntimeError('No usable position size')
            proposal=dict(symbol=self.config.symbol,side=s.side.value,timeframe='15m',
                          entry=str(entry),stop_loss=str(sl),take_profit=str(tp),
                          base_amount_estimate=str(amount),risk_budget_usdt=str(risk),
                          indicative_notional_usdt=str(amount*entry),
                          warning='SHADOW ONLY: quantity is base units, not verified Bitget contracts; no order may be placed')
        outcome='SHADOW_PROPOSAL' if proposal else 'NO_SIGNAL'
        self.db.execute('INSERT INTO shadow_events VALUES (?,?,?,?)',
                        (timestamp,outcome,json.dumps(proposal) if proposal else None,datetime.now(timezone.utc).isoformat()))
        return ShadowResult(outcome,timestamp,proposal)
