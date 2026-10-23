from backtesting.data_loader import ExchangeDataLoader
from backtesting.runner import BacktestRunner
from backtesting.strategy_setup import (
    create_strategy_coordinator,
)


def main():

    loader = ExchangeDataLoader(
        exchange_name="bybit",
        market_type="swap",
    )

    market_data = loader.load_market_data(
        symbol="SOL/USDT:USDT",
        candles=14 * 24 * 4 + 1,  # ~14 days of 15m bars; loader also fetches 5m bars
    )

    coordinator = create_strategy_coordinator()

    runner = BacktestRunner(
        strategy_coordinator=coordinator,
        initial_balance=10_000.0,
        risk_percentage=0.05,
        default_risk_reward=3.0,
        default_stop_percentage=0.01,
        breakout_expiry_candles=3,
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