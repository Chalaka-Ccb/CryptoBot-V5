# CryptoBot-V5 — Bitget Live V1

**Branch:** `BitgetEngineV1` (not `main`)

**Status:** development / demo verification required. **Do not use real funds yet.**

## Trading rules
- Bitget USDT-M futures, `SOL/USDT:USDT` only.
- **ChannelReboundStrategy** only; reuse the existing backtest coordinator and Bollinger configuration.
- 15m signals take priority at 15m close; otherwise evaluate 5m. Only closed candles are used.
- Channel Rebound uses ADX, Bollinger Bands and RSI; its own breakout trigger, stop-loss and take-profit are preserved.
- Pending breakout entries expire after 3 completed 5m candles. A live trigger uses the observed market price, not simulated intrabar fills.
- Risk is **5% of equity** per trade, **12× maximum leverage**, not necessarily 12× exposure on every trade. Existing RiskManager applies margin, quantity and notional caps.
- Only one open position per symbol.

## Local setup (Windows / PyCharm)
```powershell
git switch BitgetEngineV1
git pull origin BitgetEngineV1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m unittest test.test_live_foundation test.test_live_sizing test.test_order_manager test.test_live_engine -v
```
Add Bitget **demo** API credentials to `.env`. Do not commit `.env`.
`python run_live.py --check` performs read-only checks of symbol, balance, candles, price, positions and trigger orders. Use your virtual environment interpreter.

## Safety
- `LIVE_CONFIRM` is blank by default. Trading operations require `LIVE_CONFIRM=YES_I_UNDERSTAND`; **do not enable yet**.
- Create `STOP` in the working directory to pause entries. Create `FLATTEN` to request cancellation and closing. `LOCKED` blocks new entries after an incident.
- Daily drawdown default 5%; repeated errors and unresolved orders lock the engine.
- State: `data/live_state.json`; logs: `data/events.jsonl`, `data/orders.jsonl`, `logs/live.log`.
- Restart requires exchange reconciliation. Unknown existing positions are locked rather than automatically adopted.
- Never assume an entry filled solely because the order API acknowledged it.

## Outstanding exchange validation before enabling orders
Bitget classic vs UTA account types and CCXT versions can expose conditional SL/TP orders differently. The protection query and identification rules **must be verified using demo responses**. Automatic SL/TP repair is deliberately disabled: unverified protection triggers flatten + LOCKED. Confirm precision, contract sizing, account setup, fill reconciliation, partial fills, cancellation semantics, close-only behavior and exchange-side protection first. Backtest intrabar fills cannot be reproduced exactly by polling live prices.

The CSV trade ledger and optional Telegram notifications are **not yet fully integrated**. The code is not production-ready until end-to-end demo tests pass.

## DigitalOcean
`deploy/cryptobot.service` is a starting systemd service. Adjust user, working directory, Python path, environment, filesystem permissions and secret management before deployment.
