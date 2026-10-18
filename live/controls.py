"""Operator controls. STOP pauses entries; FLATTEN requires order-manager action."""
from pathlib import Path

class Controls:
    def __init__(self, root="."):
        self.root = Path(root)

    def entries_blocked(self):
        return any((self.root / name).exists() for name in ("STOP", "FLATTEN", "LOCKED"))

    def flatten_requested(self):
        return (self.root / "FLATTEN").exists()

    def locked(self):
        return (self.root / "LOCKED").exists()

    def lock(self, reason):
        (self.root / "LOCKED").write_text(str(reason) + "\n", encoding="utf-8")
