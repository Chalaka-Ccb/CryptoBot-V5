"""Run exactly one strategy. Example: python -m test.backtest_individual --strategy fib --candles 1000"""
import argparse
from backtesting.data_loader import ExchangeDataLoader
from backtesting.runner import BacktestRunner
from engine.strategy_coordinator import StrategyCoordinator
from strategies.supertrend_dynamic import SupertrendStrategy
from strategies.tema_adx_cmo import TemaAdxCmoStrategy
from strategies.fibonacci_scalping import FibonacciScalpingStrategy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=("supertrend", "tema", "fib"), required=True)
    parser.add_argument("--symbol", default="BTC/USDT:USDT")
    parser.add_argument("--candles", type=int, default=1000,
                        help="15m candle count; 1m download uses 15x")
    args = parser.parse_args()
    loader = ExchangeDataLoader(exchange_name="bybit", market_type="swap")
    market_data = loader.load_market_data(
        symbol=args.symbol, candles=args.candles,
        include_1m=args.strategy == "fib",
    )
    strategies_15m = []
    strategies_1m = []
    if args.strategy == "supertrend":
        strategies_15m.append(SupertrendStrategy())
    elif args.strategy == "tema":
        strategies_15m.append(TemaAdxCmoStrategy())
    else:
        strategies_1m.append(FibonacciScalpingStrategy())
    coordinator = StrategyCoordinator(
        strategies_15m=strategies_15m, strategies_5m=[],
        strategies_1m=strategies_1m,
    )
    runner = BacktestRunner(
        strategy_coordinator=coordinator, initial_balance=10000.0,
        risk_percentage=0.02, default_risk_reward=3.0,
        default_stop_percentage=0.01, breakout_expiry_candles=3,
        execution_timeframe="1m" if args.strategy == "fib" else "5m",
    )
    print(f"Testing ONLY {args.strategy} on {args.symbol}")
    result = runner.run(market_data)
    print("\n===== INDIVIDUAL BACKTEST =====")
    print(f"Strategy: {args.strategy}")
    print(f"Trades: {result.total_trades}")
    print(f"Wins: {result.winning_trades}; losses: {result.losing_trades}")
    print(f"Win rate: {result.win_rate:.2f}%")
    print(f"Net PnL: {result.total_pnl:.2f} USDT")
    print(f"Net return: {result.return_percentage:.2f}%")
    print(f"Final balance: {result.final_balance:.2f} USDT")


if __name__ == "__main__":
    main()
