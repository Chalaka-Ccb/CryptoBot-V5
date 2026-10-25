from dataclasses import dataclass


@dataclass(frozen=True)
class NR7Config:
    lookback: int = 7

    # Price offset added/subtracted from NR7 boundaries.
    # Exchange tick-size conversion should be handled later
    # by the execution layer.
    trigger_offset: float = 0.0

    # Optional stop buffer beyond the opposite side.
    stop_buffer: float = 0.0
