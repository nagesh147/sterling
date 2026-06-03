# Sterling Trading Report — Baseline (Existing Setup)

**Report 1 of 3** · _Canonical_ · Date: 2026-06-03 · Branch: `main` @ `7a6b2ab`
Companion reports: [Report 2 — With Kronos](./STERLING_TRADING_REPORT_KRONOS.md) · [Report 3 — Before/After](./STERLING_TRADING_REPORT_BEFORE_AFTER.md)

> This report supersedes and consolidates `REAL_DATA_PERFORMANCE.md`, `DERIVATIVES_EDGE_STUDY.md`, `BACKTEST_EDGE_REPORT.md`, `SCALPING_PERFORMANCE_REPORT.md`, and `performance_report.md`. Those files are retained for provenance only and carry a deprecation banner pointing here.

---

## 0. Data Provenance — read this first

This is the single most important section for a reviewer. Numbers in this report come from **two different evidentiary tiers**, and they are never mixed without a label.

| Instrument | P&L basis | Trust level | Source |
|---|---|---|---|
| **Futures** (Delta India perp/dated) | **REAL** bar-by-bar replay on actual 1-minute OHLCV | High — $ and % are real | `vector_store_1m_{BTC,ETH,SOL}USD.parquet`, ~Dec 2023 → May 2026 (3.56M bars) |
| **Spot / Index** | **REAL** — same replay at 1× leverage, **no funding** | High for win%/PF; $ = the futures replay de-levered | Same parquet; spot = the underlying the futures settle against |
| **Options** (Delta India calls/puts) | **MODELED** — constant-IV Black–Scholes, calibrated to **one** live surface snapshot | **win% and PF only.** Dollar/return figures are discarded | No historical IV chain exists yet |

**Three hard rules this report obeys:**

1. **The platform does not trade spot.** It routes **futures** and **options** on Delta India. "Spot/Index" here means the *underlying reference price* and a *spot-equivalent* view: the same signal at 1× with no funding. It is included because traders reason in underlying terms and it isolates pure directional edge from leverage/funding/convexity.
2. **All three instrument classes fire on the SAME entry signals.** A given config's **win rate is therefore identical** across spot, futures, and options. What changes between instruments is only the **P&L transform**:
   - Spot/Index → linear, 1×, no funding
   - Futures → linear, leveraged, minus funding + fees
   - Options → **convex** (long premium), minus theta
3. **Options dollar figures are not reported.** Under fractional compounding, short-DTE modeled options explode to nonsense (the prior study produced "+5,219,805,847,186%" and "$26T"). Only **win% and PF** survive scrutiny, and even those are optimistic (no theta-realistic IV path). This is a stated limitation, not a result.

> **One-line baseline verdict:** With the existing setup and **no AI gate**, *most* configurations lose. Real edge is narrow and concentrated at the **4-hour timeframe**; sub-hour timeframes die to fees and theta. Win rates run **28–43%** — these are trend/tail strategies (you lose more often than you win; profit comes from a few large winners), and they carry **27–47% drawdowns**.

---

## 1. What the system is

Sterling is a single-engine directional trading system ("Sterling Engine") with a derivatives routing layer. It generates directional signals on crypto underlyings and expresses them as **futures** or **options** on Delta India (paper by default).

```
Underlying OHLCV  ──►  Signal Engine (5 strategies)  ──►  Risk / Sizing  ──►  Derivatives Selector  ──►  Order Router
   (BTC/ETH/SOL)        × 3 profiles × 6 timeframes        (ATR + Kelly)       (futures | options)        (paper/shadow/live)
```

The same signal can be routed to a future (linear exposure) or an option (convex exposure); the **Derivatives Selector** chooses based on per-strategy bias, Greeks budget, IV-rank, and liquidity gates.

---

## 2. The configuration surface (everything a user can set in the UI)

Configs are split into **metric-moving** (change the trade set or its P&L → back-tested below) and **operational/cosmetic** (cataloged, not back-tested).

