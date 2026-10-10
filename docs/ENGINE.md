# `engine/` — File-by-File Deep Dive

The `engine/` package is the **orchestration layer** of CryptoBot-V5. It contains no trading
logic itself (that lives in `strategies/`) and no risk maths (that lives in `risk/`). Instead it
*wires* those pieces together into a deterministic, per-symbol decision pipeline and keeps the
authoritative account/position book in one place.

```
TradingEngine ──uses──▶ StrategyCoordinator ──calls──▶ strategies/*.generate_signal()
     │                        │
     │                        └── returns TradingSignal | None
     ├──uses──▶ RiskManager ──calls──▶ risk/position_sizing + risk/risk_reward
     ├──uses──▶ ExecutionEngine ──delegates to──▶ Broker (ABC) → PaperBroker / real broker
     ├──uses──▶ PositionManager ──reads/writes──▶ EngineState
     └──uses──▶ DailyDrawdownGuard (risk/daily_drawdown.py)
```

---

## 1. `engine/state.py` — `EngineState`

**Purpose:** the single source of truth for everything the bot currently "has".

A mutable `@dataclass` holding:

| Field | Type | Meaning |
|---|---|---|
| `account` | `Account` | Balance, equity, PnL snapshot |
| `active_orders` | `dict[order_id → Order]` | Every order submitted (keyed by ID) |
| `positions` | `dict[symbol → Position]` | At most **one position per symbol** (dict keyed by symbol enforces this structurally) |
| `trades` | `list[Trade]` | Append-only journal of every trade ever opened |

**Key methods / how they work:**

- `has_active_order(symbol)` — scans `active_orders.values()` and returns `True` if any order for
  that symbol has status in `{PENDING, OPEN, PARTIALLY_FILLED}` (via `Order.is_active`).
- `has_open_position(symbol)` — dict lookup + `Position.is_open`.
- `symbol_is_busy(symbol)` — the composition of the two above. This is *the* rule that guarantees
  "one live exposure per symbol"; both `TradingEngine.process_symbol()` and
  `PositionManager.open_position()` call it as a guard.
- Mutators: `add_order`, `add_position`, `add_trade`, `remove_position`. Positions are removed on
  close so a symbol becomes free again; trades stay forever as history.

**Design note:** keeping state in one object means the engine itself is nearly stateless — you can
snapshot/replay/serialize `EngineState` without touching engine internals.

---

## 2. `engine/execution_engine.py` — `Broker` ABC + `ExecutionEngine`

Two tiny classes that form the boundary between "the bot decided" and "the exchange executed".

### `Broker` (Abstract Base Class)
```python
class Broker(ABC):
    @abstractmethod
    def submit_order(self, order: Order) -> Order: ...
    @abstractmethod
    def cancel_order(self, order_id: str) -> None: ...
```
Any venue adapter (paper, Bybit REST, WebSocket, …) only needs to implement these two methods.
`submit_order` must return the same `Order` object with updated `status`, `filled_quantity`,
`average_fill_price`, and `exchange_order_id`.

### `ExecutionEngine`
A thin facade constructed with a `Broker`:
- `submit(order)` → `broker.submit_order(order)`
- `cancel(order_id)` → `broker.cancel_order(order_id)`

**Why wrap it?** It gives the engine one choke point to later add retries, idempotency keys,
logging, or rate limiting without changing `TradingEngine`. The current concrete implementation
is `brokers/paper/broker.py::PaperBroker`, which instantly marks orders `FILLED` at their limit
price (or stop price if no limit price), setting `filled_quantity = quantity` and an
`exchange_order_id` of the form `PAPER-<order_id>`; `cancel_order` is a no-op.

---

## 3. `engine/strategy_coordinator.py` — Multi-strategy, multi-timeframe arbitration

**Purpose:** decide *which* strategy's signal wins for a symbol on this bar.

Data structures:
- `StrategyEvaluation(timeframe: str, signal: TradingSignal | None)` — frozen result.
- Constructor takes two ordered lists: `strategies_15m` and `strategies_5m` (list order = priority
  order within a timeframe).

`evaluate(candles_15m, candles_5m)` algorithm:

1. **15m has priority.** Run `_evaluate_strategies(strategies_15m, candles_15m)`. If any strategy
   returns a non-`None` signal, stop immediately and return `("15m", signal)`.
2. **Only if 15m produced nothing**, run the 5m list against `candles_5m`; first hit wins.
3. Otherwise return `("none", None)`.

`_evaluate_strategies` is a static loop: it computes `current_index = len(candles) - 1` (always
evaluate on the **last closed candle**) and calls
`strategy.generate_signal(candles, current_index)` sequentially — **first-come-first-served**, so
reordering the constructor lists changes behaviour. Empty candle lists short-circuit to `None`.

