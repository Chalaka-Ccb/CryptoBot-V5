"""Read-only, bounded Bitget/CCXT fill history; never proof of completeness."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

def positive(v, name, zero=False):
    if isinstance(v,bool): raise RuntimeError('Invalid '+name)
    try: n=Decimal(str(v))
    except (InvalidOperation,ValueError,TypeError): raise RuntimeError('Invalid '+name) from None
    if not n.is_finite() or (n<0 if zero else n<=0): raise RuntimeError('Invalid '+name)
    return n

@dataclass(frozen=True)
class Fill:
    trade_id:str
    order_id:str
    side:str
    amount:Decimal
    price:Decimal
    fee_usdt:Decimal|None
    timestamp_ms:int

@dataclass(frozen=True)
class FillReport:
    order_id:str
    fills:tuple[Fill,...]
    amount:Decimal
    fee_usdt:Decimal|None
    history_complete:bool=False
    live_execution_authorized:bool=False

class BitgetFillHistory:
    def __init__(self,gateway):
        if gateway.config.symbol!='SOL/USDT:USDT': raise ValueError('Unsupported symbol')
        self.gateway=gateway
    def inspect(self,order_id,side,*,since_ms,until_ms,limit=100):
        if not isinstance(order_id,str) or not order_id or side not in ('buy','sell'):
            raise ValueError('Order ID and side required')
        if any(isinstance(x,bool) or not isinstance(x,int) for x in (since_ms,until_ms,limit)):
            raise ValueError('Invalid window')
        if since_ms<0 or until_ms<=since_ms or not 1<=limit<=100:
            raise ValueError('Invalid window')
        self.gateway.connect()
        ex=self.gateway.exchange
        if not ex.has.get('fetchMyTrades'): raise RuntimeError('Trade history unsupported')
        rows=ex.fetch_my_trades('SOL/USDT:USDT',since_ms,limit)
        if not isinstance(rows,list) or len(rows)>=limit:
            raise RuntimeError('Incomplete or invalid history page')
        fills=[];seen=set()
        for t in rows:
            if not isinstance(t,dict) or t.get('symbol')!='SOL/USDT:USDT':
                raise RuntimeError('Invalid trade')
            ts=t.get('timestamp')
            if isinstance(ts,bool) or not isinstance(ts,int) or ts<since_ms:
                raise RuntimeError('Invalid timestamp')
            if ts>=until_ms: continue
            tid=t.get('id'); oid=t.get('order')
            if not isinstance(tid,str) or not tid or not isinstance(oid,str) or not oid or tid in seen:
                raise RuntimeError('Invalid or duplicate trade ID')
            seen.add(tid)
            if t.get('side') not in ('buy','sell'): raise RuntimeError('Invalid side')
            amount=positive(t.get('amount'),'amount')
            price=positive(t.get('price'),'price')
            fee=t.get('fee'); fee_usdt=None
            if fee is not None:
                if not isinstance(fee,dict): raise RuntimeError('Invalid fee')
                value=positive(fee.get('cost'),'fee',True)
                if not isinstance(fee.get('currency'),str) or not fee['currency']:
                    raise RuntimeError('Invalid fee currency')
                if fee['currency']=='USDT': fee_usdt=value
            if oid==order_id:
                if t['side']!=side: raise RuntimeError('Fill side mismatch')
                fills.append(Fill(tid,oid,side,amount,price,fee_usdt,ts))
        total_fee=sum((f.fee_usdt for f in fills),Decimal(0)) if all(f.fee_usdt is not None for f in fills) else None
        return FillReport(order_id,tuple(fills),sum((f.amount for f in fills),Decimal(0)),total_fee)
