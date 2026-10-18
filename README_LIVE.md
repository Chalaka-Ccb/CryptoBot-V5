# CryptoBot-V5 — Bitget live engine

Branch: `BitgetEngineV1`. **Development code; not validated for real-money orders.**

## Configuration
SOL/USDT:USDT, Channel Rebound only, 15m priority over 5m, breakout expiry 3 completed 5m candles, risk 5% of equity, maximum leverage 12x, isolated margin. Actual fills differ from backtests.

## Windows
```powershell
git switch BitgetEngineV1
git pull origin BitgetEngineV1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_live_*.py" -v
.\.venv\Scripts\python.exe run_live.py --check
```
Copy `.env.example` to `.env` and add Bitget credentials. For a real Bitget account use `BITGET_DEMO=false`. Keep `LIVE_CONFIRM=` blank until conditional order handling has been tested.

## Safety controls
`STOP` blocks new entries; `FLATTEN` requests closing the position; `LOCKED` blocks entries after an incident. Never remove `LOCKED` before reconciling the actual exchange position and orders. Logs are in `data/` and `logs/`. `data/live_state.json` stores local restart state. Do not run two engine instances for the same account and symbol.

## Current limitations
- Bitget conditional SL/TP identification and automatic repair require validation on the actual Bitget account type. Current engine fails closed rather than blindly adding protection orders.
- Partial fills and ambiguous order acknowledgements require reconciliation against the exchange; do not assume an acknowledged market order has filled.
- `live/ledger.py` provides fee-aware closed-trade reconstruction but is not yet wired to the engine's trade lifecycle.
- Telegram is not implemented.
- The DigitalOcean systemd unit is a starting template, not a verified deployment.
- Read-only `--check` confirms API connectivity only. It does **not** validate real order behavior.
