"""Atomic, versioned paper-only checkpoint. Not an exchange reconciliation system."""
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from core.models.signal import TradingSignal, SignalSide, EntryTiming
from live.paper_execution import PaperState, PaperTrade

VERSION = 1


def _dt(value):
    if value is None:
        return None
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Naive timestamp in checkpoint')
    return result


def save_checkpoint(path, runner):
    path = Path(path)
    p = runner.paper
    signal = None
    if p.signal:
        signal = asdict(p.signal)
        signal['side'] = p.signal.side.value
        signal['entry_timing'] = p.signal.entry_timing.value
    payload = {
        'version': VERSION, 'saved_at': datetime.now(timezone.utc).isoformat(),
        'last_5m': runner.last_5m.isoformat() if runner.last_5m else None,
        'last_15m': runner.last_15m.isoformat() if runner.last_15m else None,
        'started': runner.started, 'state': p.state.value,
        'stop_requested': p.stop_requested, 'balance': p.balance,
        'risk_fraction': p.risk_fraction, 'leverage': p.leverage,
        'fee_rate': p.fee_rate, 'margin_reserve': p.margin_reserve,
        'entry': p.entry, 'quantity': p.quantity, 'signal': signal,
        'trades': [{**asdict(t), 'side': t.side.value} for t in p.trades],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.checkpoint-', suffix='.tmp', delete=False) as f:
            temp = f.name
            json.dump(payload, f, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def load_checkpoint(path, runner):
    """Fail closed on corrupted/mismatched state; caller must inspect gaps before running."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    p = runner.paper
    if data.get('version') != VERSION:
        raise ValueError('Unsupported checkpoint version')
    for field in ('risk_fraction', 'leverage', 'fee_rate', 'margin_reserve'):
        if data[field] != getattr(p, field):
            raise ValueError(f'Checkpoint configuration mismatch: {field}')
    state = PaperState(data['state'])
    signal = data['signal']
    if signal:
        signal = TradingSignal(**{**signal, 'side': SignalSide(signal['side']),
                                  'entry_timing': EntryTiming(signal['entry_timing'])})
    if (state in (PaperState.PENDING, PaperState.OPEN)) != (signal is not None):
        raise ValueError('Inconsistent checkpoint state/signal')
    if state == PaperState.OPEN and (data['entry'] <= 0 or data['quantity'] <= 0):
        raise ValueError('Invalid open position in checkpoint')
    from risk.validation import finite_number
    balance = finite_number('balance', data['balance'], positive=True)
    entry = finite_number('entry', data['entry'])
    quantity = finite_number('quantity', data['quantity'])
    if entry < 0 or quantity < 0:
        raise ValueError('Invalid entry or quantity')
    last5, last15 = _dt(data['last_5m']), _dt(data['last_15m'])
    trades = [PaperTrade(**{**t, 'side': SignalSide(t['side'])}) for t in data['trades']]
    p.balance, p.entry, p.quantity = balance, entry, quantity
    p.signal, p.state, p.stop_requested = signal, state, bool(data['stop_requested'])
    p.trades = trades
    runner.last_5m, runner.last_15m, runner.started = last5, last15, bool(data['started'])
