"""Shared-capital, single-position TEMA portfolio backtest.

Example:
 python -m test.backtest_tema_portfolio --timeframe 15m --rr 1.5 --candles 1000
"""
import argparse
from collections import defaultdict
from datetime import timedelta

from backtesting.broker import BacktestBroker
from backtesting.data_loader import ExchangeDataLoader
from core.enums.position import PositionSide
from core.enums.trade import ExitReason
from core.models.account import Account
from core.models.candle import Candle
from engine.risk_manager import RiskManager
from risk.limits import RiskLimits
from backtesting.execution import BacktestExecution
from strategies.tema_adx_cmo import TemaAdxCmoStrategy


def select_symbols(exchange, count=15, max_price=15.0):
    """Select liquid USDT linear swaps using a live snapshot, not historical prices."""
    exchange.load_markets()
    tickers = exchange.fetch_tickers()
    eligible = []
    for symbol, market in exchange.markets.items():
        if not (market.get("active", True) and market.get("swap")
                and market.get("linear") and market.get("quote") == "USDT"):
            continue
        base = (market.get("base") or "").upper()
        if base in {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "USD1"}:
            continue
        ticker = tickers.get(symbol, {})
        price = ticker.get("last")
        volume = ticker.get("quoteVolume")
        if price is None or volume is None:
            continue
        try:
            price, volume = float(price), float(volume)
        except (ValueError, TypeError):
            continue
        if 0 < price < max_price and volume > 0:
            eligible.append((volume, symbol, price))
    eligible.sort(key=lambda row: (-row[0], row[1]))
    if len(eligible) < count:
        raise ValueError(f"Only {len(eligible)} eligible symbols found; requested {count}")
    return eligible[:count]


def aggregate(five_minute, minutes):
    """Aggregate only complete, contiguous 5m bars aligned to UTC boundaries."""
    if minutes == 5:
        return list(five_minute)
    n = minutes // 5
    result = []
    for end in range(n - 1, len(five_minute)):
        segment = five_minute[end - n + 1:end + 1]
        start = segment[0].timestamp
        if (start.hour * 60 + start.minute) % minutes:
            continue
        if any(segment[i].timestamp + timedelta(minutes=5) != segment[i + 1].timestamp
               for i in range(n - 1)):
            continue
        result.append(Candle(
            timestamp=start, open=segment[0].open,
            high=max(c.high for c in segment), low=min(c.low for c in segment),
            close=segment[-1].close, volume=sum(c.volume for c in segment),
        ))
    return result


