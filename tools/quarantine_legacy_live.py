"""One-time, fail-closed migration for deprecated live order writer.

Run from repository root. Backups are saved before editing. This script does not
import exchange code or make network requests.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BROKER = ROOT / 'brokers' / 'live_broker.py'
ENGINE = ROOT / 'engine' / 'live_engine.py'
OLD_TEST = ROOT / 'test' / 'test_live_engine.py'
QUARANTINED_TEST = ROOT / 'test' / 'legacy_live_engine_test.py'


def insert_guard(path, marker, guard):
    source = path.read_text(encoding='utf-8')
    if guard.strip() in source:
        return False
    if source.count(marker) != 1:
        raise RuntimeError(f'Expected exactly one marker in {path}; refusing to modify')
    updated = source.replace(marker, marker + guard, 1)
    backup = path.with_suffix(path.suffix + '.phase6f.bak')
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(updated, encoding='utf-8')
    return True


def main():
    if not BROKER.is_file() or not ENGINE.is_file():
        raise RuntimeError('Run inside CryptoBot-V5; legacy files not found')
    edits = [
        (BROKER, '    def configure_symbol(self, symbol):\n',
         '        raise RuntimeError("LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only")\n'),
        (BROKER, '    def submit_prepared(self, order, request):\n',
         '        raise RuntimeError("LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only")\n'),
        (BROKER, '    def update_stop_loss(self, position, price):\n',
         '        raise RuntimeError("LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only")\n'),
        (BROKER, '    def cancel_order(self, order_id):\n',
         '        raise RuntimeError("LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only")\n'),
        (ENGINE, '    def initialize(self):\n',
         '        raise RuntimeError("LEGACY LIVE ENGINE DISABLED: do not use for trading")\n'),
        (ENGINE, '    def run_once(self, now=None):\n',
         '        raise RuntimeError("LEGACY LIVE ENGINE DISABLED: do not use for trading")\n'),
    ]
    # Validate all markers before any edits.
    for path, marker, guard in edits:
        content = path.read_text(encoding='utf-8')
        if guard.strip() not in content and content.count(marker) != 1:
            raise RuntimeError(f'Marker mismatch in {path}; no changes made')
    for path, marker, guard in edits:
        if insert_guard(path, marker, guard):
            print('Guard installed:', path.relative_to(ROOT), marker.strip())
    if OLD_TEST.exists():
        if QUARANTINED_TEST.exists():
            raise RuntimeError('Both old and quarantined legacy test files exist; resolve manually')
        OLD_TEST.rename(QUARANTINED_TEST)
        print('Legacy test quarantined:', QUARANTINED_TEST.relative_to(ROOT))
    elif not QUARANTINED_TEST.exists():
        print('WARNING: legacy test not found; verify repository layout')
    print('Phase 6F complete. Live V1 order submission remains disabled.')


if __name__ == '__main__':
    main()
