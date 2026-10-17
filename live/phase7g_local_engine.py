"""Phase 7G: integrated local read-only shadow engine. No exchange writes."""
import argparse
import json
import logging
import signal
import time
from pathlib import Path

LOG = logging.getLogger('local_shadow')

def snapshot_is_clear(snapshot):
    """Do not use entry_blocked: it is intentionally True in read-only mode."""
    if not isinstance(snapshot, dict) or snapshot.get('live_execution_authorized') is not False or snapshot.get('entry_blocked') is not True:
        return False
    fields=('open_positions','ordinary_open_orders','pending_plan_orders','unresolved_intents','unresolved_incidents')
    return all(type(snapshot.get(k)) is int and snapshot[k] == 0 for k in fields)

class LocalShadowSession:
    def __init__(self, gateway, inspector, supervisor, shadow):
        self.gateway=gateway;self.inspector=inspector;self.supervisor=supervisor;self.shadow=shadow
        self.latest_snapshot=None
        # Override the callback so each shadow tick must consume a fresh verified snapshot.
        self.shadow.safety_check=self.safety_clear

    def safety_clear(self):
        return snapshot_is_clear(self.latest_snapshot)

    def tick(self):
        self.latest_snapshot=None
        snapshot=self.supervisor.check_account_snapshot(self.gateway,self.inspector)
        self.latest_snapshot=snapshot
        if not snapshot_is_clear(snapshot):
            return {'account':snapshot,'shadow_status':'BLOCKED_ACCOUNT_STATE','proposal':None,
                    'live_execution_authorized':False}
        result=self.shadow.tick()
        return {'account':snapshot,'shadow_status':result.status,
                'candle_timestamp':result.candle_timestamp,'proposal':result.proposal,
                'live_execution_authorized':False}

    def run(self, interval, *, max_cycles=None, sleep=time.sleep):
        if interval < 10: raise ValueError('interval must be >=10 seconds')
        cycles=0
        while max_cycles is None or cycles < max_cycles:
            cycles+=1
            try:
                report=self.tick()
                print(json.dumps(report,sort_keys=True),flush=True)
            except Exception as exc:
                self.latest_snapshot=None
                LOG.exception('UNVERIFIED EXCHANGE STATE; local engine remains read-only and blocked')
                print(json.dumps({'shadow_status':'ERROR_BLOCKED','error_type':type(exc).__name__,
                                  'live_execution_authorized':False}),flush=True)
            if max_cycles is not None and cycles >= max_cycles: break
            sleep(interval)

def main():
    p=argparse.ArgumentParser(description='Local read-only shadow engine; NEVER sends orders')
    p.add_argument('--journal',required=True)
    p.add_argument('--incidents',required=True)
    p.add_argument('--shadow-db',required=True)
    p.add_argument('--interval',type=int,default=30)
    p.add_argument('--once',action='store_true')
    args=p.parse_args()
    if args.interval<10:p.error('interval must be at least 10 seconds')
    paths=[Path(x).expanduser().resolve() for x in (args.journal,args.incidents,args.shadow_db)]
    if len(set(paths))!=3:p.error('journal, incidents and shadow-db must be distinct files')
    logging.basicConfig(level=logging.WARNING)
    from live.bitget_gateway import BitgetGateway
    from live.config import LiveConfig
    from live.bitget_plan_inspector import BitgetPlanInspector
    from live.live_intent_journal import LiveIntentJournal
    from live.bitget_emergency_controller import EmergencyController
    from live.bitget_safety_supervisor import BitgetSafetySupervisor
    from live.phase7f_shadow import ShadowEngine
    config=LiveConfig(mode='paper',risk_percentage=0.005,leverage=5)
    gateway=BitgetGateway(config)
    journal=LiveIntentJournal(paths[0])
    emergency=None;shadow=None
    try:
        emergency=EmergencyController(paths[1],journal)
        supervisor=BitgetSafetySupervisor(None,emergency,journal)
        inspector=BitgetPlanInspector(gateway)
        shadow=ShadowEngine(gateway,journal,emergency,db_path=paths[2],config=config)
        session=LocalShadowSession(gateway,inspector,supervisor,shadow)
        try:session.run(args.interval,max_cycles=1 if args.once else None)
        except KeyboardInterrupt:print('Stopped safely. No exchange orders submitted or changed.')
    finally:
        if shadow:shadow.close()
        if emergency:emergency.close()
        journal.close()

if __name__=='__main__':main()
