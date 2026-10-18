"""Optional notification hook; notifications must not interrupt execution."""
class Notifier:
    def send(self, message):
        return False  # Telegram integration optional; no secrets or network dependency here.
