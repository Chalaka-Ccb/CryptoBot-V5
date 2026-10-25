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
    parser.add_argument("--timeframe", choices=("5m", "15m", "30m", "1h"), default="15m",
                        help="TEMA signal timeframe; 5m execution is retained")
    parser.add_argument("--rr", type=float, default=None,
                        help="TEMA reward/risk; omit for original 0.789:1")
    args = parser.parse_args()
    if args.rr is not None and (args.strategy != "tema" or not (0 < args.rr <= 20)):
        parser.error("--rr requires --strategy tema and a ratio in (0, 20]")
    if args.strategy != "tema" and args.timeframe != "15m":
        parser.error("--timeframe currently applies only to TEMA")
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
        pass  # Dedicated configurable signal timeframe handled by runner.
    else:
        strategies_1m.append(FibonacciScalpingStrategy())
    coordinator = StrategyCoordinator(
        strategies_15m=strategies_15m, strategies_5m=[],
        strategies_1m=strategies_1m,
    )
    tema = (TemaAdxCmoStrategy(
        leveraged_take_profit_roi=(0.152 * args.rr if args.rr is not None else 0.12),
    ) if args.strategy == "tema" else None)
    runner = BacktestRunner(
        strategy_coordinator=coordinator, initial_balance=10000.0,
        risk_percentage=0.02, default_risk_reward=3.0,
        default_stop_percentage=0.01, breakout_expiry_candles=3,
        execution_timeframe="1m" if args.strategy == "fib" else "5m",
        custom_signal_timeframe=args.timeframe if tema else None,
        custom_signal_strategy=tema,
    )
    print(f"Testing ONLY {args.strategy} on {args.symbol}")
    if tema:
        print(f"TEMA signal timeframe: {args.timeframe}; RR: {args.rr if args.rr is not None else 0.12/0.152:.4f}:1")
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
