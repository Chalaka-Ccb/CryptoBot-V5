from enum import Enum


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class ExitReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STRATEGY_EXIT = "strategy_exit"
    TRAILING_STOP = "trailing_stop"
    DAILY_DRAWDOWN = "daily_drawdown"
    MANUAL = "manual"
    UNKNOWN = "unknown"