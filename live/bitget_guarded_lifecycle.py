"""Phase 6V: offline-only journal + fill/protection gate orchestration.

No exchange writes. Does not automatically repair unprotected positions.
"""
from live.live_order_lifecycle import OrderIntent, OfflineOrderLifecycle, OrderState


class GuardedLifecycle:
    def __init__(self, journal, gate):
        self.journal = journal
        self.gate = gate
        self.lifecycle = OfflineOrderLifecycle()
        self.client_id = None
        if journal.unresolved():
            raise RuntimeError('Unresolved journal entry; restart requires reconciliation')

    def reserve_and_acknowledge_mock(self, intent: OrderIntent, order_id: str):
        """For tests ONLY: simulate the transition normally driven by a verified exchange acknowledgment."""
        if self.client_id is not None:
            raise RuntimeError('Active intent')
        self.journal.reserve(intent)
        self.client_id = intent.client_id
        self.lifecycle.plan(intent)
        self.journal.mark_submission_uncertain(intent.client_id)
        self.lifecycle.acknowledge(intent.client_id, order_id)
        self.journal.acknowledge(intent.client_id, order_id)

    def observe_fill(self, cumulative_contracts):
        self._active()
        try:
            self.lifecycle.report_fill(self.client_id, cumulative_contracts)
            return self.lifecycle.state
        except Exception:
            self._halt()
            raise

    def confirm_protection(self):
        self._active()
        if self.lifecycle.filled <= 0:
            raise RuntimeError('Cannot protect unfilled entry')
        try:
            report = self.gate.check(self.lifecycle.intent, self.lifecycle.filled)
            self.lifecycle.report_protection(
                self.client_id, float(report.filled_contracts),
                stop_confirmed=True, target_confirmed=True)
            self.journal.mark_protected(self.client_id)
            return report
        except Exception:
            self._halt()
            raise

    def _active(self):
        if self.client_id is None or self.lifecycle.state == OrderState.HALTED:
            raise RuntimeError('No active healthy intent')

    def _halt(self):
        self.lifecycle.halt('Manual exchange reconciliation required')
        if self.client_id is not None:
            self.journal.halt(self.client_id)
