from dataclasses import dataclass


@dataclass
class Account:
    account_id: str
    currency: str

    initial_balance: float
    balance: float

    used_margin: float = 0.0
    available_balance: float = 0.0

    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be greater than 0")

        if self.balance < 0:
            raise ValueError("balance cannot be negative")

        if self.available_balance == 0.0:
            self.available_balance = self.balance - self.used_margin

    @property
    def equity(self) -> float:
        return self.balance + self.total_unrealized_pnl

    @property
    def total_pnl(self) -> float:
        return self.total_realized_pnl + self.total_unrealized_pnl

    @property
    def return_percentage(self) -> float:
        return (
            (self.equity - self.initial_balance)
            / self.initial_balance
        ) * 100.0

    def update_balance(self, amount: float) -> None:
        self.balance += amount

        if self.balance < 0:
            raise ValueError("account balance cannot be negative")

        self.available_balance = self.balance - self.used_margin