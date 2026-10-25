import argparse
from datetime import datetime, timedelta, timezone

from backtesting.data_loader import ExchangeDataLoader
from backtesting.runner import BacktestRunner
from backtesting.strategy_setup import (
    create_strategy_coordinator,
)


def main():
    parser = argparse.ArgumentParser(description="Run one fixed 30-day XRP backtest")
    parser.add_argument("--period", type=int, choices=(1, 2, 3), required=True,
                        help="1=oldest, 2=middle, 3=latest")
    args = parser.parse_args()
    anchor = datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc)
    start = anchor - timedelta(days=(4 - args.period) * 30)
    end = start + timedelta(days=30)
    print(f"PERIOD {args.period}/3: {start.isoformat()} to {end.isoformat()} (exclusive)")


    loader = ExchangeDataLoader(
        exchange_name="bybit",
        market_type="swap",
    )

    market_data = loader.load_dated_5m_market_data(
        symbol="XRP/USDT:USDT", start=start, end=end, warmup_candles=250,
    )

    coordinator = create_strategy_coordinator()

    runner = BacktestRunner(
        strategy_coordinator=coordinator,
        initial_balance=10_000.0,
        risk_percentage=0.05,
        default_risk_reward=3.0,
        default_stop_percentage=0.01,
        breakout_expiry_candles=3,
        trade_start_time=start,
    )

    result = runner.run(
        market_data
    )

    print()
    print("===== BACKTEST RESULT =====")
    print(f"Symbol: {result.symbol}")
    print(f"Total trades: {result.total_trades}")
    print(f"Winning trades: {result.winning_trades}")
    print(f"Losing trades: {result.losing_trades}")
    print(f"Win rate: {result.win_rate:.2f}%")
    print(f"Total PnL: {result.total_pnl:.2f} USDT")
    print(f"Return: {result.return_percentage:.2f}%")
    print(f"Final balance: {result.final_balance:.2f} USDT")


if __name__ == "__main__":
    main()