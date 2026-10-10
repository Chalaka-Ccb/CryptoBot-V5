# `strategies/` and `indicators/` — File-by-File Explanation

This document explains **every indicator** in `indicators/` (the maths building blocks) and
**every strategy** in `strategies/` (the signal generators), how each is implemented, and which
other modules use them.

### The common strategy contract

Every strategy is a plain class with:

```python
name: str                                  # identifier stored on every signal
def generate_signal(candles: list[Candle], index: int) -> TradingSignal | None
```

It returns a frozen `TradingSignal` (`core/models/signal.py`) carrying:
`strategy`, `side` (LONG/SHORT), `candle_index`, `entry_timing`
(`CURRENT_CLOSE` / `NEXT_OPEN` / `BREAKOUT`), `trigger_price`, `stop_loss`,
optional `take_profit`, and a human-readable `reason`. Returning `None` simply means
"no setup on this bar". Some strategies add exit helpers (`should_exit_long`, `trailing_stop`).

Signals are consumed by `engine/strategy_coordinator.py` (live + backtest) and turned into orders
by `engine/trading_engine.py`; sizing/TP defaults come from `engine/risk_manager.py`.

---

# PART A — Indicators (`indicators/`)

All indicators are **pure functions**: input `list[Candle]`, output a parallel list where warm-up
positions are `None`. No state, no side effects, easy to test.

## 1. `indicators/ema.py` — `calculate_ema(candles, period)`
Classic EMA seeded with an SMA:
1. Validate `period > 0`; return all-`None` if fewer candles than `period`.
2. First value at index `period-1` = `SMA(first `period` closes)`.
3. Then recursive smoothing: `EMA_t = (close_t − EMA_{t−1}) × k + EMA_{t−1}` with multiplier
   `k = 2/(period+1)`.
**Used by:** `EMACrossoverStrategy` (8/21), `Setup1234Strategy` (trend filters 200 & 21),
`risk/trailing/ema9.py` (trailing stop).

## 2. `indicators/atr.py` — True Range + ATR
- `calculate_true_range(candles)`: TR₀ = high−low; for later bars
  `TR = max(high−low, |high−prev_close|, |low−prev_close|)` — captures gaps.
- `calculate_atr(candles, period=14)`: first ATR = SMA of the first `period` TRs, then
  **Wilder smoothing** `ATR_t = (ATR_{t−1}×(period−1) + TR_t)/period`. Returns parallel list with
  `None` warm-up. Also defines an `ATRValue` wrapper dataclass.
**Used by:** `risk/trailing/atr.py` (ATR trailing stop). ADX computes its own TR inline instead.

## 3. `indicators/bollinger_bands.py` — `calculate_bollinger_bands(candles, period=20, std_multiplier=2.0)`
Per bar (once `period` closes exist), over the rolling close window:
- `middle = SMA(window)`
- population variance `σ² = Σ(p−mean)²/period`, `upper/lower = middle ± multiplier·σ`
- `bandwidth = (upper − lower) / middle` (volatility-normalised channel width; guard against
  zero middle → 0.0)
Returns `BollingerBands` frozen dataclasses (middle, upper, lower, std, bandwidth).
**Used by:** FFFD, Squeeze, Channel-Rebound strategies. Bandwidth is the squeeze detector's core
statistic.

