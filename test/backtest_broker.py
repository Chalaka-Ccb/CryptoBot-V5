"""Run the unchanged Setup1234 strategy alone on one selected timeframe."""
import argparse
from backtesting.data_loader import ExchangeDataLoader
from backtesting.runner import BacktestRunner
from engine.strategy_coordinator import StrategyCoordinator
from strategies.pullback.setup_1234 import Setup1234Strategy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", choices=("1m", "5m", "15m"), default="5m")
    parser.add_argument("--symbol", default="SOL/USDT:USDT")
    parser.add_argument("--candles", type=int, default=3500)
    parser.add_argument("--risk", type=float, default=0.02)
    args = parser.parse_args()
    if args.candles < 250:
        parser.error("--candles must be >= 250")
    loader = ExchangeDataLoader(exchange_name="bybit", market_type="swap")
    market_data = loader.load_market_data(
        symbol=args.symbol, candles=args.candles, timeframe=args.timeframe)
    strategy = Setup1234Strategy()
    coordinator = StrategyCoordinator(
        strategies_15m=[strategy] if args.timeframe == "15m" else [],
        strategies_5m=[strategy] if args.timeframe != "15m" else [],
    )
    runner = BacktestRunner(
        strategy_coordinator=coordinator,
        timeframe=args.timeframe,
        initial_balance=10_000.0,
        risk_percentage=args.risk,
        default_risk_reward=3.0,
        default_stop_percentage=0.01,
        breakout_expiry_candles=3,
    )
    result = runner.run(market_data)
    print("\n===== BACKTEST RESULT =====")
    print(f"Symbol: {result.symbol}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Total trades: {result.total_trades}")
    print(f"Winning trades: {result.winning_trades}")
    print(f"Losing trades: {result.losing_trades}")
    print(f"Win rate: {result.win_rate:.2f}%")
    print(f"Net PnL (fees included): {result.total_pnl:.2f} USDT")
    print(f"Net return: {result.return_percentage:.2f}%")
    print(f"Final balance: {result.final_balance:.2f} USDT")


if __name__ == "__main__":
    main()
