# Derivatives Edge Study (Phase 1)

_Generated 2026-06-02 · real data: `backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet` (1m OHLCV, ~2024→2026) · live surface: Delta India `/v2/tickers` snapshot 2026-06-02_

## TL;DR

- **Futures edge is real and OOS-survivable** on 2h–4h; sub-hour dies to fees. 8 of 225 robustness-gated configs survive (net>0, OOS Sharpe>0, MC p-loss≤35%).
- **The best, by a wide margin, is `ma_crossover 4h BTC` (+95.3%, OOS retention ~0.91, p-loss 11%).** The rest are real but markedly riskier (p-loss 24–34%, max-DD 33–47%).
- **The routing gate denies the options expression of a proven signal across almost the entire IVR range** — options are only routed in a razor-thin IVR≈50 band; the **IVR cap is the binding over-filter** (the 1.3% live spread never trips the spread veto).
- **The vol-risk-premium is thin right now** (BTC VRP 0.91–1.18, ETH 0.90–1.21), so a blind vol-selling engine is not well paid; the durable options edge is **regime-conditional** and needs the forward IV history (now accruing) to validate.

## Methodology + honesty bounds

- **Futures = real.** Bar-by-bar first-touch ATR SL/TP on real OHLCV, 0.10% round-trip fee, 200-bar time-stop (`robustness_scan.py`). Robustness = CPCV out-of-sample Sharpe (`analytics/cpcv`) + Monte-Carlo p-loss over 3000 bootstraps (`analytics/monte_carlo`). Gate enforced on **OOS**, not in-sample.
- **Options = modeled.** No historical options chain exists (Delta India serves only a live snapshot; DVOL stubbed; local IV tables were empty). Options economics are therefore Black-Scholes priced off realized vol, **calibrated to the 2026-06-02 live surface** (`deriv_fut_opt_metrics.py` covers the per-config futures-vs-options sweep). Treat all options numbers as an optimistic upper bound until forward IV accrues.
- **Vol-timing is not yet validatable.** IV-percentile / IV-rank require a historical IV series we don't have. The forward recorder (`delta_iv_recorder`, already wired) is now accruing it; vol-timing rules ship `provisional`.

## 1. Real futures edge — OOS survivors (225 configs → 8)

| # | config | trades | win% | PF | Sharpe | OOS-keep | p-loss | net | max-DD |
|---|--------|-------:|-----:|---:|-------:|---------:|-------:|----:|-------:|
| 1 | **ma_crossover 4h BTC (Intraday)** | 166 | 43.4 | 1.29 | 1.83 | **0.91** | **11%** | **+95.3%** | −27.2% |
| 2 | breakout 4h BTC (Intraday) | 100 | 42.0 | 1.20 | 1.31 | 0.86 | 28% | +27.7% | −28.1% |
| 3 | smc 4h ETH (Scalping) | 220 | 39.6 | 1.15 | 0.97 | 1.07 | 25% | +38.6% | −33.1% |
| 4 | smc 2h ETH (Aggressive) | 240 | 30.0 | 1.15 | 0.91 | 1.19 | 27% | +46.4% | −45.0% |
| 5 | smc 2h ETH (Intraday) | 237 | 40.9 | 1.12 | 0.82 | 1.19 | 32% | +37.5% | −46.9% |
| 6 | smc 4h BTC (Intraday) | 149 | 40.9 | 1.14 | 0.90 | 0.88 | 34% | +26.3% | −44.4% |
| 7 | price_action 1h BTC (Intraday) | 434 | 41.7 | 1.11 | 0.69 | 0.94 | 24% | +39.2% | −38.5% |
| 8 | ma_crossover 2h BTC (Aggressive) | 322 | 29.2 | 1.10 | 0.62 | 0.98 | 34% | +27.6% | −39.0% |

_OOS-keep = CPCV mean_test_sharpe ÷ mean_train_sharpe (≈1 means OOS retains in-sample performance — the honest robustness signal; the raw OOS Sharpe column in the CSV is per-trade √252-scaled and not an annual figure). Full matrix: `backend/robustness_scan_results.csv`._