### 2.1 Metric-moving configs — the full matrix

| Dimension | UI control | Allowed values | Default | Effect on metrics |
|---|---|---|---|---|
| **Symbol** | Instrument Selector | BTCUSD, ETHUSD, SOLUSD | BTC | Different edge per asset; BTC cleanest at 4h |
| **Timeframe** | Backtest / Scalping panel | 1m, 5m, 15m, 30m, 1h, **4h** | 30m exec / 4h macro | **Dominant driver.** 4h is the only durable edge; ≤30m is fee-death |
| **Strategy** | Strategy toggles | ma_crossover, breakout, smc, price_action, mean_reversion | all on | Defines entries (see §3.1) |
| **Profile (ATR bracket)** | Profile selector | Scalping (SL 1.0× / TP 2.0× ATR), Intraday (2.0× / 3.5×), Aggressive (1.5× / 4.5×) | Intraday (validated) | Sets stop/target → win-rate vs R:R trade-off |
| **Instrument bias** | Derivatives settings | auto / futures / options | auto | Linear vs convex P&L transform |
| **Capital** | Risk config | float | **$100,000** | Scales $ P&L (not win%/PF) |
| **Max position %** | Risk config | 0–1 | **0.05** (5%) | Caps per-trade exposure |
| **Max contracts** | Risk config | int | **10** | Hard lot cap |
| **Partial TP R1 / R2** | Risk config | R-multiples | **1.5R / 2.0R** | Scale-out points → realized-PnL shape |
| **Financial stop %** | Risk config | 0–1 | **0.50** (50% of premium/margin) | Hard money stop |
| **Time stop (DTE)** | Risk config | days | **3** | Forces exit before expiry decay |
| **Kelly win-rate prior** | Risk config | 0–1 | **0.52** (used only when `win_rate_known`) | Sizing aggressiveness |
| **Daily-loss breaker** | Risk panel | soft-warn $, hard-halt $ | operator-set | Halts new entries when breached |
| **Tiered TP** | Scalping config | tp1 R-mult, tp1 size %, move-to-BE | 1.5R / 30% / on | Scale-out + breakeven pull |
| **Re-entry cooldown** | Scalping config | minutes | **0 (off)** | Any cooldown removed net-positive trades in replay; kept for manual opt-in |
| **Derivatives: target delta** | Derivatives settings | 0–1 | edge 0.55 / scalp 0.50 / breakout 0.40 | Strike selection → convexity |
| **Derivatives: DTE band** | Derivatives settings | min/pref/max days | edge 7/14/30 · scalp 0/1/3 | Theta exposure |
| **Derivatives: leverage cap** | Derivatives settings | × | edge 10 · scalp 25 · breakout 15 | Max notional/margin |
| **Derivatives: max premium %** | Derivatives settings | % of account | edge 2.0% · scalp 1.5% | Caps option cost |
| **Derivatives: max spread %** | Derivatives settings | % | edge 4% · scalp 5% · breakout 10% | Liquidity quality gate (the real gate on Delta India) |
| **Derivatives: IVR cap** | Derivatives settings | percentile | edge 50 · scalp 85 | Blocks buying rich vol |

> **Scoring weights** (Regime 20 / Signal 20 / Execution 15 / DTE 10 / Health 20 / Risk-Reward 15 = 100 pts) gate *which* candidate is taken when several fire on one bar. They reshape the trade set but are not independently back-tested here; defaults shown.

### 2.2 Portfolio-level gates (metric-moving, always-on safety layer)

| Gate | Default | What it does |
|---|---|---|
| **Drawdown circuit breaker** (`app.state.dd_circuit_breaker`) | on | Halts trading when portfolio drawdown breaches threshold; evaluated **before** any strategy logic |
| **Correlation penalty** (`correlation_tracker`) | on | Fed 1H closes every evaluate(); penalizes stacking correlated exposure |
| **Greeks budget** (`greeks_budget`) | on | Caps net delta/gamma/vega/theta across the options book |
| **Execution circuit breaker** (`app.state.circuit_breaker`) | on | Execution-level kill-switch (distinct from drawdown breaker) |

