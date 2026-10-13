# CryptoBot-V5

FFFD live trading defaults to Bybit SOL perpetuals using the backtest settings.
See [changes and DigitalOcean deployment](deploy/README.md) for installation,
credentials, preflight, testnet and production operation.

A modular, research-grade **algorithmic crypto trading bot** written in pure Python (no heavy
frameworks — everything from indicators to risk math is implemented from scratch). The project
is organised as a clean pipeline:

```
Market Data → Indicators → Patterns → Strategies (Signals) → Risk Management → Engine → Execution / Backtesting
```

It currently targets **Bybit USDT-M perpetual futures** via [CCXT](https://github.com/ccxt/ccxt),
works on two timeframes (**15m primary, 5m secondary**), and ships with a full event-driven
**backtesting framework** that reuses the exact same strategy/risk code as live trading.

---

## 📚 Documentation Map

Because the codebase is large, the documentation is split into several files. Start here, then
drill down into the module-specific guides:

| Document | Contents |
|---|---|
| **README.md** (this file) | Project overview, full folder structure, architecture, data flow, how to run |
| **[docs/ENGINE.md](docs/ENGINE.md)** | File-by-file deep dive of the `engine/` folder (`trading_engine`, `strategy_coordinator`, `risk_manager`, `position_manager`, `execution_engine`, `state`) |
| **[docs/STRATEGIES.md](docs/STRATEGIES.md)** | File-by-file explanation of every strategy in `strategies/` (trend, bollinger, breakout, momentum, pullback) **and** every indicator in `indicators/` they rely on |
| **[docs/BACKTESTING.md](docs/BACKTESTING.md)** | File-by-file explanation of the `backtesting/` framework (data loader, runner, broker, execution, results) plus `brokers/`, `test/` and `risk/` modules |
| **[docs/PATTERNS_CORE.md](docs/PATTERNS_CORE.md)** | Candlestick pattern library (`patterns/`) and shared domain models/enums (`core/`) |

---

## 🗂 Full Folder Structure

```
CryptoBot-V5/
│
├── README.md                     ← You are here (overview + structure)
├── requrements.txt               ← Dependency list (currently empty; only external dep is ccxt)
│
├── core/                         ← Shared domain models & enums (used by every other module)
│   ├── enums/
│   │   ├── order.py              OrderSide, OrderType, OrderStatus
│   │   ├── position.py           PositionSide, PositionStatus
│   │   └── trade.py              TradeStatus, ExitReason
│   └── models/
│       ├── account.py            Account (balance, equity, PnL helpers)
│       ├── candle.py             Candle (OHLCV + body/wick/polarity properties)
│       ├── order.py              Order dataclass
│       ├── pattern.py            PatternResult (candlestick pattern output)
│       ├── position.py           Position dataclass (live position state)
│       ├── signal.py             TradingSignal, SignalSide, EntryTiming
│       └── trade.py              Trade dataclass (entry→exit record with PnL)
│
├── indicators/                   ← Pure-function technical indicators (list-in, list-out)
│   ├── adx.py                    ADX / DI+/DI- (Wilder-style directional strength)
│   ├── atr.py                    True Range + ATR with Wilder smoothing
│   ├── bollinger_bands.py        SMA middle band ± k·σ, bandwidth metric
│   ├── ema.py                    Exponential Moving Average (SMA-seeded)
│   ├── hilo_activator.py         Hi-Lo Activator trend-flip line
│   ├── macd.py                   MACD line / signal line / histogram
│   ├── volume.py                 Volume SMA
│   ├── volume_spike.py           Breakout volume confirmation (ratio vs Volume SMA)
│   └── williams_r.py             Larry Williams %R oscillator
│
├── patterns/                     ← Candlestick pattern detectors (20 patterns)
│   ├── base.py                   BasePattern ABC (detect(candles) → PatternResult)
│   ├── config.py                 PatternConfig wick/body thresholds
│   ├── bullish/                  Hammer, Inverted Hammer, Engulfing, Harami, Morning Star,
│   │                             Piercing Line, Bullish Marubozu, 3 White Soldiers,
│   │                             Bullish Hikkake, Bullish 20/20
│   └── bearish/                  Shooting Star, Hanging Man, Engulfing, Harami, Evening Star,
│                                 Dark Cloud Cover, Bearish Marubozu, 3 Black Crows,
│                                 Bearish Hikkake, Bearish 20/20
│
├── strategies/                   ← Signal generators (the heart of the bot)
│   ├── trend/
│   │   ├── ema_crossover.py      EMA 8/21 golden-cross + volume filter (+ exit logic)
│   │   ├── hilo_macd.py          Hi-Lo Activator flip + MACD trend filter (next-open entry)
│   │   └── config.py             MovingAverageCrossoverConfig
│   ├── bollinger/
│   │   ├── fffd.py               "Fechou Fora – Fechou Dentro" mean-reversion
│   │   ├── squeeze.py            Bandwidth squeeze → expansion breakout + volume
│   │   ├── channel_rebound.py    Ranging-market band rebound filtered by low ADX
│   │   └── config.py             BollingerConfig
│   ├── breakout/
│   │   ├── nr7.py                Narrow-Range-7 inside-bar OCO breakout (dual signals)
│   │   └── config.py             NR7Config
│   ├── momentum/
│   │   ├── williams_r.py         %R oversold-recovery long + overbought exit rule
│   │   └── config.py             WilliamsRStrategyConfig
│   └── pullback/
│       ├── setup_1234.py         Connors-style 1-2-3-4 three-lower-lows reversal
│       └── config.py             Setup1234Config + trend-filter enum
│
├── risk/                         ← Risk math (pure functions + stateful guard)
│   ├── position_sizing.py        Fixed-fractional sizing: qty = capital·risk% / stop distance
│   ├── risk_reward.py            Default take-profit at N:R (default 3:1)
│   ├── daily_drawdown.py         DailyDrawdownGuard — halts trading after daily loss limit
│   ├── config.py                 RiskConfig defaults
│   └── trailing/
│       ├── atr.py                ATR(2×) ratchet stop (never loosens)
│       ├── ema9.py               EMA-9 / previous-candle trailing stop + exit check
│       └── swing.py              Swing-low/high trailing stop
│
├── engine/                       ← Live-trading orchestration (see docs/ENGINE.md)
│   ├── trading_engine.py         TradingEngine — the per-symbol decision pipeline
│   ├── strategy_coordinator.py   StrategyCoordinator — 15m-priority signal arbitration
│   ├── risk_manager.py           RiskManager — approves/vetoes signals, sizes positions
│   ├── position_manager.py       PositionManager — open/update/close lifecycle + Trade log
│   ├── execution_engine.py       Broker ABC + ExecutionEngine (order submission wrapper)
│   └── state.py                  EngineState — single source of truth (orders/positions/trades)
│
├── brokers/                      ← Broker implementations of the engine's Broker ABC
│   └── paper/broker.py           PaperBroker — instant-fill simulation for smoke tests
│
├── backtesting/                  ← Event-driven backtester reusing engine components
│   ├── data_loader.py            ExchangeDataLoader — CCXT paginated OHLCV download
│   ├── market_data.py            BacktestMarketData container (15m + 5m series)
│   ├── context.py                build_context() — point-in-time candle slicing (no lookahead)
│   ├── runner.py                 BacktestRunner — main event loop / timeline engine
│   ├── broker.py                 BacktestBroker — trade opener + intra-candle SL/TP simulator
│   ├── execution.py              BacktestExecution — pending next-open entries + risk sync
│   ├── result.py                 BacktestTrade / BacktestResult statistics
│   ├── config.py                 BacktestConfig defaults (bybit, BTC/USDT:USDT…)
│   └── portfolio.py              (placeholder — reserved for future portfolio accounting)
│
├── test/                         ← Runnable scripts (manual integration checks)
│   ├── backtest_broker.py        End-to-end backtest demo (download → run → print result)
│   └── test_backtest_data_loader.py  Data-loader smoke test (prints candle counts)
│
└── docs/                         ← Detailed module documentation
    ├── ENGINE.md
    ├── STRATEGIES.md
    ├── BACKTESTING.md
    └── PATTERNS_CORE.md
```

---

## 🏛 Architecture & Data Flow

### Layered design

1. **`core/` — Domain layer.** Immutable-friendly dataclasses and string enums shared by all
   layers. Nothing in `core` imports from any other package, so it can never create circular
   dependencies. Key contract object: `TradingSignal` (strategy name, side, entry timing,
   trigger price, stop-loss, optional take-profit, human-readable reason). See
   [docs/PATTERNS_CORE.md](docs/PATTERNS_CORE.md).

2. **`indicators/` + `patterns/` — Analysis layer.** Stateless maths. Every indicator takes a
   `list[Candle]` and returns a parallel `list[...]` with `None` for warm-up bars. Patterns take
   candles and return a `PatternResult`. No side effects, trivially unit-testable.

3. **`strategies/` — Signal layer.** Each strategy exposes
   `generate_signal(candles, index) -> TradingSignal | None` (NR7 additionally exposes
   `generate_signals()` returning a *pair* of OCO-style signals). Some strategies also expose
   exit/trailing helpers (`should_exit_long`, `trailing_stop`). Strategies never place orders —
   they only describe *what should happen*. Full details: [docs/STRATEGIES.md](docs/STRATEGIES.md).

4. **`risk/` — Risk layer.** Pure sizing/reward functions plus the stateful
   `DailyDrawdownGuard` and three trailing-stop algorithms. Details: [docs/BACKTESTING.md](docs/BACKTESTING.md).

5. **`engine/` — Orchestration layer.** `TradingEngine.process_symbol()` wires everything:
   busy-symbol check → drawdown check → coordinator signal → entry-price resolution → risk
   approval → order construction → execution → position opening. See [docs/ENGINE.md](docs/ENGINE.md).

6. **`brokers/` + `backtesting/` — Execution/simulation layer.** `PaperBroker` implements the
   engine's `Broker` interface for instant-fill simulation; the `backtesting/` package runs the
   *same strategies and the same RiskManager* against historical CCXT data through an
   event-driven timeline. See [docs/BACKTESTING.md](docs/BACKTESTING.md).

### Per-candle pipeline (live engine)

```
process_symbol(symbol, candles_15m, candles_5m, timestamp)
        │
        ├─ 1. state.symbol_is_busy()?  ──yes→ reject ("already has active order/position")
        ├─ 2. DailyDrawdownGuard.check() ──triggered→ reject ("daily drawdown limit")
        ├─ 3. StrategyCoordinator.evaluate(15m first, then 5m) ──no signal→ reject
        ├─ 4. _resolve_entry_price(signal, candles)  (trigger / current close / next open)
        ├─ 5. RiskManager.evaluate(signal, entry)    (size = capital·2% / stop-distance, TP = 3R)
        ├─ 6. _build_order(...) MARKET or STOP order
        ├─ 7. ExecutionEngine.submit(order) → Broker.submit_order()
        └─ 8. if FILLED → PositionManager.open_position() + Trade record
```

---

## ⚙️ Configuration Highlights

Defaults are frozen dataclasses colocated with each module:

| Config | Location | Notable defaults |
|---|---|---|
| `BollingerConfig` | `strategies/bollinger/config.py` | period 20, std 2.0, ADX threshold 20, squeeze lookback 20 |
| `NR7Config` | `strategies/breakout/config.py` | lookback 7, trigger offset 0.0 |
| `MovingAverageCrossoverConfig` | `strategies/trend/config.py` | fast 8 / slow 21, volume SMA 20, stop mode `ema21` |
| `WilliamsRStrategyConfig` | `strategies/momentum/config.py` | period 14, oversold −80, overbought −20 |
| `Setup1234Config` | `strategies/pullback/config.py` | EMA-200 trend filter, RR 2.0, use previous swing high |
| `RiskConfig` | `risk/config.py` | risk 2%/trade, RR 3.0, daily drawdown 5%, ATR 14×2.0 |
| `BacktestConfig` | `backtesting/config.py` | exchange `bybit`, symbol `BTC/USDT:USDT`, market type `swap` |
| `PatternConfig` | `patterns/config.py` | wick/body ratios for star, marubozu, hikkake, 20/20 patterns |

---

## 🚀 Running

```bash
pip install ccxt            # the only third-party dependency

# 1) Smoke-test the data loader (downloads ~2500 15m + 7500 5m candles)
python -m test.test_backtest_data_loader

# 2) Run a full backtest (EMA-crossover + Hi-Lo/MACD coordinator on BTC/USDT:USDT)
python -m test.backtest_broker
```

The backtest prints every opened/closed trade, signal, and rejection reason, and finishes with a
`BacktestResult` (total trades, win rate, final balance, return %).

---

## ✨ Design Principles

- **Pure-Python indicators** — no TA-Lib/pandas dependency; every formula is explicit and auditable.
- **Strategies are dumb** — they emit declarative `TradingSignal`s; the engine owns execution.
- **One position per symbol** — enforced centrally in `EngineState.symbol_is_busy()`.
- **Fail-safe risk** — missing stop-loss ⇒ automatic rejection; daily drawdown ⇒ global halt.
- **No lookahead bias in backtests** — `build_context()` slices candles by timestamp each bar.
- **Live/backtest parity** — both paths share `StrategyCoordinator` and `RiskManager`.

## Known Gaps / TODO (as-implemented notes)

- Install the pinned CCXT dependency with `pip install -r requirements.txt`.
- `backtesting/portfolio.py` is an empty placeholder.
- The `patterns/` library is not yet wired into any strategy or the engine.
- Trailing stops (`risk/trailing/`) are implemented but not yet called by the live engine.
- NR7's dual-signal OCO behaviour is documented in its docstring but the coordinator currently
  consumes single `generate_signal()` results only.
- `TradingEngine` calls `daily_drawdown_guard.check(...)` while `DailyDrawdownGuard` implements
  `update(...)` — this mismatch must be reconciled before live use.
- `BacktestRunner.run()` contains some redundant evaluation/print blocks (see docs/BACKTESTING.md).
