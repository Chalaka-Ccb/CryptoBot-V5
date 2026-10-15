# Live engine

The live executable runs FFFD using the backtest strategy factory and risk code.
Defaults: Bybit SOL/USDT:USDT, 2% risk, 10x isolated margin, 1000 primary
warmup candles, testnet enabled, order submission disabled.

See [changes and DigitalOcean deployment](../deploy/README.md) for exact settings,
credentials, preflight, service installation, production and recovery instructions.

```bash
python -m pip install -r requirements.txt
python -m unittest test.test_live_engine -v
python -m engine.live_engine --check
python -m engine.live_engine
```

Credentials come from process environment. The module does not load .env files.
The preflight cannot submit orders even when LIVE_TRADING_ENABLED=true.