def run(args):
    loader = ExchangeDataLoader(exchange_name="bybit", market_type="swap")
    chosen = select_symbols(loader.exchange, args.symbols, args.max_price)
    print("\nSelected symbols (CURRENT snapshot; not historical price filter):")
    for _, symbol, price in chosen:
        print(f"  {symbol}: {price:.6f} USDT")

    # Fetch once per symbol. Align every market to the SAME 5m timestamps.
    by_symbol = {}
    for _, symbol, _ in chosen:
        print(f"Loading {symbol}...")
        data = loader.load_historical_candles(symbol, "5m", args.candles * 3)
        if len(data) < 100:
            raise ValueError(f"Not enough history for {symbol}")
        by_symbol[symbol] = {c.timestamp: c for c in data}
    common = set.intersection(*(set(d) for d in by_symbol.values()))
    if not common:
        raise ValueError("No common timestamps across all symbols")
    # Require one contiguous aligned interval; no accidental gap bridging.
    end = max(common)
    start = end
    while start - timedelta(minutes=5) in common:
        start -= timedelta(minutes=5)
    timestamps = sorted(t for t in common if start <= t <= end)
    if len(timestamps) < 100:
        raise ValueError("Common contiguous history too short; reduce --candles or change symbols")
    print(f"Shared window: {timestamps[0]} through {timestamps[-1]} ({len(timestamps)} 5m candles)")

    strategy = TemaAdxCmoStrategy(
        leveraged_take_profit_roi=(0.152 * args.rr if args.rr is not None else 0.12),
    )
    minutes = {"5m": 5, "15m": 15, "30m": 30, "1h": 60}[args.timeframe]
    broker = BacktestBroker(balance=args.capital)
    account = Account(account_id="PORTFOLIO", currency="USDT",
                      initial_balance=args.capital, balance=args.capital)
    risk = RiskManager(account, risk_percentage=args.risk, default_risk_reward=3.0,
                       limits=RiskLimits(leverage=args.leverage))
    execution = BacktestExecution(broker, risk)
    histories = defaultdict(list)
    signal_histories = defaultdict(list)
    completed = []
    skipped = 0
    signals = 0
    active_symbol = None

    for ts in timestamps:
        close_time = ts + timedelta(minutes=5)
        # First process the currently open position's bar, then all closed signals.
        if active_symbol is not None:
            closed = broker.process_candle(active_symbol, by_symbol[active_symbol][ts])
            if closed is not None:
                completed.append(closed)
                active_symbol = None
        candidates = []
        for symbol in sorted(by_symbol):
            histories[symbol].append(by_symbol[symbol][ts])
            if (close_time.hour * 60 + close_time.minute) % minutes:
                continue
            count = minutes // 5
            segment = histories[symbol][-count:]
            if len(segment) < count:
                continue
            if (segment[0].timestamp.hour * 60 + segment[0].timestamp.minute) % minutes:
                continue
            signal_histories[symbol].append(Candle(
                timestamp=segment[0].timestamp,
                open=segment[0].open, high=max(c.high for c in segment),
                low=min(c.low for c in segment), close=segment[-1].close,
                volume=sum(c.volume for c in segment),
            ))
            bars = signal_histories[symbol]
            if active_symbol == symbol and strategy.use_reversal_exit:
                trade = broker.get_open_trade(symbol)
                if trade:
                    exit_now = (strategy.should_exit_long(bars, len(bars)-1)
                                if trade.side == PositionSide.LONG
                                else strategy.should_exit_short(bars, len(bars)-1))
                    if exit_now:
                        completed.append(broker.close_trade(
                            symbol, bars[-1].close, close_time, ExitReason.STRATEGY_EXIT))
                        active_symbol = None
            signal = strategy.generate_signal(bars, len(bars)-1)
            if signal:
                signals += 1
                candidates.append((symbol, signal))
        if active_symbol is not None:
            skipped += len(candidates)
            continue
        # Deterministic tie-breaking; one entry maximum per timestamp.
        for i, (symbol, signal) in enumerate(candidates):
            pending = execution.create_pending_entry(signal, symbol, args.timeframe)
            trade = execution.execute_current_close(pending, by_symbol[symbol][ts])
            if trade is not None:
                active_symbol = symbol
                skipped += len(candidates) - i - 1
                break

    gross = sum(t.gross_pnl or 0.0 for t in completed)
    net_closed = sum(t.net_pnl or 0.0 for t in completed)
    wins = sum((t.net_pnl or 0.0) > 0 for t in completed)
    losses = sum((t.net_pnl or 0.0) < 0 for t in completed)
    print("\n===== SHARED-CAPITAL TEMA PORTFOLIO =====")
    print(f"Symbols: {len(by_symbol)} | TF: {args.timeframe} | RR: {args.rr if args.rr else 0.12/0.152:.4f}")
    print(f"Initial capital: {args.capital:.2f} | Risk/trade: {args.risk:.2%} | Leverage cap: {risk.limits.leverage}x")
    print(f"Signals: {signals} | Skipped while occupied: {skipped}")
    print(f"Closed trades: {len(completed)} | Wins: {wins} | Losses: {losses}")
    print(f"Net win rate: {100*wins/len(completed) if completed else 0:.2f}%")
    print(f"Gross closed PnL (without fees): {gross:.2f} USDT")
    print(f"Net closed PnL (after fees): {net_closed:.2f} USDT")
    print(f"Total fees (including any open entry): {broker.total_fees:.2f} USDT")
    print(f"Realized balance: {broker.balance:.2f} USDT")
    print(f"Return on initial capital: {100*(broker.balance/args.capital-1):.2f}%")
    if active_symbol:
        print(f"OPEN POSITION: {active_symbol}; unrealized PnL excluded")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", choices=["5m", "15m", "30m", "1h"], default="15m")
    parser.add_argument("--rr", type=float, default=None)
    parser.add_argument("--candles", type=int, default=1000, help="15m-equivalent candle count")
    parser.add_argument("--symbols", type=int, default=25)
    parser.add_argument("--max-price", type=float, default=15.0)
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--risk", type=float, default=0.10)
    parser.add_argument("--leverage", type=float, default=15.0)
    args = parser.parse_args()
    if args.candles < 100 or args.symbols < 1 or args.capital <= 0 or not 0 < args.risk <= 1 or args.leverage < 1:
        parser.error("Invalid candles, symbols, capital, or risk")
    if args.rr is not None and not 0 < args.rr <= 20:
        parser.error("--rr must be > 0 and <= 20")
    run(args)


if __name__ == "__main__":
    main()