### 2.3 Operational / cosmetic configs (cataloged, not back-tested)

These change *how you operate or view*, not the trade economics: **Mode** (paper / shadow / live, default paper), **auto-execute** futures/options toggles (default OFF until 7-day audit), **data source / exchange adapter** (delta_india default; deribit/okx/binance), **Telegram alerts**, **font/theme**, panel layout, watchlist, session export, snapshot/eval-history browsing, alert thresholds, and the analytics panels (walk-forward, sensitivity, correlation heatmap) which *report* metrics rather than change them.

---

## 3. Strategy & profile definitions (exact, matches `strategies.py`)

### 3.1 Entry logic (long-only in the validated path)

| Strategy | Entry trigger |
|---|---|
| **MA Crossover** | EMA(9) crosses above EMA(21) — fresh bull cross only |
| **Breakout** | Close crosses above 20-bar Donchian high (retest-entry variant on the live scanner) |
| **SMC** | Bullish fair-value gap (low of bar > high of bar−2) + bullish close |
| **Price Action** | Bullish engulfing candle |
| **Mean Reversion** | Z-score < −2.0 (20-bar) snap-back (rapid re-entry is its edge) |

### 3.2 ATR brackets by profile

| Profile | Stop loss | Take profit | R:R |
|---|---|---|---|
| Scalping | 1.0× ATR | 2.0× ATR | 1:2 |
| **Intraday** (validated default) | 2.0× ATR | 3.5× ATR | 1:1.75 |
| Aggressive | 1.5× ATR | 4.5× ATR | 1:3 |

**Cost model:** 0.10% round-trip fees on futures; first-touch SL/TP; ATR-based position sizing.

---

## 4. SPOT / INDEX — directional edge at 1× (REAL underlying, no funding)

Spot/Index isolates the *pure directional signal*: the same entries as futures, sized 1× on the underlying, **no leverage, no funding**. Win% and PF are identical to futures by construction; the $ column is the futures replay de-levered to 1×.

### 4.1 Full grid shape — median across the 270-config matrix (3 symbols × 6 TF × 5 strategies × 3 profiles)

| Timeframe | Median win% | Median PF | Median net return (1×) | Read |
|---|---|---|---|---|
| 1m | 27.8% | 0.38 | −100.0% | Total fee/noise death |
| 5m | 32.9% | 0.68 | −99.9% | Dead |
| 15m | 33.1% | 0.84 | −86.8% | Loses |
| 30m | 32.9% | 0.87 | −64.5% | Loses |
| 1h | 32.8% | 0.91 | −53.2% | Loses |
| **4h** | **33.6%** | **0.92** | **−26.4%** | Least-bad; edge lives here |

> Even at 4h the **median** config loses. Edge is a minority of configs, not the average.

### 4.2 The 10 configs that are net-profitable in-sample (the "validated" set)

| # | Symbol | TF | Strategy | Profile | Trades | Win% | PF | Sharpe | Net (1×) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | BTCUSD | 4h | ma_crossover | Intraday | 166 | 43.4% | **1.29** | **1.83** | +95.3% |
| 2 | BTCUSD | 4h | breakout | Intraday | 100 | 42.0% | 1.20 | 1.31 | +27.7% |
| 3 | ETHUSD | 4h | smc | Scalping | 220 | 39.5% | 1.15 | 0.97 | +38.6% |
| 4 | SOLUSD | 4h | smc | Aggressive | 123 | 28.5% | 1.15 | 0.94 | +24.4% |
| 5 | BTCUSD | 4h | smc | Intraday | 149 | 40.9% | 1.14 | 0.90 | +26.3% |
| 6 | BTCUSD | 4h | ma_crossover | Aggressive | 156 | 28.2% | 1.14 | 0.83 | +23.8% |
| 7 | BTCUSD | 1h | price_action | Intraday | 434 | 41.7% | 1.11 | 0.69 | +39.2% |
| 8 | BTCUSD | 4h | smc | Aggressive | 135 | 30.4% | 1.07 | 0.48 | +5.6% |
| 9 | SOLUSD | 4h | smc | Scalping | 196 | 38.3% | 1.06 | 0.43 | +6.4% |
| 10 | BTCUSD | 1h | price_action | Aggressive | 431 | 29.0% | 1.06 | 0.39 | +14.4% |

