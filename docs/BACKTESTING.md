# `backtesting/`, `risk/`, `brokers/` and `test/` — File-by-File Explanation

This guide covers the **simulation stack** (`backtesting/`), the **risk library** (`risk/`), the
concrete broker implementation (`brokers/paper/`) and the runnable scripts in `test/`.

---

# PART A — Backtesting framework (`backtesting/`)

The backtester is an event-driven engine that replays historical candles through the **same
`StrategyCoordinator` and `RiskManager` classes used by the live engine**, so research results map
directly to live behaviour.

Overall loop:

```
ExchangeDataLoader ──▶ BacktestMarketData (15m + 5m lists)
                              │
BacktestRunner.run ◀──────────┘
   ├─ _build_timeline(): merge both series, sort by timestamp (15m first on ties)
   ├─ for each (timestamp, timeframe, candle):
   │     ├─ build_context()      → point-in-time candle slices (no lookahead)
   │     ├─ StrategyCoordinator.evaluate() → TradingSignal?
   │     ├─ pending next-open entry executed at this bar's open (via BacktestExecution+RiskManager)
   │     ├─ BacktestBroker.process_candle() → intra-bar SL/TP exit check
   │     └─ new signal with NEXT_OPEN timing → stored as PendingEntry for the following bar
   └─ returns BacktestResult statistics
```

## 1. `backtesting/config.py` — `BacktestConfig`
Frozen defaults describing *what* to download: `exchange="bybit"`, `symbol="BTC/USDT:USDT"`,
`timeframe_15m="15m"`, `timeframe_5m="5m"`, `limit=200`, `candles=1000`,
`market_type="swap"` (USDT-m perpetuals). It is a plain settings bag; the runner script currently
passes explicit arguments instead of importing it.

## 2. `backtesting/data_loader.py` — `ExchangeDataLoader`
CCXT wrapper that turns exchange REST responses into typed `Candle`s.

- **Constructor:** validates the exchange name exists on the `ccxt` module
  (`hasattr(ccxt, exchange_name)`), instantiates it with `enableRateLimit=True` and
  `defaultType=market_type` ("swap" ⇒ perpetual futures).
- **`load_candles(symbol, timeframe, limit)`** — one-shot fetch via `fetch_ohlcv`, converted and
  then `_remove_incomplete_candle` drops the last row (exchanges return the still-forming bar).
- **`load_historical_candles(symbol, timeframe, candles)`** — paginated bulk download:
  1. Compute `timeframe_ms` with `exchange.parse_timeframe`.
  2. Fetch the newest single candle to learn "now", then set `since = latest_ts − candles·tf_ms`.
  3. Loop fetching ≤1000 bars per request, advancing `since` past the last received timestamp;
     stops on empty batch, non-advancing cursor, or short batch (end of history).
  4. De-duplicate by timestamp (dict keyed by ms), sort ascending, keep the last `candles` rows,
     drop the final incomplete candle.
- **`_validate_exchange`** — asserts `fetchOHLCV` capability, loads markets, checks symbol
  availability and timeframe support; raises descriptive `ValueError`s.
- **`_convert_candles`** — maps raw `[ms, o, h, l, c, v]` rows to UTC-aware `Candle` objects and
  sorts by timestamp.
- **`load_market_data(symbol, candles=2500)`** — convenience: downloads `candles` 15m bars and
  `candles×3` 5m bars (same wall-clock span) and bundles them into a `BacktestMarketData`.

## 3. `backtesting/market_data.py` — `BacktestMarketData`
Frozen container `{symbol, candles_15m, candles_5m}` plus two properties:
`start_time` = min of both series' first timestamps, `end_time` = max of both series' last
timestamps (both `None`-safe). Pure data holder used by the runner and loader.

## 4. `backtesting/context.py` — `build_context()` + `BacktestContext`
**The anti-lookahead mechanism.** At every simulated moment it filters both full series down to
`[c for c in candles if c.timestamp <= current_timestamp]` and returns them in a frozen
`BacktestContext(candles_15m, candles_5m)`. Strategies therefore only ever see candles closed up
to "now". (Cost note: O(n) filter per event — fine for research sizes, could be index-based later.)

## 5. `backtesting/broker.py` — `BacktestBroker`
Simulated single-position broker (dataclass with mutable fields):

- State: `balance`, `trade_counter`, `current_trade` (only **one concurrent trade** allowed).
- `open_trade(...)` — refuses when a trade is already open or qty/price ≤ 0; creates a `Trade`
  with sequential ID `BT-000001…`; prints a `===== TRADE OPENED =====` block.