## 4. `indicators/macd.py` — `calculate_macd(candles, fast=12, slow=26, signal=9)`
Contains a private `_ema(values, period)` helper (same SMA-seeded algorithm as `ema.py` but works
on any float list). Steps:
1. Fast EMA and slow EMA of closes; `macd_line_i = fast_i − slow_i` where both defined.
2. Signal line = EMA(`signal_period`) computed **only over the valid MACD values** (they are
  compacted into a dense list first, so the signal EMA isn't distorted by `None` warm-ups).
3. Emit `MACDValue(macd_line, signal_line, histogram = macd − signal)` aligned back to candle
   indices via a running `signal_index`.
Validates `fast < slow`. **Used by:** `HiLoMACDStrategy` (bullish filter `macd > signal`).

## 5. `indicators/williams_r.py` — `calculate_williams_r(candles, period=14)`
Larry Williams %R: over each rolling window,
`%R = ((highest_high − close) / (highest_high − lowest_low)) × −100`, range 0 → −100.
Guard: if the window has zero price range (flat market) emit `None` instead of dividing by zero.
Also ships a `WilliamsRConfig(period=14)` dataclass.
**Used by:** momentum `WilliamsRStrategy` (oversold −80 recovery entry, overbought −20 exit).

## 6. `indicators/hilo_activator.py` — `calculate_hilo_activator(candles, period=3)`
A step-wise trend-flip line (Doug Ross' Hi-Lo Activator):
- Two reference lines: `bearish_line = SMA(highs, period)` and `bullish_line = SMA(lows, period)`.
- State machine carried across bars (`previous_line`, `previous_trend`):
  - Initial: bullish if close ≥ bullish_line else bearish.
  - While bearish: if close crosses **above** previous line → flip BULLISH, track bullish_line.
  - While bullish: if close crosses **below** previous line → flip BEARISH, track bearish_line.
  - Otherwise stay in current trend and keep following that side's line.
- Emits `HiLoValue(line, trend, bullish_line, bearish_line)` per bar (None during warm-up).
**Used by:** `HiLoMACDStrategy` (entry flip detection, dynamic stop, exit rule).

## 7. `indicators/adx.py` — `calculate_adx(candles, period=14)`
Directional-movement strength (simplified, non-smoothed ADX):
1. Per bar compute `TR`, `+DM = up_move if up_move>down_move and >0 else 0`,
   `−DM = down_move if down_move>up_move and >0 else 0` where
   `up_move = high−prev_high`, `down_move = prev_low−low`.
2. For each bar after warm-up, sum TR/+DM/−DM over the last `period` bars, then
   `+DI = 100·Σ+DM/ΣTR`, `−DI = 100·Σ−DM/ΣTR`,
   `DX = 100·|+DI − −DI| / (+DI + −DI)` stored as the "ADX" value (zero-division guarded).
**Used by:** `ChannelReboundStrategy` as a regime filter — only trade when DX < threshold (20),
i.e. *weak trend / ranging market*.

## 8. `indicators/volume.py` — `calculate_volume_sma(candles, period=20)`
Simple moving average of `candle.volume` with `None` warm-up.
**Used by:** `EMACrossoverStrategy` (volume confirmation), `BollingerSqueezeStrategy`
(above-average volume requirement).

## 9. `indicators/volume_spike.py` — `calculate_volume_spike(candles, index, period=20, minimum_ratio=1.5)`
Single-bar breakout-volume checker (deliberately index-based rather than whole-series):
- `volume_sma` over the window ending at `index`; `ratio = current_volume / volume_sma`;
  `confirmed = ratio >= minimum_ratio`.
- Returns `VolumeSpikeResult(volume, volume_sma, ratio, confirmed)`; `confirmed=False` when there
  aren't enough bars or the SMA is ≤ 0.
**Status:** implemented but not yet referenced by any shipped strategy (reserved for stricter
breakout confirmation, e.g. NR7/Squeeze upgrades).

---

# PART B — Strategies (`strategies/`)

## Trend group (`strategies/trend/`)

### `trend/config.py` — `MovingAverageCrossoverConfig`
Frozen defaults: `fast_period=8`, `slow_period=21`, `volume_period=20`,
`stop_mode="ema21"` (alternative `"recent_swing_low"`), `swing_lookback=5`, `stop_buffer=0.0`.

### `trend/ema_crossover.py` — `EMACrossoverStrategy` (`name="ema_8_21_crossover"`)
**Idea:** ride fresh momentum shifts confirmed by participation.
Entry logic (`generate_signal`):
1. Compute EMA-fast and EMA-slow series; need both at `index−1` and `index`.
2. **Golden cross:** `fast(t−1) ≤ slow(t−1)` **and** `fast(t) > slow(t)`.
3. **Volume filter:** `volume(t) > VolumeSMA20(t)` (strictly greater, else no signal).
4. Entry = current candle **close** (`EntryTiming.CURRENT_CLOSE`, trigger_price=close).
5. Stop-loss from `_calculate_stop_loss`: either the EMA-21 value itself minus buffer, or the
   minimum low of the last `swing_lookback` candles minus buffer; unknown mode raises. If
   stop ≥ entry the setup is invalid → `None`.
6. No take-profit ⇒ RiskManager later applies the default 3:1 target.
Exit helper `should_exit_long(candles, index)`: mirror-image **death cross**
(`fast(t−1) ≥ slow(t−1)` and `fast(t) < slow(t)`).
**Registered in:** `backtesting/strategy_setup.py` for both 15m and 5m lists.

### `trend/hilo_macd.py` — `HiLoMACDStrategy` (`name="hilo_macd"`)
**Idea:** enter trend flips only when MACD agrees, and trail with the Hi-Lo line.
Constructor params: `hilo_period=3`, MACD 12/26/9.
Entry (`generate_signal`):
1. **MACD trend filter:** `macd_line > signal_line` (bullish momentum context).
2. **Hi-Lo flip:** previous state was BEARISH and current close crossed above the previous
   Hi-Lo line → structural trend change.
3. Both must hold. Emits LONG with `EntryTiming.NEXT_OPEN` — the docstring explicitly notes it
   "doesn't pretend the current close is the entry price"; trigger_price carries the current
   close as a reference while the engine/backtester executes at next bar open.
4. Stop = current Hi-Lo line (dynamic, rises with the trend).
Exit helpers: `should_exit_long` = close below current Hi-Lo line; `trailing_stop` = current
Hi-Lo line value (a ready-made trailing mechanism other components can call).
**Registered in:** `backtesting/strategy_setup.py` (both timeframes).

## Bollinger group (`strategies/bollinger/`)

### `bollinger/config.py` — `BollingerConfig`
Shared knobs: band `period=20`, `std_multiplier=2.0`; FFFD execution window 2 & trigger offset
0.01; squeeze lookback 20 / volume period 20; channel-rebound ADX period 14, threshold 20.0,
band-touch tolerance 0.002; universal `stop_buffer_percent=0.001`.

### `bollinger/fffd.py` — `FFFDStrategy` (`name="fffd"`)
Portuguese *"Fechou Fora – Fechou Dentro"* (closed outside – closed inside), a mean-reversion
pattern at the band edges:
- **Bullish:** previous candle **closed below** the lower band, current candle **closed back
  above** it → LONG. Trigger = current high + 0.01 offset (buy-stop just above the signal bar);
  stop = current low. No TP → default 3:1 applies.
- **Bearish:** mirrored on the upper band → SHORT, trigger = current low − offset, stop = current
  high.
Requires bands available at `index−1` and `index` (warm-up handled by `None` checks).

### `bollinger/squeeze.py` — `BollingerSqueezeStrategy` (`name="bollinger_squeeze"`)
Volatility-compression breakout:
1. Gather historical `bandwidth` values over the previous `squeeze_lookback` bars.
2. **Was squeeze:** previous bar's bandwidth equals the minimum of that history (channel at its
   tightest).
3. **Expansion:** current bandwidth strictly greater than previous bandwidth.
4. **Volume confirm:** current volume > VolumeSMA(20).
5. Direction from the breakout candle: close above upper band ⇒ LONG (trigger=current high,
   stop=middle band); close below lower band ⇒ SHORT (trigger=current low, stop=middle band).
   Middle-band stops give a generous but trend-invalidating risk point; TP defaults to 3:1.

### `bollinger/channel_rebound.py` — `ChannelReboundStrategy` (`name="bollinger_channel_rebound"`)
The *opposite regime* play — fade the bands, but **only in ranges**:
1. **Regime filter:** ADX/DX value must be **below** `adx_threshold` (20). Strong trends disable
   the strategy entirely.
2. **Long rebound:** candle's low touches/pierces the lower band within a 0.2% tolerance, and the
   candle confirms bullishly (green body closing back above the lower band). Stop = lower band
   ×(1−0.001 buffer); **take profit = upper band** (trade-to-target mean reversion — one of the
   few strategies that supplies its own TP). Trigger = current high.
3. **Short rebound:** mirrored on the upper band with a red confirmation candle; stop above the
   upper band, TP = lower band, trigger = current low.

## Breakout group (`strategies/breakout/`)

### `breakout/config.py` — `NR7Config`
`lookback=7`, `trigger_offset=0.0`, `stop_buffer=0.0` (tick-size conversion deferred to the
execution layer per comments).

### `breakout/nr7.py` — `NR7Strategy` (`name="nr7"`)
Narrow-Range-7 volatility contraction breakout (Todd Gordon style). Unique in exposing
**`generate_signals()` → list[TradingSignal]**:
1. Window = last `lookback` candles ending at `index`; compute each `high−low` range.
2. NR7 condition: current candle's range equals the window minimum (tightest bar in 7).
3. Emits **two opposite pending setups** (an OCO pair):
   - LONG: buy-stop at NR7 high + offset, stop at NR7 low − buffer.
   - SHORT: sell-stop at NR7 low − offset, stop at NR7 high + buffer.
   Both use `EntryTiming.BREAKOUT`, `take_profit=None` (→ 3:1 default), and carry explanatory
   reasons.
The class docstring assigns OCO management (place both, cancel the loser, expiry) to the Trading
Engine — that orchestration is **not yet implemented**; the coordinator consumes single-signal
strategies today.

## Momentum group (`strategies/momentum/`)

### `momentum/config.py` — `WilliamsRStrategyConfig`
`period=14`, oversold −80, overbought −20, `enter_at_close=True`, `trigger_offset=0.0`.

### `momentum/williams_r.py` — `WilliamsRStrategy` (`name="williams_r"`)
Oversold-recovery long-only momentum flip:
1. Compute %R series; require values at `index−1` and `index`.
2. **Trigger:** `%R(t−1) ≤ −80` **and** `%R(t) > −80` — oscillator crossing back *up out of*
   the oversold zone (recovery confirmation, not blind bottom-fishing).
3. **Entry:** config switch — `enter_at_close=True` uses the current close as trigger price;
   otherwise current high + offset (breakout style).
4. **Stop-loss (`_find_oversold_low`):** walks backwards through consecutive oversold bars and
   takes the lowest low of the whole oversold sequence — because the signal candle alone isn't
   necessarily the dip's bottom. Stops immediately when %R leaves the zone or hits `None`.
5. **Exit (`should_exit_long`):** %R previously above −20 (overbought) and now falling — take
   money off the table at the top of the range.

## Pullback group (`strategies/pullback/`)

### `pullback/config.py` — `Setup1234Config` + `PullbackTrendFilter` enum
Options: trend filter `EMA_200` (default) or `EMA_21_SLOPE`; periods 200/21; trigger offset;
stop buffer; optional `risk_reward_ratio=2.0`; `use_previous_swing_high=True`.

### `pullback/setup_1234.py` — `Setup1234Strategy` (`name="setup_1234"`)
Larry Connors-style countertrend pullback **inside an established uptrend**:
1. **Pattern:** three consecutive lower lows ending at the current bar
   (`low[t−2]<low[t−3]`, `low[t−1]<low[t−2]`, `low[t]<low[t−1]`) — capitulation/dip.
2. **Trend filter (`_trend_is_valid`):** either close > EMA-200 (major uptrend), or close > EMA-21
   *and* EMA-21 rising (slope variant). Fails if EMAs still warming up.
3. **Entry:** buy-stop above the dip bar's high (`EntryTiming.BREAKOUT`) + offset — you only join
   once the selling pressure actually reverses.
4. **Stop:** bar-4 low − buffer; sanity check aborts if stop ≥ trigger.
5. **Take-profit (`_calculate_take_profit`):** prefer the previous swing high (bar-1's high) when
   it sits above the trigger; otherwise fall back to `trigger + risk × 2.0`; otherwise `None`
   (RiskManager 3:1 default).
Docstring again defers order creation/expiry to the engine.

## Package exports
Each sub-package `__init__.py` re-exports its strategy classes
(`FFFDStrategy`, `BollingerSqueezeStrategy`, `ChannelReboundStrategy`, `NR7Strategy`,
`WilliamsRStrategy`, `Setup1234Strategy`, `EMACrossoverStrategy`, `HiLoMACDStrategy`) so callers
can `from strategies.trend import EMACrossoverStrategy` etc.

`backtesting/strategy_setup.py::create_strategy_coordinator()` currently wires only the two trend
strategies (`EMACrossoverStrategy`, `HiLoMACDStrategy`) into both the 15m and 5m lists — the
template for adding the others.

---

## Strategy ↔ Indicator ↔ Consumer summary

| Strategy | Indicators used | Own TP? | Exit helper | Entry timing |
|---|---|---|---|---|
| `ema_8_21_crossover` | EMA(8,21), Volume SMA(20) | ✗ (3:1 default) | `should_exit_long` (death cross) | CURRENT_CLOSE |
| `hilo_macd` | Hi-Lo Activator(3), MACD(12/26/9) | ✗ | `should_exit_long`, `trailing_stop` | NEXT_OPEN |
| `fffd` | Bollinger Bands(20,2) | ✗ | — | BREAKOUT trigger |
| `bollinger_squeeze` | BB bandwidth, Volume SMA(20) | ✗ | — | BREAKOUT trigger |
| `bollinger_channel_rebound` | BB(20,2), ADX(14) | ✓ opposite band | — | BREAKOUT trigger |
| `nr7` | none (raw ranges) | ✗ | — (OCO pair) | BREAKOUT |
| `williams_r` | Williams %R(14) | ✗ | `should_exit_long` | close or high+offset |
| `setup_1234` | EMA(200 or 21) | ✓ swing-high / 2R | — | BREAKOUT |

Unused-but-shipped indicator: `volume_spike.calculate_volume_spike` (standalone confirmation
helper awaiting a consumer).