**Only 10 of 270 configs (3.7%) are profitable, and 8 of 10 are 4h.** This is the in-sample *selection* metric — see §4.4 for the out-of-sample reality.

### 4.3 Where edge clusters (4h slice)

| Cut | Median win% | Median PF | Median net |
|---|---|---|---|
| BTC @ 4h | 35.9% | **1.00** | −5.5% |
| ETH @ 4h | 32.8% | 0.91 | −36.6% |
| SOL @ 4h | 33.1% | 0.88 | −30.1% |
| Intraday profile @ 4h | 37.8% | 0.97 | −28.3% |
| Scalping profile @ 4h | 33.7% | 0.95 | −21.1% |
| Aggressive profile @ 4h | 24.7% | 0.87 | −30.4% |

→ **BTC + 4h + Intraday** is the center of gravity; Aggressive widens both tails.

### 4.4 Out-of-sample robustness study (the honest cut)

A separate CPCV + Monte-Carlo study (N=6 groups, K=2 test, embargo 2×hold) on a larger grid kept only **8 survivors** (net>0, OOS Sharpe>0, p(loss)≤35%). These carry an explicit **probability of ending underwater**:

| # | Config | Trades | Win% | PF | Net | **p(loss)** | Max DD |
|---|---|---|---|---|---|---|---|
| 1 | **ma_crossover 4h BTC** | 166 | 43.4% | **1.29** | **+95.3%** | **11%** | −27.2% |
| 2 | breakout 4h BTC | 100 | 42.0% | 1.20 | +27.7% | 28% | −28.1% |
| 3 | smc 4h ETH | 220 | 39.6% | 1.15 | +38.6% | 25% | −33.1% |
| 4 | smc 2h ETH (Aggr) | 240 | 30.0% | 1.15 | +46.4% | 27% | −45.0% |
| 5 | smc 2h ETH (Intr) | 237 | 40.9% | 1.12 | +37.5% | 32% | −46.9% |
| 6 | smc 4h BTC | 149 | 40.9% | 1.14 | +26.3% | 34% | −44.4% |
| 7 | price_action 1h BTC | 434 | 41.7% | 1.11 | +39.2% | 24% | −38.5% |
| 8 | ma_crossover 2h BTC (Aggr) | 322 | 29.2% | 1.10 | +27.6% | 34% | −39.0% |

> **Only `ma_crossover 4h BTC` is a clean edge** (high net, OOS-retentive, 11% p-loss). The rest are real but carry **24–34% probability of finishing underwater** and **33–47% max drawdown**. Size for the p-loss, not the headline return.

---

## 5. FUTURES — REAL, the tradable instrument

Futures = the §4 signals with **leverage + funding + 0.10% round-trip fees**. The win%/PF are identical to §4 (same entries); the differences are:

- **Leverage** scales both the return *and* the drawdown linearly. A −27% spot drawdown at 3× is −81% of margin — i.e. the **leverage cap (default 10×, max_position_pct 5%) is the real risk control**, not the signal.
- **Funding** is a continuous drag on held perp exposure (not in the spot 1× view). At 4h hold horizons it is modest but non-zero.
- **`max_contracts=10` + `max_position_pct=5%`** clamp notional regardless of signal conviction.

**Tradable conclusion for futures:** the validated, OOS-retentive edge is **`ma_crossover 4h BTC`** (PF 1.29, +95.3%, p-loss 11%, −27% DD at 1×). Secondary candidates (`breakout 4h BTC`, `smc 4h ETH`) are real but carry 25–34% p-loss. Everything ≤1h and the full-grid median **lose** after fees. This is a **few-config, 4h-only** edge — not a portfolio of always-on strategies.

