from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DrawdownStatus:
    start_of_day_balance: float
    current_balance: float
    drawdown_amount: float
    drawdown_percentage: float
    limit_percentage: float
    triggered: bool


class DailyDrawdownGuard:

    def __init__(
        self,
        limit_percentage: float = 0.05,
    ):
        if limit_percentage <= 0:
            raise ValueError(
                "limit_percentage must be greater than 0"
            )

        self.limit_percentage = limit_percentage

        self._day: date | None = None
        self._start_of_day_balance: float | None = None
        self._triggered = False

    def update(
        self,
        current_balance: float,
        current_day: date,
    ) -> DrawdownStatus:

        if current_balance < 0:
            raise ValueError(
                "current_balance cannot be negative"
            )

        # Start a new daily cycle.
        if (
            self._day is None
            or current_day != self._day
        ):
            self._day = current_day
            self._start_of_day_balance = current_balance
            self._triggered = False

        if self._start_of_day_balance is None:
            raise RuntimeError(
                "Start-of-day balance is not initialized"
            )

        start_balance = self._start_of_day_balance

        if start_balance <= 0:
            raise ValueError(
                "start-of-day balance must be greater than 0"
            )

        drawdown_amount = max(
            0.0,
            start_balance - current_balance,
        )

        drawdown_percentage = (
            drawdown_amount / start_balance
        )

        if drawdown_percentage >= self.limit_percentage:
            self._triggered = True

        return DrawdownStatus(
            start_of_day_balance=start_balance,
            current_balance=current_balance,
            drawdown_amount=drawdown_amount,
            drawdown_percentage=drawdown_percentage,
            limit_percentage=self.limit_percentage,
            triggered=self._triggered,
        )

    @property
    def is_triggered(self) -> bool:
        return self._triggered