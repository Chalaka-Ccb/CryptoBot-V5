"""Atomic state persistence for restart recovery."""
import json
import os
from pathlib import Path

class StateStore:
    def __init__(self, path="data/live_state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.path.exists():
            return {"last_processed_candle": None, "pending": None, "trade": None, "stats": {}}
        with self.path.open(encoding="utf-8") as file:
            return json.load(file)

    def save(self, state):
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(state, file, default=str)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, self.path)
