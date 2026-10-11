# `patterns/` and `core/` — File-by-File Explanation

Two foundational packages:

- **`core/`** — the shared vocabulary of the whole project: enums + dataclass domain models.
  Every other package imports from here; `core` itself imports nothing from the project, so it is
  acyclic by construction.
- **`patterns/`** — a standalone candlestick-pattern recognition library (20 detectors). It is
  fully implemented but **not yet consumed by any strategy or the engine** — intended as building
  blocks for confirmation filters (e.g. "only take the FFFD long if a Hammer printed").

---

# PART A — `core/enums/`

All enums inherit `str, Enum`, so they serialise/compare as plain strings (handy for JSON logs and
`signal.side.value == "long"` style checks used in `engine/risk_manager.py`).

### `core/enums/order.py`
| Enum | Values | Role |
|---|---|---|
| `OrderSide` | BUY, SELL | Direction on the venue |
| `OrderType` | MARKET, LIMIT, STOP, STOP_LIMIT | The engine currently emits MARKET and STOP only |
| `OrderStatus` | PENDING, OPEN, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED, EXPIRED | Full order lifecycle vocabulary |

### `core/enums/position.py`
`PositionSide` (LONG/SHORT), `PositionStatus` (OPEN/CLOSED) — used by `Position`, `Trade`,
`PositionManager`, and the backtest broker's exit logic.

### `core/enums/trade.py`
`TradeStatus` (OPEN/CLOSED) and `ExitReason` — STOP_LOSS, TAKE_PROFIT, STRATEGY_EXIT,
TRAILING_STOP, DAILY_DRAWDOWN, MANUAL, UNKNOWN. Exit reasons tag every closed trade so reports
can attribute performance per cause. `__init__.py` re-exports all seven enums.

---

# PART B — `core/models/`

### `candle.py` — `Candle` (frozen)
The atomic market-data unit: UTC `timestamp`, OHLC floats, `volume` (default 0). Derived
properties power pattern & strategy logic without recomputation:
`body = |close−open|`, `range = high−low`, `upper_wick`, `lower_wick`, `is_bullish`,
`is_bearish`, `midpoint`. Produced by `ExchangeDataLoader` and consumed everywhere.

### `signal.py` — `TradingSignal` + `SignalSide` + `EntryTiming`
The **strategy→engine contract**. Frozen dataclass: `strategy` name, `side` (LONG/SHORT),
`candle_index` (which bar triggered), `entry_timing` (`CURRENT_CLOSE` / `NEXT_OPEN` / `BREAKOUT`,
default CURRENT_CLOSE), optional `trigger_price`, `stop_loss`, `take_profit`, and free-text
`reason`. The engine branches on `entry_timing`/`trigger_price` in `_resolve_entry_price` and
`_build_order`; the backtest runner queues NEXT_OPEN signals as pending entries.

### `order.py` — `Order`
Mutable record of an instruction to a broker: IDs, symbol, side/type/quantity, `created_at`,
optional limit `price` and `stop_price`, lifecycle `status`, fill tracking
(`filled_quantity`, `average_fill_price`), `exchange_order_id`, plus provenance (`strategy`,
`reason`). Properties: `is_active` (PENDING/OPEN/PARTIALLY_FILLED), `is_filled`,
`remaining_quantity`. `EngineState.active_orders` and `ExecutionEngine` operate on this object.

### `position.py` — `Position`
Live exposure bookkeeping: identity/symbol/side/qty/entry/time, `stop_loss`/`take_profit`,
`status`, live `current_price`, running `highest_price`/`lowest_price` extremes (fed by
`PositionManager.update_price`, needed by ATR/swing trailing stops), originating `strategy`, and
exit fields once closed. Computed: `unrealized_pnl` (mark-to-market vs current price) and
`realized_pnl` (vs exit price); polarity flips for shorts.

### `trade.py` — `Trade`
The immutable-history twin of Position: full entry details, SL/TP snapshot, `status`, exit
fields, `fees`. `gross_pnl = (exit−entry)×qty` (inverted for SHORT), `net_pnl = gross − fees`.
`close(exit_price, exit_time, exit_reason, fees)` validates (>0 price, not already closed),
accumulates fees and flips status. `PositionManager.close_position` and `BacktestBroker.close_trade`
both drive this method; the Trade journal is the raw material for `BacktestResult`.

### `account.py` — `Account`
Wallet-level state: ids/currency, `initial_balance` vs current `balance`, margin fields, realized
and unrealized PnL totals. Validation in `__post_init__` (positive initial, non-negative balance,
auto-derives `available_balance = balance − used_margin`). Properties: `equity = balance +
unrealized`, `total_pnl`, `return_percentage`. `update_balance(amount)` applies deltas and keeps
`available_balance` consistent. Instantiated by `TradingEngine` users and `BacktestRunner`.

