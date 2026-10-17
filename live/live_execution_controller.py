"""Phase 6I: offline execution controller; never calls exchange write APIs.

Connects existing durable journal and lifecycle to a deterministic simulated
exchange. This is NOT an adapter for Bitget and cannot submit real orders.
"""
from live.live_order_lifecycle import OfflineOrderLifecycle, OrderState, OrderIntent


class OfflineExecutionController:
    def __init__(self, journal, simulator):
        self.journal = journal
        self.simulator = simulator
        self.lifecycle = OfflineOrderLifecycle()
        self.client_id = None
        # On restart unresolved reservations must be reconciled manually.
        if self.journal.unresolved():
            raise RuntimeError('Unresolved journal entry: reconciliation required; no new order')

    def start(self, intent: OrderIntent):
        if self.client_id is not None:
            raise RuntimeError('Controller already has an order')
        self.journal.reserve(intent)
        self.client_id = intent.client_id
        self.lifecycle.plan(intent)
        # Durable uncertainty must precede even a simulated submission.
        self.journal.mark_submission_uncertain(intent.client_id)
        try:
            order_id = self.simulator.submit(intent)
            self.lifecycle.acknowledge(intent.client_id, order_id)
            self.journal.acknowledge(intent.client_id, order_id)
        except Exception:
            self.lifecycle.halt('Submission uncertain; manual reconciliation required')
            raise
        return order_id

    def update_fill(self, cumulative_contracts):
        self._active()
        try:
            self.lifecycle.report_fill(self.client_id, cumulative_contracts)
        except Exception:
            self._halt()
            raise
        return self.lifecycle.state

    def verify_protection(self):
        self._active()
        try:
            # The simulator must independently report confirmed levels/coverage.
            snapshot = self.simulator.protection(self.client_id)
            intent = self.lifecycle.intent
            if snapshot['stop_loss'] != intent.stop_loss or snapshot['take_profit'] != intent.take_profit:
                raise RuntimeError('Protection price mismatch')
            self.lifecycle.report_protection(
                self.client_id, snapshot['contracts'],
                stop_confirmed=snapshot['stop_confirmed'],
                target_confirmed=snapshot['target_confirmed'])
            self.journal.mark_protected(self.client_id)
        except Exception:
            self._halt()
            raise
        return self.lifecycle.state

    def finish(self):
        self._active()
        if self.lifecycle.state != OrderState.PROTECTED:
            raise RuntimeError('Cannot close unprotected or unresolved order')
        # A real executor must verify position flat, ordinary orders and plans.
        if not self.simulator.is_flat_and_clear(self.client_id):
            self._halt()
            raise RuntimeError('Position/orders/plans not reconciled')
        self.journal.mark_closed(self.client_id)
        self.client_id = None
        self.lifecycle = OfflineOrderLifecycle()

    def _active(self):
        if self.client_id is None or self.lifecycle.state == OrderState.HALTED:
            raise RuntimeError('No active healthy order')

    def _halt(self):
        self.lifecycle.halt('Reconciliation required')
        if self.client_id:
            self.journal.halt(self.client_id)


class SimulatedExchange:
    """Deterministic test double. No network, credentials or CCXT dependency."""
    def __init__(self):
        self.orders = {}
        self.protections = {}
        self.flat = set()
        self.fail_submit = False

    def submit(self, intent):
        if self.fail_submit:
            raise TimeoutError('Simulated submission timeout')
        if intent.client_id in self.orders:
            raise RuntimeError('Duplicate client ID')
        order_id = 'sim-' + intent.client_id
        self.orders[intent.client_id] = order_id
        return order_id

    def protection(self, client_id):
        return self.protections[client_id]

    def is_flat_and_clear(self, client_id):
        return client_id in self.flat
