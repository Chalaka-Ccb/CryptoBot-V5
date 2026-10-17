"""Run authenticated read-only local safety snapshots; Ctrl+C to stop.

No order submission, cancellation, leverage changes or incident clearing.
"""
import argparse
import time
from live.bitget_gateway import BitgetGateway
from live.config import LiveConfig
from live.bitget_plan_inspector import BitgetPlanInspector
from live.live_intent_journal import LiveIntentJournal
from live.bitget_emergency_controller import EmergencyController
from live.bitget_safety_supervisor import BitgetSafetySupervisor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--journal', required=True, help='Existing live SQLite intent journal path')
    parser.add_argument('--incidents', required=True, help='Persistent emergency SQLite path')
    parser.add_argument('--interval', type=int, default=30)
    args = parser.parse_args()
    if args.interval < 10:
        parser.error('--interval must be at least 10 seconds')
    gateway = BitgetGateway(LiveConfig(mode='paper', risk_percentage=0.005, leverage=5))
    journal = LiveIntentJournal(args.journal)
    emergency = EmergencyController(args.incidents, journal)
    supervisor = BitgetSafetySupervisor(None, emergency, journal)
    inspector = BitgetPlanInspector(gateway)
    try:
        while True:
            try:
                print(supervisor.check_account_snapshot(gateway, inspector), flush=True)
            except Exception as exc:
                print('UNVERIFIED EXCHANGE STATE; NO ENTRIES. Error:', type(exc).__name__, flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('Read-only supervisor stopped; no exchange orders changed.')
    finally:
        emergency.close()
        journal.close()


if __name__ == '__main__':
    main()
