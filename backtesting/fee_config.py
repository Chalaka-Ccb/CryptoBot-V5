from dataclasses import dataclass


@dataclass(frozen=True)
class FeeConfig:
    maker_rate: float = 0.0002
    taker_rate: float = 0.0006

    def __post_init__(self):
        if not 0 <= self.maker_rate < 1:
            raise ValueError("Invalid maker fee rate")

        if not 0 <= self.taker_rate < 1:
            raise ValueError("Invalid taker fee rate")