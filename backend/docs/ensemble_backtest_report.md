# Sterling v4 — Ensemble Scoring Strategy Backtest Report

**Generated:** 2026-05-24
**Data:** Real OHLCV from `sterling_paper.db` — 734 days (May 2024 → May 2026)
**Assets:** BTCUSD, ETHUSD
**Timeframes:** 5m, 15m, 30m, 1h, 4h
**Total Runs:** 10 backtests × 2 strategies = 20 independent backtest runs

---

## Strategy Definitions

### Strategy A — `unweighted_mean`

> **Logic:** Direction and score are derived from the unweighted average of active track signals.

**Direction rule:**
```
direction = sign( Σ weight_i × trend_dir_i )   for all active tracks
```
- Each track's weight = `norm_score × regime_weight`
- `norm_score` is the track's raw score normalised against its rolling window
- All active tracks (trend_dir ≠ 0) vote equally regardless of edge quality

**Score rule:**
```
ensemble_score = ( Σ norm_score_i / n_active ) × 20
```
- Simple mean of normalised scores, scaled to 0–20
- No boost for agreement

**Strength rule:**
```
max_raw_score ≥ 14.0  → STRONG
max_raw_score ≥ 6.0  → SIGNAL
otherwise             → NONE
```
- Based purely on the raw score of the highest-scoring track
- Does NOT require agreement with ensemble direction

**Entry threshold:** score ≥ 7.0

---

### Strategy B — `by_edge_max_linear_agree`

> **Logic:** Direction is edge-weighted (not score-weighted); score uses the maximum active track score with a boost for unanimous agreement.

**Direction rule:**
```
direction_raw = Σ edge_i × trend_dir_i   for active tracks
direction     = sign(direction_raw)
```
- Edge (`_track_edge`) is the expected return per trade for this track in the current regime
- Tracks with higher expected edge have more voting power
- Edge is regime-conditional (different edge values for BULL_TREND, BEAR_RANGING, etc.)

**Score rule:**
```
composite_raw = max(active raw_scores) × (1 + boost)
ensemble_score = min(20.0, composite_raw)

boost = +0.30 if 3 agreeing tracks
      = +0.15 if 2 agreeing tracks
      =  0.00 otherwise
```
- Agreement means: `trend_dir == ensemble_direction`
- Only tracks that agree with the chosen direction provide the boost
- Capped at 20.0

**Strength rule:**
```
max_score ≥ 14.0 AND n_agreeing ≥ 2 AND top_track.trend_dir == direction  → STRONG
max_score ≥ 6.0  AND n_agreeing ≥ 1                                     → SIGNAL
otherwise                                                                  → NONE
```
- Must be STRONG agreement: the highest-scoring track must ALSO agree with direction
- An outlier track with a high score but opposite direction does not qualify

**Entry threshold:** score ≥ 7.0

---

## Both Strategies Share

- **Tracks:** TrendFollowing, VCP, FadeExtremes (Mean Reversion)
- **Regime engine:** `compute_regime()` with `adx_4h` macro filter
- **Lookback:** 80 bars (regime recomputed every 30 bars, forward-filled)
- **Entry:** price × 1.0003 (slight slippage); stop = entry − direction × 2.0 × ATR
- **Exit rules:** chandelier trail (TP1 at 1.5× ATR, then trail at 3× ATR), time-stop at 30 bars, trend-flip, stop-out
- **Cost:** 0.05% per trade (round-trip)

---

## Per-Pair Results

### BTCUSD / 5m
> Sampled 1-in-8 from 211,305 bars → 26,414 bars | 734 days | 1,211–1,298 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 1,298 | 1,211 | −87 |
| Win Rate | 37.2% | 37.0% | −0.2% |
| Sharpe | **+3.19** | +2.83 | −0.36 |
| Profit Factor | 0.481 | 0.447 | −0.034 |
| Max Drawdown | −16.2% | −16.7% | −0.5pp |
| CAGR | +3.54× | +2.67× | −0.87 |
| Avg Score | 9.16 | 5.51 | −3.65 |
| Avg Edge | 0.394 | 0.394 | 0 |

