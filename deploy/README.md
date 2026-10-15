# FFFD live trading on DigitalOcean

## Changes made

The live executable now defaults to **Bybit SOL/USDT:USDT**, matching
`test/backtest_broker.py`. It uses the existing shared factory in
`backtesting/strategy_setup.py` and rejects strategies other than FFFD.
Existing live execution, risk checks, exchange-side SL/TP and persistent journals
were preserved. Fixed FFFD indicator caches retaining old values when Python
reuses candle list IDs. Added read-only `--check`, graceful SIGTERM shutdown,
`requirements.txt`, a credential template, and a systemd service.

## Settings shared with the backtest

| Setting | Value |
| --- | --- |
| Strategy | FFFD on 15m and 5m, 15m priority |
| Bollinger | Period 20, standard deviation multiplier 2 |
| Stop mode | EXTREME with existing Bollinger stop buffer |
| Minimum band penetration | 0 |
| MACD exhaustion | Enabled |
| Liquidity sweep | Disabled |
| Minimum reward/risk | 2 |
| Long EMA filter | Enabled, period 200, slope lookback 0 |
| Risk per trade | 2%, subject to available margin |
| Take profit | Signal's middle band; fallback 3R |
| Default stop fallback | 1% |
| Warmup | 1000 15m candles, 3000 5m candles |
| Leverage | 10, matching shared RiskLimits |
| Margin mode | Isolated |
| Daily drawdown guard | Disabled, matching the backtest script |

Live entries occur after the confirmation candle closes. Actual market fills,
fees and latency differ from simulated close prices. Live sizing uses actual
exchange funds rather than the backtest's artificial 10,000 USDT.

## Ubuntu Droplet installation

Create an Ubuntu 24.04 Droplet with SSH access using the
[DigitalOcean quickstart](https://docs.digitalocean.com/products/droplets/getting-started/quickstart/).
Upload the complete checkout to `/opt/cryptobot`, including the existing untracked
live broker, engine, risk modules and tests. Exclude credentials and Windows virtualenvs.
Run over SSH:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv
sudo useradd --system --home /var/lib/cryptobot --shell /usr/sbin/nologin cryptobot
sudo install -d -m 700 -o cryptobot -g cryptobot /var/lib/cryptobot
sudo install -d -m 750 -o root -g cryptobot /etc/cryptobot
cd /opt/cryptobot
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
sudo .venv/bin/python -m unittest test.test_live_engine -v
sudo install -m 640 -o root -g cryptobot deploy/live.env.example /etc/cryptobot/live.env
sudo nano /etc/cryptobot/live.env
sudo install -m 644 deploy/cryptobot.service /etc/systemd/system/cryptobot.service
sudo systemctl daemon-reload
```

Enter **Bybit testnet** API credentials first. `LIVE_SANDBOX=true` selects CCXT
testnet, not Bybit Demo Trading. The module reads process environment; systemd
loads `/etc/cryptobot/live.env`. Use a trading API key restricted to the Droplet IP.
Run one engine per API account.

Read-only preflight validates credentials, account funds, markets and warmup
feeds without placing orders or changing account settings:

```bash
sudo -u cryptobot bash -c 'set -a; source /etc/cryptobot/live.env; set +a; cd /opt/cryptobot; exec .venv/bin/python -m engine.live_engine --check'
sudo systemctl enable --now cryptobot
sudo journalctl -u cryptobot -f
```

Trading starts disabled. To execute testnet orders, set
`LIVE_TRADING_ENABLED=true`, then `sudo systemctl restart cryptobot`.
Confirm an FFFD entry, attached SL/TP and position closure in the exchange UI.
Bybit's attached protection parameters are documented in its
[order API](https://bybit-exchange.github.io/docs/v5/order/create-order).

## Production

Stop with `sudo systemctl stop cryptobot`. Edit `/etc/cryptobot/live.env`:
set production API credentials, `LIVE_SANDBOX=false`,
`LIVE_TRADING_ENABLED=true` and
`LIVE_JOURNAL=/var/lib/cryptobot/live-bybit-production.json`.
Run preflight again, then `sudo systemctl start cryptobot`.
Use a separate journal for each exchange/account/environment.
No real trades were placed during development.

Bitget remains supported with `LIVE_EXCHANGE=bitget`, `BITGET_API_KEY`,
`BITGET_API_SECRET`, `BITGET_API_PASSPHRASE` and a separate journal.
`LIVE_SYMBOLS` accepts comma-separated linear USDT perpetuals.
Other environment settings are shown in `live.env.example`;
`LIVE_HISTORY` must be at least 200 for FFFD EMA warmup.

## Operations

Use `systemctl status cryptobot` and `journalctl -u cryptobot` to monitor status,
rejections and submissions. SIGTERM completes the active cycle and releases the
journal lock. Stopping leaves exchange orders and attached protection active.

API/feed failures stop the service. Automatic restart is disabled because a
submission timeout can mean an order was accepted. Inspect order history, fills,
positions and the journal client ID before restarting. Recovery of uncertain
submissions requires a unique matching open order; an already-filled uncertain
submission needs manual reconciliation. Do not delete the journal to bypass this.
Keep `/var/lib/cryptobot` across deployments.

Existing positions block new entries and are not adopted. Candle history grows
to preserve indicator seeds; monitor disk and memory on long runs. The service
needs outbound HTTPS, synchronized system time and no public application port.
Account mode/margin configuration is performed only for an idle symbol before
its first entry. Resolve exchange account configuration errors before restarting.

## Validation

```bash
python -m unittest test.test_live_engine -v
python -m engine.live_engine --help
```

Offline tests cover protected orders on both exchanges, precision/minimums,
partial fills, duplicate prevention, journal locks, timeouts, stale feeds,
disabled mode and drawdown persistence. A synthetic FFFD integration fixture
uses the actual configured strategy, EMA filter, risk sizing, protected entry,
fill reconciliation and restart (Bollinger/MACD outputs are controlled).
Actual exchange execution and Linux service operation still require verification
on your Droplet with your credentials.
