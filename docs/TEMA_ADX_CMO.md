# TEMA + ADX + CMO — implementation notes

Based on user-supplied TEMA ADX CMO Trading Strategy Guide.md.

- TEMA(9), ADX(14) > 25, directional +DI/-DI, CMO(14) above/below zero.
- Both long and short entries; only on a **new full filter alignment** to avoid repetitive entries.
- Default stop: 15.2% leveraged ROI / assumed 5x = **3.04% price movement**.
- Default TP: 12% leveraged ROI / assumed 5x = **2.4% price movement**.
- Optional reversal exit is off by default.
- Leverage is **not set by the strategy**. It must be configured separately in the broker/risk/exchange. These percentage conversions assume 5x, excluding fees/slippage.
- The source guide ambiguously calls a 12.2% example an *unleveraged* target, while also listing a 12% ROI table. This implementation explicitly interprets 12% as leveraged ROI; verify this assumption before comparing results.
- The source uses 1h candles; existing coordinator supports 5m and 15m. This strategy is **not registered yet**, pending the third strategy and the decision on timeframe/backtest support.
- Limit entry/exit order types in the guide are not implemented by TradingSignal and are not claimed here.