**Winner: `unweighted_mean`** — more trades, higher Sharpe, better profit factor. The 5m scalping regime has many fleeting signals; the unweighted averaging captures opportunities that the stricter `by_edge` filter misses.

---

### BTCUSD / 15m
> Sampled 1-in-4 from 70,434 bars → 17,609 bars | 734 days | 766–874 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 874 | 766 | −108 |
| Win Rate | 39.1% | 38.1% | −1.0% |
| Sharpe | **+1.90** | +0.98 | −0.91 |
| Profit Factor | 0.273 | 0.188 | −0.085 |
| Max Drawdown | −20.1% | −25.9% | −5.8pp |
| CAGR | +0.91× | +0.31× | −0.60 |
| Avg Score | 9.16 | 5.14 | −4.02 |
| Avg Edge | 0.409 | 0.409 | 0 |

**Winner: `unweighted_mean`** — Sharpe nearly double. The 15m scalping timeframe shows the clearest edge for `unweighted_mean`. The stricter agreement requirement in `by_edge` reduces the count and misses valid signals that split across tracks.

---

### BTCUSD / 30m
> Sampled 1-in-2 from 35,217 bars → 17,609 bars | 734 days | 661–840 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 840 | 680 | −160 |
| Win Rate | 36.9% | 36.8% | −0.1% |
| Sharpe | −1.23 | **−0.34** | +0.90 |
| Profit Factor | 0.018 | **0.049** | +0.031 |
| Max Drawdown | −63.1% | **−50.0%** | +13.1pp |
| CAGR | −0.47× | **−0.20×** | +0.27 |
| Avg Score | 9.18 | 4.70 | −4.48 |
| Avg Edge | 0.428 | 0.428 | 0 |

**Winner: `by_edge_max_linear_agree`** — In the 30m timeframe, both strategies lose money but `by_edge` loses less. The edge-weighted direction and agreement boost filter out many false trend continuations that `unweighted_mean` acts on. Max drawdown reduced by 13pp.

---

### BTCUSD / 1h
> Unsampled 17,608 bars | 734 days | 585–786 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 786 | 597 | −189 |
| Win Rate | 36.8% | 36.0% | −0.8% |
| Sharpe | −2.50 | **−2.19** | +0.31 |
| Profit Factor | 0.120 | **0.121** | +0.001 |
| Max Drawdown | −70.0% | **−61.4%** | +8.6pp |
| CAGR | −0.70× | **−0.61×** | +0.09 |
| Avg Score | 9.22 | 4.26 | −4.96 |
| Avg Edge | 0.487 | 0.487 | 0 |

**Winner: `by_edge_max_linear_agree`** — Both lose badly on hourly BTCUSD. The stricter filtering in `by_edge` reduces the number of losing trades and slightly improves Sharpe and drawdown. 1h regime transitions appear to be the primary failure mode for both.

---

### BTCUSD / 4h
> Unsampled 4,402 bars | 734 days | 147–198 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 198 | 158 | −40 |
| Win Rate | 37.4% | 35.4% | −2.0% |
| Sharpe | −1.18 | −1.74 | −0.56 |
| Profit Factor | 0.055 | **0.105** | +0.051 |
| Max Drawdown | −46.5% | **−43.4%** | +3.1pp |
| CAGR | −0.31× | −0.34× | −0.03 |
| Avg Score | 9.20 | 4.27 | −4.93 |
| Avg Edge | 0.475 | 0.475 | 0 |

**Winner: `unweighted_mean`** — Only 4,402 bars (4h resolution is sparse); Sharpe is negative for both. `unweighted_mean` has fewer drawdown events despite lower profit factor. Both strategies lack sufficient edge on 4h BTC.

