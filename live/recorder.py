"""Thread-safe structured event recorder. Secrets must never be passed as fields."""
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone

class Recorder:
    def __init__(self, data_dir="data", log_dir="logs"):
        self.data = Path(data_dir)
        self.logs = Path(log_dir)
        self.data.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("cryptobot.live")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            for handler in (logging.StreamHandler(), RotatingFileHandler(self.logs / "live.log", maxBytes=5_000_000, backupCount=5)):
                handler.setFormatter(fmt)
                self.logger.addHandler(handler)

    @staticmethod
    def _safe(fields):
        forbidden = ("key", "secret", "password", "passphrase", "signature", "token", "authorization")
        return {k: ("[REDACTED]" if any(s in k.lower() for s in forbidden) else v) for k, v in fields.items()}

    def _append(self, path, record):
        try:
            with open(path, "a", encoding="utf-8") as file:
                file.write(json.dumps(record, default=str, separators=(",", ":")) + "\n")
                file.flush()
        except OSError as error:
            self.logger.error("Logging write failed: %s", type(error).__name__)

    def event(self, name, level="INFO", **fields):
        record = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "event": name, **self._safe(fields)}
        self.logger.log(getattr(logging, level.upper(), logging.INFO), "%s %s", name, json.dumps(self._safe(fields), default=str))
        self._append(self.data / "events.jsonl", record)

    def order_call(self, action, **fields):
        self._append(self.data / "orders.jsonl", {"ts": datetime.now(timezone.utc).isoformat(), "action": action, **self._safe(fields)})

    def trade_closed(self, **fields):
        path = self.data / "trades.csv"
        try:
            row = self._safe(fields)
            exists = path.exists() and path.stat().st_size > 0
            with open(path, "a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=list(row))
                if not exists:
                    writer.writeheader()
                writer.writerow(row)
                file.flush()
        except OSError as error:
            self.logger.error("Trade CSV write failed: %s", type(error).__name__)
