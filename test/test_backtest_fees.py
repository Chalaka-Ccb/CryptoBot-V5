from datetime import datetime, timezone

from backtesting.broker import BacktestBroker
from core.enums.position import PositionSide
from core.enums.trade import ExitReason


def test_round_trip_fees():
    broker = BacktestBroker(balance=10000.0)

    trade = broker.open_trade(
        symbol="BTC/USDT:USDT",
        side=PositionSide.LONG,
        quantity=1.0,
        entry_price=1000.0,
        stop_loss=900.0,
        take_profit=1100.0,
        strategy="fee_test",
        timestamp=datetime.now(timezone.utc),
    )

    assert round(trade.entry_fee, 4) == 0.6
    assert round(broker.balance, 4) == 9999.4

    closed = broker.close_trade(
        symbol="BTC/USDT:USDT",
        exit_price=1100.0,
        exit_time=datetime.now(timezone.utc),
        exit_reason=ExitReason.TAKE_PROFIT,
    )

    assert round(closed.exit_fee, 4) == 0.66
    assert round(closed.fees, 4) == 1.26
    assert round(closed.gross_pnl, 4) == 100.0
    assert round(closed.net_pnl, 4) == 98.74
    assert round(broker.balance, 4) == 10098.74
    assert round(broker.total_fees, 4) == 1.26