- **`process_candle(candle)` — the intra-bar exit simulator.** For the open trade, in strict
  priority order:
  - LONG: stop-loss first (`candle.low <= stop` ⇒ close at stop price, reason `STOP_LOSS`),
    then take-profit (`candle.high >= tp` ⇒ close at TP price, reason `TAKE_PROFIT`).
  - SHORT: mirrored (`high >= stop`, `low <= tp`).
  Checking SL before TP is deliberately conservative: when one candle touches both levels, the
  backtest assumes you lost rather than won. Fills are assumed exact at the level price (no slippage).
- `close_trade(...)` — calls `Trade.close()` (computes gross/net PnL), adds PnL to `balance`,
  prints the `TRADE CLOSED` report, returns the finished Trade.

## 6. `backtesting/execution.py` — `BacktestExecution` + `PendingEntry`
Bridges signals to the broker using the **live RiskManager**:

- `PendingEntry(signal, symbol, timeframe)` — a signal scheduled for entry on the *next* bar.
- `can_enter(symbol)` — true iff broker has no open trade.
- `sync_account()` — copies broker balance into `risk_manager.account.balance` /
  `available_balance` so position sizing always reflects the evolving equity curve.
- `execute_next_open(pending, candle)` — enters at `candle.open`:
  1. sync account, 2. `RiskManager.evaluate(signal, entry_price=open)`; rejection prints
     `TRADE REJECTED` with reason, 3. otherwise opens the trade with the computed size, the
     signal's stop, and the risk/reward result's take-profit (strategy TP or default 3:1).

## 7. `backtesting/result.py` — `BacktestTrade`, `BacktestResult`
Reporting DTOs decoupled from engine models:
- `BacktestTrade` flattens a closed `Trade` into a serialisable record (entry/exit, SL/TP, pnl).
- `BacktestResult` holds symbol, initial/final balance and the trade list, with derived
  properties: `total_trades`, `winning_trades` (pnl>0), `losing_trades` (pnl<0), `total_pnl`
  (=final−initial), `return_percentage`, `win_rate`.

## 8. `backtesting/runner.py` — `BacktestRunner`
The orchestrator (dataclass: `strategy_coordinator`, `initial_balance=10_000`,
`risk_percentage=0.02`, `default_risk_reward=3.0`).

`run(market_data)` walkthrough:
1. Instantiate `BacktestBroker`, a fresh `Account("BACKTEST", "USDT", …)`, `RiskManager`,
   `BacktestExecution`; print the BACKTEST STARTED header.
2. `_build_timeline()` merges 15m and 5m candles into `(timestamp, timeframe, candle)` tuples and
   sorts by `(timestamp, priority)` where 15m=0 < 5m=1 — so on simultaneous timestamps the 15m bar
   is processed first (mirrors the live 15m-priority rule).
3. For every timeline event:
   - Build the no-lookahead context via `build_context`.
   - Evaluate strategies. *(Implementation quirk: the code first runs a timeframe-specific
     evaluation inside an if/else and then unconditionally overwrites it with a combined
     `evaluate(15m, 5m)` call — the second call is what actually takes effect; the branch is
     leftover scaffolding.)*
   - If a `pending_entry` exists and its timeframe matches the current event: execute it at this
     candle's open through `BacktestExecution.execute_next_open` (or print SIGNAL IGNORED when a
     trade is already open); clear the pending slot. *(Minor bug: the duplicate "Trade entered"
     print references `trade` outside its defining scope in one path — harmless because the same
     message already printed inside the `if`, but worth cleaning.)*
   - `broker.process_candle(candle)` — check SL/TP hits on the forming bar; completed trades are
     appended to `completed_trades`.
   - If the coordinator produced a signal: print the SIGNAL block; when
     `entry_timing == NEXT_OPEN`, queue it as a `PendingEntry` for the next matching-timeframe bar.
4. Print BACKTEST FINISHED + total signal count; convert closed `Trade`s to `BacktestTrade`s and
   return the `BacktestResult`.

Note: entries triggered by other timings (CURRENT_CLOSE/BREAKOUT triggers) are not yet executed
by the runner — today it effectively backtests next-open systems (e.g. HiLoMACD).

## 9. `backtesting/strategy_setup.py` — `create_strategy_coordinator()`
The strategy registry factory: builds `StrategyCoordinator(strategies_15m=[EMACrossover,
HiLoMACD], strategies_5m=[EMACrossover, HiLoMACD])`. Add more strategies here (FFFD, squeeze,
NR7…) to widen the research universe; list order encodes priority.

## 10. `backtesting/portfolio.py`
Empty placeholder reserved for multi-symbol portfolio accounting (currently the broker keeps one
global trade slot).

---

