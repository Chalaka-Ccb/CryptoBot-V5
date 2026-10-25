# NewStratergies development branch

This branch is an independent strategy-development workspace.

## Preserved infrastructure
- Shared trading engine, strategy coordinator, execution, positions and risk
- Fee-aware backtest broker, runner, data loader and execution
- Indicators and candle pattern detectors
- Paper broker and existing backtest/fee/data-loader tests

## Adding a strategy
1. Add a Python module under `strategies/`.
2. Implement `generate_signal(candles, current_index)`, returning a `TradingSignal` or `None`.
3. Optionally implement `should_exit_long`, `should_exit_short`, or `trailing_stop`.
4. Register the strategy in `backtesting/strategy_setup.py` for the desired timeframe.
5. Run `python -m pytest test` and `python -m test.backtest_broker`.

With no registered strategies, the backtest is expected to produce zero trades. Fees remain enabled by default via `backtesting/fee_config.py`.

Old strategy implementations remain available in the `main` branch and Git history.
