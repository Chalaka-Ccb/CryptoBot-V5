"""Diagnose the full XRP squeeze baseline: compare winners and losers without changing entry rules.

Run from repo root: python -m test.diagnose_xrp_squeeze --period 1
Requires Bybit historical OHLCV. Saves CSVs in diagnostic_output/.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backtesting.data_loader import ExchangeDataLoader
from backtesting.market_data import BacktestMarketData
from backtesting.runner import BacktestRunner
from engine.strategy_coordinator import StrategyCoordinator
from indicators.adx import calculate_adx
from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from strategies.bollinger.squeeze import BollingerSqueezeStrategy

SYMBOL = "XRP/USDT:USDT"
# Preserve the original 8999-candle test start for indicator initialization.
START = datetime(2026, 9, 23, 2, 45, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2026, 10, 24, 8, 40, tzinfo=timezone.utc)
OUT = Path("diagnostic_output")


def load_fixed_window(loader):
    exchange = loader.exchange
    loader._validate_exchange(SYMBOL, "5m")
    step = 300_000
    since = int(START.timestamp() * 1000)
    end = int(END_EXCLUSIVE.timestamp() * 1000)
    raw = {}
    while since < end:
        batch = exchange.fetch_ohlcv(SYMBOL, "5m", since=since, limit=1000)
        if not batch:
            raise RuntimeError(f"Missing OHLCV starting at {since}")
        for item in batch:
            if since <= item[0] < end:
                raw[item[0]] = item
        next_since = batch[-1][0] + step
        if next_since <= since:
            raise RuntimeError("OHLCV pagination stalled")
        since = next_since
    timestamps = sorted(raw)
    expected = list(range(int(START.timestamp() * 1000), end, step))
    missing = set(expected) - set(timestamps)
    if missing:
        raise RuntimeError(f"Missing {len(missing)} 5m candles; first: {datetime.fromtimestamp(min(missing)/1000, tz=timezone.utc)}")
    return loader._convert_candles([raw[t] for t in timestamps])


def safe(values, i):
    return values[i] if i >= 0 and i < len(values) else None


class DiagnosticSqueeze(BollingerSqueezeStrategy):
    def __init__(self):
        super().__init__(use_body_filter=True, min_body_ratio=0.80)  # Match current 5m backtest.
        self.signal_rows = []

    def generate_signal(self, candles, index):
        signal = super().generate_signal(candles, index)
        if signal is None:
            return None
        candle = candles[index]
        ema50 = calculate_ema(candles, 50)
        ema200 = calculate_ema(candles, 200)
        rsi = calculate_rsi(candles, 14)
        adx = calculate_adx(candles, 14)
        e200 = safe(ema200, index)
        e200_prev = safe(ema200, index - 10)
        e50 = safe(ema50, index)
        e50_prev = safe(ema50, index - 10)
        d = signal.diagnostics or {}
        prev_lower = d.get("previous_lower_band")
        volume_avg = d.get("preceding_volume_sma")
        body = abs(candle.close - candle.open)
        span = candle.high - candle.low
        self.signal_rows.append({
            "signal_time_utc": candle.timestamp + timedelta(minutes=5),
            "side": signal.side.value,
            "trigger": signal.trigger_price,
            "stop_loss": signal.stop_loss,
            "close": candle.close,
            "ema200": e200,
            "ema200_slope_10": (e200 - e200_prev) if e200 is not None and e200_prev is not None else None,
            "ema50": e50,
            "ema50_slope_10": (e50 - e50_prev) if e50 is not None and e50_prev is not None else None,
            "rsi14": safe(rsi, index),
            "adx14": safe(adx, index),
            "volume_ratio": candle.volume / volume_avg if volume_avg else None,
            "body_ratio": body / span if span else None,
            "penetration_pct": (prev_lower - candle.close) / candle.close * 100 if prev_lower else None,
            "bandwidth_before": d.get("previous_bandwidth"),
            "bandwidth_after": d.get("current_bandwidth"),
            "stop_distance_pct": (signal.stop_loss - signal.trigger_price) / signal.trigger_price * 100 if signal.stop_loss else None,
        })
        return signal


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    anchor = datetime(2026, 10, 24, tzinfo=timezone.utc)
    start = anchor - timedelta(days=(4 - args.period) * 30)
    end = start + timedelta(days=30)
    OUT.mkdir(exist_ok=True)
    loader = ExchangeDataLoader(exchange_name="bybit", market_type="swap")
    market_data = loader.load_dated_5m_market_data(
        symbol=SYMBOL, start=start, end=end, warmup_candles=250,
    )
    candles = market_data.candles_5m
    strategy = DiagnosticSqueeze()
    coordinator = StrategyCoordinator(strategies_15m=[], strategies_5m=[strategy])
    runner = BacktestRunner(
        strategy_coordinator=coordinator, initial_balance=10_000.0,
        risk_percentage=0.05, default_risk_reward=3.0,
        default_stop_percentage=0.01, breakout_expiry_candles=3,
        trade_start_time=start,
    )
    result = runner.run(market_data)
    write_csv(OUT / f"xrp_signals_period_{args.period}.csv", strategy.signal_rows)
    trade_rows = []
    for trade in result.trades:
        # OHLCV extremes cannot establish within-candle order of high/low.
        active = [c for c in candles if trade.entry_time <= c.timestamp < trade.exit_time] if trade.exit_time else []
        # Entry timestamp can be the candle open; include exit candle if present.
        if trade.exit_time:
            active = [c for c in candles if trade.entry_time <= c.timestamp <= trade.exit_time]
        if trade.side == "short" and active:
            mfe = (trade.entry_price - min(c.low for c in active)) / trade.entry_price * 100
            mae = (max(c.high for c in active) - trade.entry_price) / trade.entry_price * 100
        else:
            mfe = mae = None
        matching = next((s for s in strategy.signal_rows
                         if s["side"] == trade.side
                         and s["trigger"] == trade.entry_price
                         and s["signal_time_utc"] <= trade.entry_time), None)
        trade_rows.append({
            "entry_time_utc": trade.entry_time,
            "exit_time_utc": trade.exit_time,
            "side": trade.side,
            "entry": trade.entry_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "exit_reason": trade.exit_reason,
            "net_pnl": trade.pnl,
            "duration_minutes": (trade.exit_time - trade.entry_time).total_seconds() / 60 if trade.exit_time else None,
            "mfe_pct_ohlcv_upper_bound": mfe,
            "mae_pct_ohlcv_upper_bound": mae,
            **{k: v for k, v in (matching or {}).items() if k not in ("side", "trigger", "stop_loss")},
        })
    write_csv(OUT / f"xrp_trades_period_{args.period}.csv", trade_rows)
    print(f"Saved period {args.period} diagnostic CSV files in {OUT}")
    print("Note: OHLCV extremes do not reveal intrabar ordering; MFE/MAE are bounds, not tick-accurate paths.")
    print(f"Trades: {result.total_trades}; wins: {result.winning_trades}; losses: {result.losing_trades}; net PnL: {result.total_pnl:.2f}")


if __name__ == "__main__":
    main()
