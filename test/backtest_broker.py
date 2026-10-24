import csv
from pathlib import Path

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
        symbol="XRP/USDT:USDT",
        candles=1000,
    )

    coordinator = create_strategy_coordinator()

    runner = BacktestRunner(
        strategy_coordinator=coordinator,
        initial_balance=10_000.0,
        risk_percentage=0.05,
        default_risk_reward=3.0,
        default_stop_percentage=0.01,
        breakout_expiry_candles=3,
        diagnostic_csv="backtesting/reports/hilo_macd_diagnostics.csv",
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
    trades_path = Path("backtesting/reports/hilo_macd_trades.csv")
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    from dataclasses import asdict
    with trades_path.open("w", newline="", encoding="utf-8") as stream:
        if result.trades:
            writer = csv.DictWriter(stream, fieldnames=list(asdict(result.trades[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(trade) for trade in result.trades)
        else:
            stream.write("no_closed_trades\\n")
    print(f"Trades CSV: {trades_path.resolve()}")



if __name__ == "__main__":
    main()