**Reads:** (a) `ma_crossover 4h BTC` is the standout — high net, OOS-retentive, lowest p-loss. (b) **2h ETH SMC is a genuine new survivor** the prior 4h-only view missed. (c) Everything else carries 24–34% probability of ending underwater and 33–47% max-DD — real edge, but size accordingly. (d) Win rates are 30–43%: these are **right-tail/trend strategies** (PF>1 from a few big winners), which is exactly where long options convexity *could* help — if not for the gate (§3) and thin VRP (§2).

## 2. Live options surface (real, 2026-06-02)

| | BTC ($71.4k) | ETH ($1,994) | SOL |
|---|---|---|---|
| Realized vol 30d | 31% | 41% | — |
| ATM IV (0→87 DTE) | 28%→37% | 37%→50% | — |
| **VRP = IV÷RV30** | **0.91→1.18** | **0.90→1.21** | — |
| Skew (25Δp−25Δc) | +3.9 pts | +2.7 pts | — |
| Liquidity (spread<5%) | 414/547, med **1.3%** | 176/250, med 1.5% | — |

- **SOL has no options on Delta India → futures-only.**
- VRP is **thin** (short-dated <1.0; only ~1.1–1.2 at 1–3 months). Rich VRP appears in high-IV regimes — which we cannot yet rank without history.
- Skew is modestly **put-bid** → a small, real put-credit-spread edge.
- Liquidity is good → spread is not the constraint; **IV regime is.**

## 3. Gate over-filter — quantified (`backend/GATE_OVERFILTER.md`)

Running the **actual `instrument_chooser`** over the gate-passing combos at the live 1.3% spread, sweeping IVR:

- A proven signal is routed to **options only in a razor-thin IVR≈50 band**; below ~45 the routing score favors futures, above 50 the **IVR cap hard-vetoes options → futures-only**.
- The **spread veto never binds** at 1.3%; the **IVR cap is the binding over-filter**.
- The **futures leg is not refused** (presized edge signals pass the SL/TP solver) — so a good signal is **instrument-restricted, not fully rejected**, but it loses the options expression precisely when IV is rich (the moment selling vol would pay) and is sent to futures when IV is cheap (the moment buying would be cheap). The routing logic is, in effect, upside-down for an options *seller* and unhelpful for an options *buyer*.

**This is the structural gap the native engine fills:** at rich IV, *sell* defined-risk vol instead of vetoing; at cheap IV, *buy* defined-risk premium instead of defaulting to futures.

## 4. Phase 2 seed (what the native strategy should do, per the evidence)

1. **Directional base = futures** on the survivor configs (`ma_crossover 4h BTC` first; `smc 2h/4h ETH`, `breakout 4h BTC` next), sized to the p-loss/max-DD profile. This is the only fully-validated edge.
2. **Options only when the regime justifies it** (native engine, `regime.py`): buy defined-risk premium when VRP<1.0 (cheap), sell defined-risk spreads/condors when VRP≥1.2 (rich). Today's thin VRP ⇒ mostly stand-aside / small debit structures.
3. **Harvest the put-side skew** via put credit spreads when skew is rich (small but real).
4. **Naked vol stays gated** behind opt-in + a rich-regime check (2d) — not justified by current VRP.
5. **Re-run this study** once ≥60 days of forward IV has accrued to replace the provisional vol-timing thresholds with validated ones, and to re-price the options leg against real (not modeled) IV.

## Caveats (read before trusting any options number)

- Options results are **modeled**, calibrated to a single live snapshot; real fills/IV-premium make them worse.
- High max-DDs (to −47%) on several survivors — these are aggressive-profile, trend-tail strategies.
- OOS Sharpe magnitudes are per-trade √252-scaled; use **OOS-keep + p-loss + max-DD** for robustness, not the raw Sharpe.
- The over-filter analysis is a code-derived sensitivity across IVR (real routing logic, real combos, live spread) — not a historical PnL of blocked trades (no historical IV to drive the gate through time).