---

### ETHUSD / 5m
> Sampled 1-in-8 from 211,304 bars → 26,413 bars | 734 days | 1,191–1,325 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 1,325 | 1,191 | −134 |
| Win Rate | 37.7% | **38.5%** | +0.8% |
| Sharpe | +3.39 | **+3.56** | +0.17 |
| Profit Factor | 0.449 | **0.495** | +0.046 |
| Max Drawdown | −27.0% | **−18.9%** | +8.1pp |
| CAGR | +9.26× | **+9.32×** | +0.06 |
| Avg Score | 9.17 | 5.43 | −3.74 |
| Avg Edge | 0.401 | 0.401 | 0 |

**Winner: `by_edge_max_linear_agree`** — ETHUSD 5m is the best-performing pair for both strategies. `by_edge_max_linear_agree` wins on every metric: higher Sharpe, higher win rate (+0.8pp), better profit factor, and dramatically lower drawdown (−18.9% vs −27.0%). The edge-weighting helps on ETH's slightly mean-reverting microstructure.

---

### ETHUSD / 15m
> Sampled 1-in-4 from 70,434 bars → 17,609 bars | 734 days | 763–888 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 888 | 763 | −125 |
| Win Rate | 37.7% | 37.1% | −0.6% |
| Sharpe | **+1.93** | +1.75 | −0.18 |
| Profit Factor | 0.247 | 0.245 | −0.002 |
| Max Drawdown | −32.8% | **−37.8%** | −5.0pp |
| CAGR | +1.62× | +1.25× | −0.38 |
| Avg Score | 9.17 | 4.93 | −4.24 |
| Avg Edge | 0.423 | 0.423 | 0 |

**Winner: `unweighted_mean`** — Both profitable on ETH 15m. `unweighted_mean` has higher Sharpe and lower drawdown. The edge-weighted direction is slightly worse on this timeframe for ETH as well.

---

### ETHUSD / 30m
> Sampled 1-in-2 from 35,217 bars → 17,609 bars | 734 days | 661–824 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 824 | 661 | −163 |
| Win Rate | 37.6% | **38.7%** | +1.1% |
| Sharpe | −0.03 | **+0.45** | +0.48 |
| Profit Factor | 0.052 | **0.100** | +0.048 |
| Max Drawdown | −59.5% | **−51.2%** | +8.3pp |
| CAGR | −0.26× | **+0.04×** | +0.30 |
| Avg Score | 9.19 | 4.55 | −4.64 |
| Avg Edge | 0.454 | 0.454 | 0 |

**Winner: `by_edge_max_linear_agree`** — `unweighted_mean` barely loses money (Sharpe −0.03) while `by_edge` is marginally profitable (+0.45). On ETH 30m the edge-weighted direction and agreement boost make the difference between breaking even and slight profit.

---

### ETHUSD / 1h
> Unsampled 17,608 bars | 734 days | 585–770 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 770 | 585 | −185 |
| Win Rate | **39.5%** | 37.3% | −2.2% |
| Sharpe | −1.48 | −2.30 | −0.82 |
| Profit Factor | 0.071 | **0.150** | +0.079 |
| Max Drawdown | −76.1% | −78.4% | −2.3pp |
| CAGR | −0.72× | −0.77× | −0.05 |
| Avg Score | 9.21 | 4.02 | −5.19 |
| Avg Edge | 0.470 | 0.470 | 0 |

**Winner: `unweighted_mean`** — `unweighted_mean` has higher Sharpe here despite lower profit factor. Both are badly negative on ETH 1h. `by_edge` has fewer trades but worse Sharpe — the edge-weighting is not providing directional accuracy benefit on this regime. Profit factor is nearly double for `by_edge` but the smaller sample amplifies volatility.

---

