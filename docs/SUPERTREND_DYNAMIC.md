# Supertrend Dynamic — first development baseline

Reference: user-provided Supertrend Trading Strategy Guide.md.

- Entry: Supertrend(10, 3) flips, close aligns with EMA(100).
- Filter: completed aggregated higher-timeframe ATR(14) > rolling 40th percentile (40 bars).
- Filter: higher-timeframe ADX(14) > volatility-scaled threshold, clamped 15–30.
- Stop: Supertrend line; dynamic trailing and exit on reverse flip.
- Execution: current candle close, both long and short.
- No strategy-defined fixed take-profit.

**Integration note:** Existing engine only accepts 5m/15m strategy inputs. Default registration uses 15m entries with 1h filters (4 complete 15m candles). Guide's example uses 1h entries with 4h filters. A future engine change can expose native 1h/4h streams.

**Important risk-model difference:** Existing risk manager applies its default 3:1 take-profit when strategy returns no TP. Thus current backtest/live implementation does NOT yet achieve the guide's pure trailing-only exit. Do not interpret its results as the guide's no-TP model.

Run: `python -m test.backtest_broker`; fee-aware broker remains enabled. The test entrypoint currently uses BTC/USDT perpetual swap and 1000 15m candles. No live execution or profitability has been verified.
