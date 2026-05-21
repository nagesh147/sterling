# Hybrid VCP-Momentum Scalper — Strategy V2 Specification

## Overview

**Name:** Hybrid VCP-Momentum Scalper (Strategy V2)
**Type:** Intraday algorithmic trading strategy — BTC & ETH perpetual futures
**Core Idea:** Adapt between mean-reversion (volatility contraction) and momentum breakout (volatility expansion) modes, confirmed by microstructure proxies, targeting high Sharpe + low drawdown.
**Backtest Data:** OHLCV only from `sterling_paper.db` (SQLite). Real OBI/CVD from Delta WebSocket for live augmentation.

---

## Folder Structure

```
backend/app/engines/hybrid_vcp/
├── __init__.py
├── indicators.py       # All OHLCV-based technical indicators
├── microstructure.py   # CVD_proxy + OBI_proxy + flow_score + divergence
├── signals.py          # Mode detection + hybrid entry signal generation
├── entries.py          # Entry conditions (all gates composed)
├── exits.py            # Stop, TP, Chandelier trail, time stop, trend flip
├── profiles.py         # Strategy profiles (TF configs, thresholds)
├── backtest.py         # Vectorised backtest replay engine
└── live_filters.py     # Real OBI/CVD from WebSocket (live-only gate)
```

---

## Indicators (`indicators.py`)

Pure functions, no I/O, array-based (`np.ndarray`).

| Indicator | Formula | Purpose |
|---|---|---|
| ATR(14) | Wilder's RMA | Stop/TP sizing, vol filter |
| ATR percentile | Rank of ATR(14) vs 50-bar lookback → 0–100 | Vol filter gate |
| BB(20,2) width | `(BB_high - BB_low) / BB_mid` | VCP detection |
| BB width percentile | Rank of BB width vs 50-bar lookback → 0–100 | VCP threshold |
| RSI(14) | Standard RSI | Momentum + reversion entry |
| EMA(8), EMA(21) | Exponential moving averages | Trend, crossover signal |
| Volume SMA(20) | Rolling mean of volume | Volume spike detection |
| IBS | `(close - low) / (high - low)` | Internal bar strength (0–1) |
| Pivot high/low | Rolling max/min over configurable window | Breakout pivot detection |

---

## Mode Detection (`signals.py`)

Per bar, computed from signal-TF candles:

```python
if bb_width_percentile < 30:
    mode = "COMPRESSION"   # Favor reversion + tighter microstructure
else:
    mode = "EXPANSION"     # Favor momentum breakout
```

---

## Entry Signals (`signals.py` + `entries.py`)

### Entry Priority (ordered filter chain)

1. **Volatility Filter** — ATR percentile must be > 35 (not dead quiet)
2. **Mode Detection** — COMPRESSION or EXPANSION
3. **Hybrid Signal** — reversion (compression) OR breakout (expansion)
4. **Microstructure Confirmation** — flow_score + no divergence
5. **Activity Filter** — volume > 0.5 × vol_sma_20 (skip dead bars)
6. **Funding Bias** — stubbed to 0 in backtest; real in live mode

---

### COMPRESSION Mode (Mean-Reversion)

```
LONG  = IBS ≤ 0.35 AND RSI ≤ 40 AND bb_width_pct < 30
SHORT = IBS ≥ 0.65 AND RSI ≥ 60 AND bb_width_pct < 30
```

### EXPANSION Mode (Momentum Breakout — primary)

```
LONG  = price breaks pivot_high(4-10 bars)
        AND EMA8 > EMA21
        AND RSI crosses above 52
        AND volume > 1.25 × vol_sma_20
SHORT = mirror
```

---

## Microstructure (`microstructure.py`)

### CVD Proxy (backtest)
```python
cvd_proxy = volume * (close - open) / (high - low)
```

### OBI Proxy (backtest)
```python
close_location = (close - low) / (high - low)
obi_proxy = (2 * close_location - 1) * (volume / vol_sma_20)
```

### Combined Flow Score
```python
flow_score = (obi_proxy * 0.6 + cvd_momentum * 0.4)
divergence_penalty = -0.3 if divergence_detected else 0
final_score = clamp(flow_score + divergence_penalty, 0, 1)
```