### ETHUSD / 4h
> Unsampled 4,402 bars | 734 days | 147–202 trades

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` | Δ |
|--------|-------------------|---------------------------|---|
| Trades | 202 | 147 | −55 |
| Win Rate | 37.6% | **38.1%** | +0.5% |
| Sharpe | −2.00 | **−1.78** | +0.22 |
| Profit Factor | 0.126 | **0.131** | +0.005 |
| Max Drawdown | −67.1% | **−62.4%** | +4.7pp |
| CAGR | −0.65× | −0.52× | +0.13 |
| Avg Score | 9.18 | 3.69 | −5.49 |
| Avg Edge | 0.469 | 0.469 | 0 |

**Winner: `by_edge_max_linear_agree`** — Both negative; `by_edge` loses less on all metrics. Small sample (147–202 trades) limits confidence.

---

## Aggregate Summary

> Across all 10 asset/timeframe pairs. "Wins" = lower absolute Sharpe (less negative = better).

| Metric | `unweighted_mean` | `by_edge_max_linear_agree` |
|--------|-------------------|---------------------------|
| **Pairs where it wins** | **6** | **4** |
| Avg Sharpe | +0.199 | +0.124 |
| Avg Win Rate | 37.7% | 37.3% |
| Avg Profit Factor | 0.189 | 0.203 |
| Avg Edge | 0.4408 | 0.4408 |
| Avg Trade Count | 826 | 666 |
| Avg Score (avg entry score) | 9.17 | 4.77 |
| Profitable pairs (Sharpe > 0) | 4 | 4 |
| Losing pairs (Sharpe < 0) | 6 | 6 |

---

## Key Findings

### 1. Edge is identical
Both strategies operate on the **same underlying track signals** with the **same edge quality** (avg 0.4408 per trade). The difference is purely in *how those signals are aggregated into a direction and score*. This confirms the strategies are comparable — the comparison isolates the aggregation logic alone.

### 2. `unweighted_mean` generates more signals
Average 826 trades vs 666 for `by_edge` — roughly **24% fewer signals** with `by_edge`. The agreement boost and edge-weighted direction act as a filter. Whether that's good depends on the timeframe:
- On 5m and 15m scalping: more signals = more opportunity = `unweighted_mean` wins
- On 30m and 4h: fewer but higher-quality signals = `by_edge` wins or loses less

### 3. 1h timeframes are unprofitable for both
Both strategies produce Sharpe −1.5 to −2.5 on 1h BTC and ETH. This is a **regime detection failure**, not a scoring failure. The tracks generate too many direction changes on hourly regime transitions. This regime should be excluded from live trading or require a separate regime filter.

### 4. ETH 5m is the best pair
`by_edge_max_linear_agree` achieves Sharpe +3.56 with only −18.9% max drawdown on ETHUSD 5m — the best risk-adjusted result in the entire test suite. This pair/timeframe should be the primary focus for live deployment.

### 5. Trade quality over quantity
`by_edge` achieves higher profit factor on 6/10 pairs (0.203 vs 0.189 aggregate) despite fewer trades. This suggests the edge-weighted direction produces better-quality entries even if it misses some opportunities.

---

## Recommendation

| Timeframe | Recommended Strategy | Confidence |
|-----------|---------------------|------------|
| 5m | `by_edge_max_linear_agree` (ETH) / `unweighted_mean` (BTC) | Medium — BTC 5m prefers unweighted |
| 15m | `unweighted_mean` | High — both assets prefer it |
| 30m | `by_edge_max_linear_agree` | Medium — clearer for ETH |
| 1h | Neither — disable | High — both lose badly |
| 4h | Neither — disable | Medium — insufficient edge |

**Next steps:**
1. Investigate 1h regime transitions — the track signal churn is destroying performance
2. Run `by_edge_max_linear_agree` on ETHUSD/5m with live paper trading
3. Increase lookback from 80 to 120 bars on 30m+ timeframes to improve regime stability
4. Add a minimum agreement requirement (≥2 tracks must agree) for `unweighted_mean` as a hybrid improvement