### `pattern.py` — `PatternResult` (frozen)
Uniform output of every detector: `detected`, `pattern` name, optional `candle_index`,
`trigger_price`, `reason`. Classmethod `no_match(pattern, reason)` builds negative results with a
diagnostic message. ⚠️ Note: concrete patterns pass their suggested entry via the keyword
`entry_price=` when constructing `PatternResult(...)`; since the dataclass field is named
`trigger_price`, aligning these two names would make the pattern layer directly consumable
(currently another sign the library isn't wired in yet).

`core/models/__init__.py` re-exports Account/Order/Position/Trade for convenience.

---

# PART C — `patterns/`

## Shared infrastructure
- **`base.py::BasePattern`** — ABC: class attr `name`, ctor accepting optional `PatternConfig`,
  abstract `detect(candles) -> PatternResult`. Detectors inspect the **tail** of the list
  (`candles[-1]`, `candles[-2]`, …), i.e. they always test the latest closed bar; callers just pass
  a window.
- **`config.py::PatternConfig`** (frozen) — tunable geometry thresholds:
  `marubozu_max_wick_ratio=0.05` (max wick/body for a "flat" candle),
  `long_wick_body_ratio=2.0` and `small_opposite_wick_body_ratio=0.25` (star/hammer family),
  `large_body_range_ratio=0.60` / `small_body_range_ratio=0.30` (body-vs-range classification),
  `twenty_percent=0.20` (the 20/20 pattern).
- Each sub-package has an empty `__init__.py`; import classes directly
  (`from patterns.bullish.hammer import Hammer`).

## Bullish detectors (`patterns/bullish/`) — all return `detected=True` with
`candle_index=len(candles)-1` and an entry suggestion at the signal bar's high unless noted.

| File / Class | Bars | Exact rules implemented |
|---|---|---|
| `hammer.py::Hammer` | 1 | lower wick ≥ 2× body; upper wick ≤ 0.25× body; body within top 25% of range |
| `inverted_hammer.py::InvertedHammer` | 1 | mirror: long upper wick ≥ 2× body, tiny lower wick, body near bottom of range |
| `bullish_engulfing.py::BullishEngulfing` | 2 | previous bearish, current bullish, current body fully covers previous body (high≥ and low≤) |
| `bullish_harami.py::BullishHarami` | 2 | previous large bearish mother; current bullish body contained inside mother body |
| `morning_star.py::MorningStar` | 3 | large bearish first (body ≥ 60% of range) → small-bodied star (≤30%) not overlapping first body → bullish third closing inside first body |
| `pircing_line.py::PiercingLine` (file typo; class `PiercingLine`) | 2 | bearish then bullish that opens below and closes above previous body midpoint |
| `bullish_marubozu.py::BullishMarubozu` | 1 | bullish candle whose wicks are ≤ 5% of body ("full body" candle) |
| `three_white_soldiers.py::ThreeWhiteSoldiers` | 3 | three consecutive bullish candles each closing near its high / above prior close |
| `bullish_hikkake.py::BullishHikkake` | 4 | inside bar after mother → bearish breakdown below inside low → *failure*: next bar trades above inside high (trap reversal long) |
| `bullish_20_20.py::Bullish2020` | 1 | bullish candle opening in bottom 20% of its range and closing in top 20% (power trend bar) |

## Bearish detectors (`patterns/bearish/`) — exact mirrors of the above:

| File / Class | Mirror of | Notes |
|---|---|---|
| `shooting_star.py::ShootingStar` | Inverted Hammer | rejection wick at highs |
| `hanging_man.py::HangingMan` | Hammer | same shape, bearish context label |
| `bearish_engulfing.py::BearishEngulfing` | Bullish Engulfing | bearish body engulfs prior bullish body |
| `bearish_harami.py::BearishHarami` | Bullish Harami | bearish child inside bullish mother |
| `evening_star.py::EveningStar` | Morning Star | bullish → star → bearish confirmation |
| `dark_cloud_cover.py::DarkCloudCover` | Piercing Line | opens above prior body, closes below midpoint |
| `bearish_marubozu.py::BearishMarubozu` | Bullish Marubozu | full-body decline |
| `three_black_crows.py::ThreeBlackCrows` | Three White Soldiers | three bearish closes near lows |
| `bearish_hikkake.py::BearishHikkake` | Bullish Hikkake | failed upside breakout trap short |
| `bearish_20_20.py::Bearish2020` | Bullish 20/20 | opens top 20%, closes bottom 20% |

Every detector returns `PatternResult.no_match(name, "<why it failed>")` on each rejected branch,
making pattern evaluation self-explanatory in logs.

### How to use a pattern today

```python
from patterns.bullish.hammer import Hammer
from backtesting.data_loader import ExchangeDataLoader

loader = ExchangeDataLoader("bybit", "swap")
candles = loader.load_candles("BTC/USDT:USDT", "15m", limit=200)

result = Hammer().detect(candles)
if result.detected:
    print(result.pattern, result.reason)
```

A future integration point: strategies could call `detect()` as an extra confirmation gate, or the
coordinator could treat `PatternResult`s as pseudo-signals.
