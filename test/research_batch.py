"""Multi-symbol, multi-timeframe independent strategy research.

Run: python -m test.research_batch --exchange bybit --candles 1500
"""
import argparse
import csv
import json
from pathlib import Path
from types import SimpleNamespace

from backtesting.data_loader import ExchangeDataLoader
from backtesting.research import ResearchRunner
from engine.strategy_coordinator import StrategyCoordinator
from backtesting.strategy_setup import (
    EMACrossoverStrategy, HiLoMACDStrategy, FFFDStrategy,
    BollingerSqueezeStrategy, ChannelReboundStrategy, NR7Strategy,
    WilliamsRStrategy, Setup1234Strategy,
)

TOKENS = ("SOL", "XRP", "BGB", "PI", "POL", "SONIC", "OP",
          "USUAL", "DOGE", "APY", "SUI")
TIMEFRAMES = ("1m", "5m", "15m")


def strategies():
    return [
        EMACrossoverStrategy(),
        HiLoMACDStrategy(),
        FFFDStrategy(min_band_penetration=0.0, stop_mode="EXTREME",
                     use_macd_exhaustion=True, min_reward_risk=2.0,
                     use_long_ema_filter=True, use_short_rsi_filter=True,
                     short_rsi_mode="FALLING", short_rsi_threshold=60.0),
        BollingerSqueezeStrategy(),
        ChannelReboundStrategy(),
        NR7Strategy(),
        WilliamsRStrategy(),
        Setup1234Strategy(),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="bybit")
    parser.add_argument("--candles", type=int, default=1500)
    parser.add_argument("--output", default="research_output")
    parser.add_argument("--tokens", nargs="+", default=list(TOKENS))
    parser.add_argument("--timeframes", nargs="+", default=list(TIMEFRAMES))
    args = parser.parse_args()
    if args.candles < 250:
        parser.error("--candles must be >= 250 for indicator warmup")
    if any(tf not in TIMEFRAMES for tf in args.timeframes):
        parser.error("Supported timeframes: 1m, 5m, 15m")
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    loader = ExchangeDataLoader(args.exchange, "swap")
    loader.exchange.load_markets()
    rows = []
    errors = []
    for token in args.tokens:
        symbol = f"{token}/USDT:USDT"
        if symbol not in loader.exchange.markets:
            errors.append({"symbol": symbol, "error": "Not listed on exchange"})
            continue
        for tf in args.timeframes:
            try:
                candles = loader.load_historical_candles(symbol, tf, args.candles)
                if len(candles) < 220:
                    raise ValueError("Insufficient historical candles")
                data = SimpleNamespace(symbol=symbol, candles_5m=candles,
                                       candles_15m=candles,
                                       **({"candles_" + tf: candles} if tf in ("1m", "30m") else {}))
                for strategy in strategies():
                    coordinator = StrategyCoordinator(
                        strategies_15m=[strategy] if tf == "15m" else [],
                        strategies_5m=[strategy] if tf != "15m" else [])
                    result = ResearchRunner(coordinator, timeframe=tf).run(data)
                    name = strategy.name
                    prefix = folder / f"{token}_{tf}_{name}"
                    result.export(str(prefix))
                    completed = [t for t in result.trades if t.exit_time is not None]
                    gross = sum(t.gross_pnl for t in completed)
                    fees = sum(t.fees for t in completed)
                    net = gross - fees
                    wins = sum(t.net_pnl > 0 for t in completed)
                    gross_wins = sum(t.gross_pnl > 0 for t in completed)
                    rows.append({
                        "symbol": symbol, "timeframe": tf, "strategy": name,
                        "signals": len(result.signals), "filled": len(result.trades),
                        "closed": len(completed), "open": len(result.trades) - len(completed),
                        "gross_wins": gross_wins, "net_wins": wins,
                        "gross_win_rate": round(100 * gross_wins / len(completed), 2) if completed else 0,
                        "net_win_rate": round(100 * wins / len(completed), 2) if completed else 0,
                        "gross_pnl": round(gross, 4), "fees": round(fees, 4),
                        "net_pnl": round(net, 4),
                        "profit_factor_net": round(
                            sum(max(0, t.net_pnl) for t in completed) /
                            abs(sum(min(0, t.net_pnl) for t in completed)), 4)
                            if any(t.net_pnl < 0 for t in completed) else None,
                    })
                    print(f"{symbol} {tf} {name}: {len(completed)} closed, net {net:.2f}")
            except Exception as exc:
                errors.append({"symbol": symbol, "timeframe": tf, "error": str(exc)})
                print(f"SKIPPED {symbol} {tf}: {exc}")
    if rows:
        with (folder / "summary.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (folder / "errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    print(f"Finished: {len(rows)} strategy/timeframe results; {len(errors)} errors. See {folder}")


if __name__ == "__main__":
    main()