### Divergence Detection
```
price breaks high BUT cvd_proxy ≤ 0 (flat/negative) → DIVERGENCE → skip/weaken
price breaks low  BUT cvd_proxy ≥ 0 → DIVERGENCE → skip/weaken
```

### Entry Microstructure Gate
```
|flow_score| must exceed threshold AND no divergence
```

---

## Exits (`exits.py`)

| Exit | Trigger |
|---|---|
| Initial stop | `entry_price - 0.9 × ATR` (long) / `entry_price + 0.9 × ATR` (short) |
| TP1 (50% close) | `entry + 1.5 × ATR` → close 50%, move stop to breakeven |
| TP2 trailing | After 0.7R profit: Chandelier trail `extreme - 0.5 × ATR`, ratchet only |
| Time stop | `hold_bars` elapsed (profile-specific) |
| Trend flip | Signal trend reverses → exit remaining position |

---

## Risk Parameters

- **Risk per trade:** 0.5% of equity
- **Leverage:** Dynamic 5×–50× — higher in low-vol ( ATR percentile low)
- **Max concurrent positions:** 2
- **Daily loss limit:** -2.5% → stop trading for the day
- **Kelly fraction cap:** 0.5 (conservative)

---

## Profiles (`profiles.py`)

| Profile | Signal TF | Regime TF | hold_bars | Direction |
|---|---|---|---|---|
| btc_scalping_15m | 15m | 1h | 16 | both |
| btc_scalping_30m | 30m | 2h | 12 | both |
| eth_scalping_15m | 15m | 1h | 16 | both |
| eth_scalping_30m | 30m | 2h | 12 | both |

---

## Backtest (`backtest.py`)

- **Fill price:** Next bar open (no signal-bar close — no look-ahead)
- **Cost model:** Slippage (tiered) + taker fees (0.05% RT) + funding accrual (stubbed 0)
- **Data source:** `sterling_paper.db` via existing `db.py` candle loader
- **Output:** Trades list + equity curve + PerformanceReport (Sharpe, PF, win rate, max DD, CAGR)

---

## Live Filters (`live_filters.py`)

Active only when `deploy_mode == "live"`. Not used in backtest.

- **Real OBI:** Weighted top-10 levels from `l2_orderbook` WebSocket channel
- **Real CVD:** Cumulative aggressor side from `recent_trade` WebSocket channel
- **Final gate:** Real OBI/CVD must confirm entry direction; fallback to proxy if data gap
- **Funding:** Real funding rate from `funding` channel; filter |funding| > 0.08%

---

## Options Leg (Live Enhancement — Not Backtested)

- Buy ATM calls/puts (delta 0.40–0.55, DTE 7–14 days)
- Size: 20–25% of futures risk
- Exit: On futures signal OR ±25–35% premium
- Greeks monitoring: delta, gamma, theta, vega
- **Not backtested — documented as live-only enhancement**

---

## Reusing Existing Files

| Need | Source |
|---|---|
| Candle schema | `app.schemas.market.Candle` |
| ATR calculation | `app.engines.indicators.atr.compute_atr` |
| Slippage model | `app.engines.risk.slippage.slippage_bps` |
| Cost attribution | `app.engines.backtest.costs.compute_trade_costs` |
| Cooldown (optional) | `app.engines.risk.cooldown` |
| Kelly ruin guard | `app.engines.directional.kelly_ruin` |
| Walk-forward split | `app.engines.backtest.sweep.walk_forward_split` |
| DB candle loader | `app.services.db.py` |

---

## Target Metrics (conservative, fee & slippage adjusted)

- Win Rate: 65–73%
- Profit Factor: 2.4–3.1
- Sharpe: 2.5–3.4
- Max Drawdown: 10–18%
- Trades/Day: 10–24 (15m profile)

---

## Data Limitations (Documented)

- **Backtest:** OHLCV only — microstructure uses high-quality proxies derived from candle internals. Results = conservative lower bound.
- **Live:** Full OBI (L2 orderbook) + CVD (tick data) + real funding from Delta WebSocket add confirmed alpha.
- **Options:** Not backtested. Live-only via Delta REST + Greeks monitoring.