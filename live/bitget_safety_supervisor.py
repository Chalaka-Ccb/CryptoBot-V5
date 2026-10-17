"""Phase 7E: read-only, fail-closed safety supervision.

No exchange writes. The caller MUST keep the entry gate locked on any
failure or unresolved incident. EmergencyController does not flatten positions.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

UNSAFE = frozenset({
    'UNKNOWN_CHILD_ORDER', 'POSITION_FILL_MISMATCH',
    'FILLED_PROTECTION_UNVERIFIED', 'RECONCILIATION_ERROR',
})


def _quantity(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RuntimeError('Invalid position quantity') from None
    if not number.is_finite() or number < 0:
        raise RuntimeError('Invalid position quantity')
    return number


@dataclass(frozen=True)
class SupervisorResult:
    client_id: str
    status: str
    incident_recorded: bool
    observed_utc: str
    entry_blocked: bool = True
    live_execution_authorized: bool = False


class BitgetSafetySupervisor:
    def __init__(self, reconciler, emergency, journal):
        self.reconciler = reconciler
        self.emergency = emergency
        self.journal = journal

    def check_once(self, client_id, *, plan_order_id, since_ms, until_ms):
        """One iteration. No implicit retries, no clearing journal/incident."""
        if not isinstance(client_id, str) or not client_id:
            raise ValueError('Client ID required')
        # A persisted incident remains blocking even when a later read looks safe.
        if client_id in self.emergency.unresolved():
            return SupervisorResult(client_id, 'PERSISTED_INCIDENT', True,
                                    datetime.now(timezone.utc).isoformat())
        try:
            report = self.reconciler.inspect(
                client_id, plan_order_id=plan_order_id,
                since_ms=since_ms, until_ms=until_ms)
            if report.client_id != client_id:
                raise RuntimeError('Reconciler returned wrong client ID')
            status = report.status
            if status in UNSAFE or report.emergency_attention:
                self.emergency.handle(report)
                return SupervisorResult(client_id, status, True,
                                        datetime.now(timezone.utc).isoformat())
            # Even a protected snapshot is not proof of complete history.
            return SupervisorResult(client_id, status, False,
                                    datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            # Persist incident before surfacing failure. If persistence itself
            # fails, fail closed by propagating an exception to the caller.
            fallback = type('IncidentReport', (), {
                'client_id': client_id,
                'status': 'RECONCILIATION_ERROR',
                'position_amount': 'unknown',
            })()
            try:
                self.emergency.handle(fallback)
            except Exception as persistence_exc:
                raise RuntimeError(
                    'Supervisor failed; incident persistence unconfirmed; '
                    'stop process and manually inspect Bitget'
                ) from persistence_exc
            return SupervisorResult(client_id, 'RECONCILIATION_ERROR', True,
                                    datetime.now(timezone.utc).isoformat())

    def check_account_snapshot(self, gateway, inspector):
        """Independent account snapshot; any exposure blocks entries."""
        market = gateway.connect()
        if market.get('id') != 'SOLUSDT' or market.get('swap') is not True or market.get('linear') is not True:
            raise RuntimeError('Unexpected market')
        positions = gateway.fetch_positions()
        if not isinstance(positions, list):
            raise RuntimeError('Unreliable position response')
        active = 0
        for p in positions:
            if not isinstance(p, dict) or p.get('symbol') != 'SOL/USDT:USDT':
                raise RuntimeError('Unexpected position')
            active += int(_quantity(p.get('contracts')) > 0)
        ex = gateway.exchange
        if not ex.has.get('fetchOpenOrders'):
            raise RuntimeError('Open-order reads unavailable')
        orders = ex.fetch_open_orders('SOL/USDT:USDT')
        plans = inspector.fetch_all()
        if not isinstance(orders, list) or not isinstance(plans, list):
            raise RuntimeError('Unreliable order/plan snapshot')
        return {
            'open_positions': active,
            'ordinary_open_orders': len(orders),
            'pending_plan_orders': len(plans),
            'unresolved_intents': len(self.journal.unresolved()),
            'unresolved_incidents': len(self.emergency.unresolved()),
            'entry_blocked': True,
            'live_execution_authorized': False,
        }
