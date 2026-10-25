# Fibonacci Scalping 1m — first implementation

Based on user-supplied 1-Minute Fibonacci Scalping Strategy Guide.md.

- Confirm pivots with 3 candles on each side; this deliberately delays recognition and avoids lookahead.
- Require higher-high/higher-low (long) or lower-high/lower-low (short) pivot structure.
- Detect close-confirmed break of structure; create a resting LIMIT order at the 0.618 retracement of the last swing leg.
- Stop beyond the originating swing by 0.05%, target the break's extreme (Fib 0.0); minimum 1R.
- Pending orders expire after the runner's configured `breakout_expiry_candles` (3 by default). This is a simplification of the guide's invalidation rule.
- **Limit fills are simulated**, not exchange maker queue fills; existing broker charges taker fees by default, conservatively.
- The guide's discretionary 10–15 minute stall exit and resetting the grid on every new BoS are not implemented yet.
- The shared live engine does not yet implement EntryTiming.LIMIT. Do not enable this strategy for live execution until limit-order handling is added.
- For isolated 1m backtesting: load market data with `include_1m=True`, configure `BacktestRunner(execution_timeframe="1m", ...)`, and register FibonacciScalpingStrategy in `strategies_1m`.
- **Do not run this alongside 5m/15m strategies for initial comparison**; isolate strategy/timeframe.
