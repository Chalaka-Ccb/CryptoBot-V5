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
        symbol="BTC/USDT:USDT",
        candles=100,
    )

    coordinator = create_strategy_coordinator()

    runner = BacktestRunner(
        strategy_coordinator=coordinator,
        initial_balance=10_000.0,
    )

    result = runner.run(
        market_data
    )

    print()
    print("===== RESULT =====")
    print(
        f"Trades: {result.total_trades}"
    )
    print(
        f"Balance: {result.final_balance}"
    )


if __name__ == "__main__":
    main()