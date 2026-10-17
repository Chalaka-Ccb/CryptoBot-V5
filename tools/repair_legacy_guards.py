"""Repair Phase 6F guards per method. Offline, no exchange access."""
import ast
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'brokers/live_broker.py': ('LEGACY LIVE EXECUTION DISABLED: use guarded Live V1 only',
        ('configure_symbol', 'submit_prepared', 'submit_order', 'update_stop_loss', 'cancel_order')),
    'engine/live_engine.py': ('LEGACY LIVE ENGINE DISABLED: do not use for trading',
        ('initialize', 'run_once', 'run', '_submit', '_enter', '_close_managed', '_expire_breakouts', '_manage_position')),
}

def repair(path, message, names):
    original = path.read_text(encoding='utf-8')
    tree = ast.parse(original, filename=str(path))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    class_name = 'LiveBroker' if path.name == 'live_broker.py' else 'LiveEngine'
    matches = [n for n in classes if n.name == class_name]
    if len(matches) != 1:
        raise RuntimeError(f'Expected one {class_name} in {path}')
    methods = [n for n in matches[0].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    changes = []
    for name in names:
        found = [n for n in methods if n.name == name]
        if len(found) != 1:
            raise RuntimeError(f'Expected exactly one {class_name}.{name} in {path}')
        method = found[0]
        if not method.body:
            raise RuntimeError(f'Empty method: {name}')
        first = method.body[0]
        if isinstance(first, ast.Raise) and isinstance(first.exc, ast.Call) and isinstance(first.exc.func, ast.Name) and first.exc.func.id == 'RuntimeError' and first.exc.args and isinstance(first.exc.args[0], ast.Constant) and first.exc.args[0].value == message:
            continue
        # Insert before first executable statement (after docstring if present).
        index = 1 if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str) else 0
        anchor = method.body[index] if index < len(method.body) else None
        if anchor is None:
            raise RuntimeError(f'No insertion anchor for {name}')
        changes.append((anchor.lineno, f'        raise RuntimeError({message!r})\n'))
    if not changes:
        return False
    lines = original.splitlines(keepends=True)
    for lineno, snippet in sorted(changes, reverse=True):
        lines.insert(lineno - 1, snippet)
    updated = ''.join(lines)
    ast.parse(updated, filename=str(path))
    backup = path.with_suffix(path.suffix + '.phase6f2.bak')
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(updated, encoding='utf-8')
    return True

def main():
    # Validate entire operation before writing any file.
    for relative, (_, names) in TARGETS.items():
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f'Missing {relative}')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        class_name = 'LiveBroker' if path.name == 'live_broker.py' else 'LiveEngine'
        matches = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
        if len(matches) != 1 or any(sum(isinstance(m, ast.FunctionDef) and m.name == name for m in matches[0].body) != 1 for name in names):
            raise RuntimeError(f'Unexpected method structure in {relative}; no files changed')
    for relative, (message, names) in TARGETS.items():
        changed = repair(ROOT / relative, message, names)
        print(f'{relative}: {"repaired" if changed else "already guarded"}')
    print('Guard repair complete. No API calls made.')

if __name__ == '__main__':
    main()
