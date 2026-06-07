# Mean-Reversion Sleeve — Validation & Build Plan

**Status: VALIDATED LEAD, NOT DEPLOYABLE (2026-06-07).**
Higher-timeframe (2h/4h) Bollinger + RSI mean-reversion — buy when price reclaims
the lower Bollinger band while RSI is oversold — is the **one real edge candidate**
the audit surfaced. It shows genuine out-of-sample behaviour but **cannot be
proven** with the data in this repo. This document records the evidence, why it is
unprovable today, and the only honest path to a deployable sleeve.

Code:
- Research validator: [`backend/study/mean_reversion_wf.py`](../backend/study/mean_reversion_wf.py)
- Disabled scaffold: [`backend/app/engines/edge/sleeves/mean_reversion.py`](../backend/app/engines/edge/sleeves/mean_reversion.py)
- Enforcement: `EdgeGate(min_dsr=0.5, require_beats_hold=True)` in `app/engines/edge/registry.py`

## 1. Evidence (anchored walk-forward, params selected on past data only)

$500, BTC 4h, OOS span 2025-03 → 2026-05 (BTC fell −12% over it):

| TF | WF $500 | Sharpe | n trades | DSR | vs BTC HODL |
|----|---------|--------|----------|-----|-------------|
| 1h | $497 (−0.6%) | 0.11 | 59 | 0.003 | −12.7% |
| 2h | $579 (+15.8%) | 4.14 | 19 | 0.040 | −12.3% |
| 4h | $554 (+10.7%) | 1.83 | 23 | 0.012 | −12.3% |

Cross-symbol sanity (final BTC-selected params applied to OOS spans never used in
selection): ETH +19.6%, SOL +20.1% (while SOL fell −38%). Positive and
hold-beating on both — hard to fake by overfitting BTC.

## 2. Why it is unprovable here — the sample-size trap

- The edge lives at **2h/4h**, where it fires only ~1.5 trades/month → n ≤ 23.
- At **1h**, where you finally get a usable sample (n=59), the **edge vanishes**
  (Sharpe 0.11, flat). The extra trades are noise + fees, not edge.
- So you can have *"edge present"* **or** *"enough trades to prove it"*, never both,
  from 3 symbols × 2.4 years.
- Deflated Sharpe stays at **0.01–0.04**, far below the 0.5 deploy bar. The
  good-looking Sharpes (1.83, 4.14, even 8.88 cross-symbol) are small-sample
  noise inflation.

### Sample-size math (the target)

For DSR ≥ 0.5 at the 243-variant grid, the observed Sharpe must reach the
expected-max-under-null hurdle in standard-error units:

```
expected_max(N=243) ≈ 2.82           # Bailey & López de Prado
t-stat needed       = 2.82           # for DSR = 0.5 (z = 0)
t-stat              = SR_per_trade · sqrt(n − 1)
SR_per_trade (4h)   ≈ 1.83 / sqrt(19/yr) ≈ 0.42
⇒ n − 1 ≥ (2.82 / 0.42)² ≈ 45   ⇒  n ≈ 46 OOS trades
```

At ~19 trades/yr/symbol on 4h, **one symbol can't get there** in a useful OOS
window. A basket can: 15 symbols × ~19/yr × ~1.5 yr OOS ≈ **400+ trades** — far
past the ~46 needed — **without enlarging the param grid** (so the deflation
hurdle stays fixed at 2.82 while n grows). That is the whole idea.

## 3. The plan — get to a provable n

1. **Data.** Ingest a **15–30 liquid crypto basket** at 1m (the parquet format in
   `backend/vector_store_1m_*.parquet`), enough history for ≥ 1.5 yr of OOS after
   the train anchor. Source = the same OHLCV pipeline that produced BTC/ETH/SOL.
2. **Pooled walk-forward.** Extend `study/mean_reversion_wf.py` to select params on
   the **pooled** pre-window trades across the basket, then trade each symbol's
   next window. Stitch all symbols' OOS trades into one stream.
3. **Deflate honestly.** `num_trials` = the param-grid size (243), **not** inflated
   by the symbol count — pooling grows n, not the number of hypotheses.
4. **Acceptance (all required):**
   - pooled OOS **DSR ≥ 0.5**
   - **beats buy-and-hold** (return AND drawdown) on the basket
   - edge **stable across folds** (no single fold/symbol carrying it)
   - holds on a **held-out symbol set** never used in selection
5. **Promotion (only if §4 passes).** Set validated params in
   `sleeves/mean_reversion.py`, flip `QUALIFIED = True`, register in
   `edge.strategies.SIGNAL_FNS`, regenerate `robustness_scan_results.csv`. The
   live `EdgeGate` (DSR ≥ 0.5) is the final bouncer.

## 4. Guardrails (do not repeat the audit's sins)

- **No parameter tuning to chase DSR.** The grid is fixed; more tuning = more
  trials = higher hurdle. Provability comes from **more independent data**, not
  more knobs.
- **No dropping timeframe for trade count** — it kills this edge (see §2).
- **Scaffold stays disabled** until §4 acceptance is met on data not used to pick
  params. `is_qualified(dsr)` is the single check; `QUALIFIED` stays `False`.