**Contract expected of strategies:** duck-typed objects exposing
`generate_signal(candles: list[Candle], index: int) -> TradingSignal | None`. No base class is
enforced, which keeps strategies dependency-light.

---

## 4. `engine/risk_manager.py` — Signal approval & sizing gatekeeper

**Purpose:** convert an approved *idea* (signal) into an executable *plan* (size + TP) — or reject it.

- `RiskDecision` (frozen dataclass): `approved: bool`, optional `PositionSizeResult`, optional
  `RiskRewardResult`, and a human-readable `reason`. Every rejection path fills `reason` so the
  engine can log exactly why a trade didn't happen.

- `RiskManager(account, risk_percentage=0.02, default_risk_reward=3.0)` holds a reference to the
  shared `Account` — sizing always uses the **live balance**.

`evaluate(signal, entry_price)` step by step:

1. **Validation gates** (rejects):
   - `entry_price <= 0` → *"Entry price must be greater than 0"*
   - `signal.stop_loss is None` → *"Signal does not provide a stop-loss"*
     (this bot refuses to size a trade without a defined risk point — fail-safe design)
   - side string not `long`/`short` → *"Unsupported signal side"*
2. **Position sizing** via `risk/position_sizing.calculate_position_size`:
   `max_risk_amount = balance × 2%`, `risk_per_unit = |entry − stop|`,
   `quantity = max_risk_amount / risk_per_unit`. So every trade risks a constant % of equity.
3. **Take-profit**:
   - If the strategy already supplied `signal.take_profit` (e.g. Bollinger channel target or
     Setup-1-2-3-4 swing high), the manager just *echoes* it back inside a `RiskRewardResult`
     whose `risk_reward_ratio` is computed as `|TP−entry| / |entry−SL|` (informational).
   - If the strategy left TP empty (FFFD, Williams %R, EMA crossover…), the manager applies the
     **default 3:1 reward** via `risk/risk_reward.calculate_take_profit`:
     long ⇒ `entry + 3·risk_distance`, short ⇒ `entry − 3·risk_distance`.
4. Returns `approved=True` with both results attached.

Note: `RiskManager` never raises on bad prices from callers — it converts them into soft rejections
(`approved=False`), while the underlying pure functions in `risk/` raise hard `ValueError`s for
programming errors (equal entry/stop, zero capital…).

---

## 5. `engine/position_manager.py` — Position lifecycle bookkeeping

Wraps `EngineState` mutations so open/update/close logic exists in exactly one place.

### `open_position(...)`
1. Re-checks `state.symbol_is_busy(symbol)` and raises `ValueError` if busy — a second line of
   defence beyond the engine's early return.
2. Generates sequential IDs: `POS-000001`, `TRD-000001` (based on current counts).
3. Creates a `Position` seeded with `current/highest/lowest_price = entry_price` plus SL/TP and
   originating `strategy` name (highest/lowest feed future trailing-stop logic).
4. Creates the matching `Trade` record and appends both to state (`positions[symbol]`,
   `trades.append`). The Trade journal is what backtest/live reporting is built from.

### `update_price(symbol, price)`
Called on every tick/bar. Silently no-ops if there is no open position, otherwise refreshes
`current_price` and ratchets `highest_price`/`lowest_price` — the running extremes used by ATR
and swing trailing stops.

### `close_position(symbol, exit_price, exit_reason, timestamp, fees=0.0)`
1. Requires an open position (else `ValueError`).
2. Flips `Position.status → CLOSED`, stamps `closed_at`, `exit_price`, `exit_reason`
   (`ExitReason.STOP_LOSS / TAKE_PROFIT / STRATEGY_EXIT / TRAILING_STOP / DAILY_DRAWDOWN / MANUAL …`).
3. Walks `state.trades` **in reverse** to find the still-open trade for that symbol and calls
   `trade.close(...)`, which computes gross/net PnL (`(exit−entry)×qty` for longs, inverted for
   shorts, minus fees). Reverse scan assumes the newest open trade for a symbol is the correct one
   (consistent with one-position-per-symbol).

⚠️ Current gap: `close_position` updates the Position/Trade but does **not** call
`state.remove_position(symbol)` nor credit PnL back to `Account.balance` — wiring those up is a
TODO before live use.

---

## 6. `engine/trading_engine.py` — The master pipeline

Contains `EngineDecision` (frozen result object: symbol, timeframe, signal, order, executed flag,
reason) and the `TradingEngine` class, which composes all five components above plus a
`DailyDrawdownGuard`.

### `process_symbol(symbol, candles_15m, candles_5m, timestamp)` — full walkthrough