# PART B — Risk library (`risk/`)

## `risk/config.py` — `RiskConfig`
Central defaults: `risk_percentage=0.02` (2%/trade), `risk_reward_ratio=3.0`,
`daily_drawdown_limit=0.05`, ATR trailing params (period 14, multiplier 2.0), EMA trailing period
9, swing lookback 3. Documentation-grade today — callers pass literal defaults.

## `risk/position_sizing.py` — `calculate_position_size(...)`
Fixed-fractional sizing pure function with hard input validation (>0 everywhere, entry≠stop):
`max_risk_amount = capital × risk_percentage`; `risk_per_unit = |entry − stop|`;
`position_size = max_risk_amount / risk_per_unit`. Returns a frozen `PositionSizeResult` carrying
all intermediate values for audit. Effect: every trade loses exactly ~2% of equity if stopped out.

## `risk/risk_reward.py` — `calculate_take_profit(...)`
Given entry, stop, side and ratio (default 3.0): `risk_distance = |entry − stop|`;
LONG ⇒ `TP = entry + ratio×risk_distance`; SHORT ⇒ `TP = entry − ratio×risk_distance`; wrapped in
frozen `RiskRewardResult`. Validated inputs; unsupported side raises.

## `risk/daily_drawdown.py` — `DailyDrawdownGuard` + `DrawdownStatus`
Stateful circuit breaker:
- Tracks `_day`, `_start_of_day_balance`, `_triggered`. On the first call of a new calendar day it
  resets the baseline to the current balance and clears the trigger.
- Each `update(current_balance, current_day)` computes
  `drawdown = max(0, start − current)`, percentage vs start; once ≥ limit (default 5%) the guard
  latches `triggered=True` for the rest of the day (even if balance recovers).
- `is_triggered` property for quick polling. Returns immutable `DrawdownStatus` snapshots.
⚠️ The live `TradingEngine` calls `.check(...)`, which doesn't exist yet — reconcile before use.

## Trailing stops (`risk/trailing/`)
All three follow the same **ratchet contract**: given `current_stop`, they may only tighten it
(long stops move up, short stops move down) — never loosen. None are wired into the live engine
yet; `Position.highest_price/lowest_price` (maintained by `PositionManager.update_price`) supplies
the extremes they need.

- **`atr.py::calculate_atr_trailing_stop`** — stop trails the best price since entry by
  `ATR(14) × 2.0`: LONG `max(current_stop, highest − mult·ATR)`; SHORT
  `min(current_stop, lowest + mult·ATR)`. Falls back to `current_stop` while ATR warms up.
- **`ema9.py::calculate_ema9_trailing_stop`** — candidate = better of EMA(9) and previous candle's
  low (long) / high (short), ratcheted against the current stop. Companion
  `should_exit_ema9(side)` fires when close crosses under (over) the EMA-9 for longs (shorts).
- **`swing.py::calculate_swing_trailing_stop`** — candidate = min low (long) / max high (short)
  over the last `lookback=3` candles, ratcheted. Classic structure-following stop.

`risk/__init__.py` re-exports sizing, RR, drawdown types; `risk/trailing/__init__.py` re-exports
the three stop functions plus `should_exit_ema9`.

---

# PART C — `brokers/paper/broker.py` — `PaperBroker`
Concrete `engine.execution_engine.Broker` implementation for zero-risk testing:
`submit_order` instantly flips status→FILLED, sets `filled_quantity=quantity`, and derives
`average_fill_price` from `order.price` (market/limit) else `order.stop_price` (stops) — raising if
neither exists — plus a synthetic `PAPER-<id>` exchange order id. `cancel_order` is a no-op.
It intentionally ignores market impact/slippage; realistic fills belong to venue-specific brokers
(not yet implemented).

---

# PART D — Runnable scripts (`test/`)

- **`test/test_backtest_data_loader.py`** — manual smoke test: constructs an
  `ExchangeDataLoader("bybit", "swap")`, calls `load_market_data("BTC/USDT:USDT", candles=2500)`
  and prints counts, start/end times and first/last candles of both series. Verifies pagination,
  dedup and candle conversion work against the live API.
- **`test/backtest_broker.py`** — end-to-end demo (`main()`): load 100×15m candles (+300×5m),
  build the trend-strategy coordinator via `create_strategy_coordinator()`, run
  `BacktestRunner(strategy_coordinator, initial_balance=10_000).run(market_data)`, and print total
  trades and final balance. This is the canonical "how do I run a backtest" example:

```bash
python -m test.backtest_broker
```

Both scripts require network access and `pip install ccxt`; they are plain `main()`-style
integration checks rather than pytest suites.
