"""Phase 7D: durable fail-closed incident controller. No exchange writes.

Incident persistence happens before journal halt. A failed journal halt still
leaves a durable incident that blocks entry on restart. Do not interpret an
incident as an exchange-side position close or cancellation.
"""
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

UNSAFE = frozenset({
    'UNKNOWN_CHILD_ORDER', 'POSITION_FILL_MISMATCH',
    'FILLED_PROTECTION_UNVERIFIED', 'RECONCILIATION_ERROR',
})

@dataclass(frozen=True)
class EmergencyIncident:
    client_id: str
    reason: str
    position_amount: str
    status: str = 'manual_action_required'
    live_execution_authorized: bool = False

class EmergencyController:
    def __init__(self, path, journal):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS emergency_incidents (
            client_id TEXT PRIMARY KEY, reason TEXT NOT NULL,
            position_amount TEXT NOT NULL, status TEXT NOT NULL,
            created_utc TEXT NOT NULL)''')
        self.journal = journal

    def close(self):
        self.db.close()

    def unresolved(self):
        return [r[0] for r in self.db.execute(
            "SELECT client_id FROM emergency_incidents WHERE status='manual_action_required'")]

    def assert_entry_blocked_if_unsafe(self):
        if self.unresolved() or self.journal.unresolved():
            raise RuntimeError('Unresolved journal/incident: all entries blocked')
        return True  # Not authorization to submit: other preflight gates remain.

    def handle(self, report):
        if report.status not in UNSAFE:
            raise ValueError('No qualifying unsafe reconciliation status')
        cid = report.client_id
        if not isinstance(cid, str) or not cid:
            raise ValueError('Missing client ID')
        amount = str(report.position_amount)
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('''INSERT OR IGNORE INTO emergency_incidents
                (client_id,reason,position_amount,status,created_utc)
                VALUES(?,?,?,'manual_action_required',?)''',
                (cid,report.status,amount,now))
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            raise
        try:
            self.journal.halt(cid)
        except Exception as exc:
            raise RuntimeError('Incident persisted; journal halt failed; manual recovery required') from exc
        return EmergencyIncident(cid,report.status,amount)

    def prepare_manual_response(self, client_id):
        row = self.db.execute('''SELECT reason,position_amount,status
            FROM emergency_incidents WHERE client_id=?''',(client_id,)).fetchone()
        if not row:
            raise KeyError('No incident')
        return {
            'client_id':client_id,
            'reason':row[0],
            'reported_position_amount':row[1],
            'status':row[2],
            'instructions':[
                'Stop all automated entries and inspect Bitget positions immediately.',
                'Inspect pending entry triggers and exchange-side SL/TP orders.',
                'If exposure is unprotected, use the exchange interface to manage or close it safely.',
                'Reconcile fills, orders and flat/clear state before any manual incident resolution.'
            ],
            'automatic_cancel_or_close':False,
            'live_execution_authorized':False,
        }
