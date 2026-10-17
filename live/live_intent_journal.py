"""Phase 6H: durable, fail-closed intent journal. No exchange writes.

SQLite reservation is committed before a future network submission. An
unresolved reservation always blocks another entry, including after restart.
"""
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from live.live_order_lifecycle import OrderIntent

SCHEMA = """
CREATE TABLE IF NOT EXISTS intents (
 client_id TEXT PRIMARY KEY,
 payload TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN
  ('reserved','submitted_unknown','acknowledged','protected','closed','cancelled','halted')),
 exchange_order_id TEXT,
 created_utc TEXT NOT NULL,
 updated_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS only_one_active_intent
ON intents((1))
WHERE status NOT IN ('closed','cancelled');
"""
ACTIVE = ("reserved", "submitted_unknown", "acknowledged", "protected", "halted")


class LiveIntentJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def reserve(self, intent: OrderIntent):
        if not isinstance(intent, OrderIntent):
            raise TypeError("OrderIntent required")
        now = self._now()
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute(
                "INSERT INTO intents(client_id,payload,status,created_utc,updated_utc)"
                " VALUES(?,?,'reserved',?,?)",
                (intent.client_id, json.dumps(asdict(intent), sort_keys=True), now, now))
            self.db.execute("COMMIT")
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise RuntimeError("Entry reservation rejected: duplicate ID or unresolved intent") from None

    def get(self, client_id):
        row = self.db.execute(
            "SELECT payload,status,exchange_order_id FROM intents WHERE client_id=?",
            (client_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown client ID")
        return {"intent": OrderIntent(**json.loads(row[0])),
                "status": row[1], "exchange_order_id": row[2]}

    def unresolved(self):
        return [row[0] for row in self.db.execute(
            "SELECT client_id FROM intents WHERE status NOT IN ('closed','cancelled')")]

    def mark_submission_uncertain(self, client_id):
        """Persist immediately BEFORE a future exchange write.

        Any exception, timeout or crash after this transition requires
        exchange reconciliation; never blindly resubmit.
        """
        self._transition(client_id, "reserved", "submitted_unknown")

    def acknowledge(self, client_id, order_id):
        if not isinstance(order_id, str) or not order_id.strip():
            raise ValueError("Exchange order ID required")
        self._transition(client_id, "submitted_unknown", "acknowledged", order_id)

    def mark_protected(self, client_id):
        """Only after separate exchange-side SL/TP verification."""
        self._transition(client_id, "acknowledged", "protected")

    def mark_closed(self, client_id):
        """Only after separate exchange reconciliation proves flat and no plans."""
        self._transition(client_id, "protected", "closed")

    def mark_cancelled(self, client_id):
        """Only after separate exchange reconciliation proves no fill/no plans."""
        self._transition(client_id, "reserved", "cancelled")

    def halt(self, client_id):
        current = self.get(client_id)["status"]
        if current in ("closed", "cancelled"):
            raise RuntimeError("Cannot halt a terminal intent")
        self._transition(client_id, current, "halted")

    def _transition(self, client_id, old, new, order_id=None):
        cur = self.db.execute(
            "UPDATE intents SET status=?,exchange_order_id=COALESCE(?,exchange_order_id),"
            "updated_utc=? WHERE client_id=? AND status=?",
            (new, order_id, self._now(), client_id, old))
        if cur.rowcount != 1:
            raise RuntimeError("Invalid state transition; reconciliation required")