### 5.1 Fee-death gradient (why ≤30m is excluded)

| TF | Futures median PF | Verdict |
|---|---|---|
| 15m | 0.87 | Loses to fees |
| 30m | 0.92 | Loses |
| 1h | 0.93 | Loses |
| **4h** | **0.94** | Only durable tier |

(Full-grid medians from the 12,960-config robustness grid; consistent with the 270-grid in §4.1.)

---

## 6. OPTIONS — MODELED overlay (win% / PF only)

> ⚠️ **MODELED.** Constant-IV BSM calibrated to a *single* live Delta India surface snapshot. **No historical IV chain exists**, so vol-timing cannot be honestly back-tested. **Win% ≈ the futures win% (same signals); only PF carries information; all $/return figures are discarded as artifacts.**

Options take the same entry as the underlying signal, repriced as a long ATM (or near-ATM) option. Because the payoff is **convex**, PF differs from futures even though win% is the same — winners pay convex multiples, losers are capped at premium:

| TF | Options win% | Options PF | Futures PF (same config) | Read |
|---|---|---|---|---|
| 15m | 33.1% | 0.92 | 0.87 | Both lose; theta + fees |
| 30m | 32.9% | 1.01 | 0.92 | ~Breakeven |
| 1h | 32.8% | 1.08 | 0.93 | Convexity lifts a losing signal toward flat |
| **4h** | **33.1%** | **1.47** | **0.94** | Convexity meaningfully amplifies |

**Headline config — `ma_crossover 4h BTC` (14-DTE, 1% spread, modeled):** options win% 43.4%, **PF ≈ 1.68–1.76** vs futures PF 1.29–1.33. Options *amplify the PF of a signal that already has edge* because winners pay convex multiples — **but this is modeled and optimistic.**

**Options verdict:** options are a **convexity overlay, not a standalone edge.** They raise PF *where the underlying signal already wins* (4h) and bleed to losses on the median config via theta (7–14 DTE median PF ≈ 0.91–0.99). No standalone options edge is demonstrated and none can be validated until the forward-IV recorder accrues a genuine IV series. On Delta India specifically, options are thin (near-ATM OI in single digits), so the **spread cap is the binding liquidity gate**.

---

## 7. Baseline scorecard (existing setup, no Kronos)

| Question | Answer (real data) |
|---|---|
| Does the average config make money? | **No.** Median PF < 1.0 at every timeframe. |
| Where is the edge? | **4h, BTC-led, a handful of configs.** Chiefly `ma_crossover 4h BTC`. |
| Best validated config | ma_crossover 4h BTC — PF **1.29**, win **43.4%**, +95.3%, p-loss **11%**, DD −27.2% |
| Typical win rate | **28–43%** (trend/tail; lose more often than win) |
| Typical drawdown | **27–47%** on the survivors |
| Are options a separate edge? | **No** — convexity overlay only, and modeled |
| Biggest risk in the baseline | **Firing every signal.** Validated combos still bleed out-of-sample because they trade in bad regimes too (see Report 3 "before"). |

**This is the problem Kronos is proposed to solve** → see [Report 2](./STERLING_TRADING_REPORT_KRONOS.md).

---

### Appendix — reproducibility

- Futures/spot grid: `backtest_edge_results.csv` (270 rows) + `backend/comprehensive_backtest.py`.
- OOS robustness: CPCV (N=6, K=2, embargo 2×hold) + Monte-Carlo p-loss.
- Defaults: `backend/app/schemas/risk.py`, `backend/app/core/config.py`, `backend/app/engines/derivatives/profiles.py`, `backend/app/engines/scalping/config.py`.
- Data: `vector_store_1m_{BTC,ETH,SOL}USD.parquet`, ~Dec 2023 → May 2026, 3.56M bars.