Every exit below returns an `EngineDecision(executed=False, reason=...)` so callers get a uniform,
auditable answer.

1. **Concurrency guard** — `state.symbol_is_busy(symbol)` → reject if there is already an active
   order or open position for the symbol.
2. **Global kill-switch** — `daily_drawdown_guard.check(current_balance=account.balance, ...)`.
   If the day's drawdown ≥ limit (default 5%), reject with *"Daily drawdown limit reached"*.
   ⚠️ Note: `risk/daily_drawdown.py` currently exposes `update(balance, day)` rather than
   `check(...)`; this interface mismatch must be fixed before running live.
3. **Signal generation** — delegates to `StrategyCoordinator.evaluate` (15m priority, then 5m).
   No signal → reject *"No strategy signal"*.
4. **Entry-price resolution** — `_resolve_entry_price(signal, candles_15m, candles_5m)`:
   - `signal.trigger_price` set → use it directly (covers breakout/close-triggered strategies).
   - `entry_timing == CURRENT_CLOSE` → last candle's `close` (falls back across timeframes).
   - `entry_timing == NEXT_OPEN` → last candle's `open` (the strategy intends to enter on the
     *following* bar's open; the scheduler outside the engine handles the wait).
   - Anything else → `None` → reject *"Entry price could not be resolved"*.
5. **Risk approval** — `RiskManager.evaluate(signal, entry_price)`; rejection reason propagated
   verbatim. Defensive `None` checks on both `position_size` and `risk_reward` results.
6. **Order construction** — `_build_order`:
   - Sequential ID `ORD-000001…`.
   - If the signal carries a `trigger_price` the engine builds a **STOP order**
     (`stop_price = trigger`, `price = None`) — i.e. breakout entries become conditional orders.
   - Otherwise a **MARKET order** priced at the resolved entry.
   - Side mapping: LONG→BUY, SHORT→SELL. Status starts `PENDING`; strategy name + reason travel
     with the order for audit.
7. **Submission** — `ExecutionEngine.submit(order)`. If the returned status ≠ `FILLED`
   (rejected/expired/partially handled elsewhere) → reject *"Order was not filled"*.
8. **Fill reconciliation** — the **actual average fill price** takes priority over the planned
   entry when opening the position; filled quantity falls back to requested quantity.
9. **Take-profit selection** — strategy-provided TP wins; otherwise the RiskManager's default
   3:1 computed target is stored on the position.
10. **Open position** — `PositionManager.open_position(...)` records the Position + Trade pair,
    returning `EngineDecision(executed=True, reason="Order filled and position opened")`.

### Helper mappers
- `_position_side(SignalSide) → PositionSide` and `_order_side(SignalSide) → OrderSide` are small
  total functions that raise `ValueError` on unknown enum values (defensive against future sides).

### What the engine deliberately does NOT do yet
- Exit management (SL/TP monitoring, `should_exit_long` hooks, trailing stops) — implemented in
  strategies/risk modules but not scheduled by `TradingEngine`.
- OCO handling for NR7's dual signals (documented in `nr7.py`'s docstring as engine responsibility).
- Persisting `EngineState` or emitting events/metrics.

---

## 7. `engine/__init__.py` — Public API

Re-exports the whole façade so consumers can simply write
`from engine import TradingEngine, EngineState, StrategyCoordinator, ...`. The exported names are:
`Broker`, `ExecutionEngine`, `PositionManager`, `RiskDecision`, `RiskManager`, `EngineState`,
`StrategyCoordinator`, `StrategyEvaluation`, `EngineDecision`, `TradingEngine`.

---

## How to assemble a live `TradingEngine` (wiring example)

```python
from core.models.account import Account
from engine import (
    EngineState, ExecutionEngine, PositionManager, RiskManager,
    StrategyCoordinator, TradingEngine,
)
from brokers.paper import PaperBroker
from risk.daily_drawdown import DailyDrawdownGuard
from backtesting.strategy_setup import create_strategy_coordinator

account = Account("MAIN", "USDT", initial_balance=10_000, balance=10_000)
state   = EngineState(account=account)

engine = TradingEngine(
    state=state,
    strategy_coordinator=create_strategy_coordinator(),
    risk_manager=RiskManager(account),
    position_manager=PositionManager(state),
    execution_engine=ExecutionEngine(PaperBroker()),
    daily_drawdown_guard=DailyDrawdownGuard(limit_percentage=0.05),
)

decision = engine.process_symbol("BTC/USDT:USDT", candles_15m, candles_5m, now)
print(decision.executed, decision.reason)
```

An external scheduler (not yet in the repo) is expected to fetch candles, call
`process_symbol` per closed bar, and periodically call `PositionManager.update_price` /
`close_position` for exits.
