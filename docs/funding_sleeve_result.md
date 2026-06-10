# Funding-Carry Sleeve — Result (Honest Negative)

The Phase-1 orthogonal-sleeve spike: does a **funding-rate positioning-tilt
sleeve** add *independent* information past the correlation wall that capped the
conviction regime book at DSR 0.166? Pre-registered design + kill/fold bar:
`docs/superpowers/specs/2026-06-10-funding-sleeve-spike-design.md`. Code:
`backend/study/funding_pipeline.py`, `backend/study/funding_sleeve.py` (research
only — nothing wired live).

**Verdict: KILL. The funding sleeve loses out-of-sample across the entire grid
and drags the book down when combined. Funding adds no independent edge here.**

## Method

- **Data:** real Binance USDⓈ-M perp **funding history** (`fapi/v1/fundingRate`,
  8h cadence, 2,684 events/coin, 2023-12-29 → 2026-06-10) overlaid on the **same**
  BTC/ETH/SOL 4h OHLCV bars the conviction book uses (`data/ohlcv`). Same
  universe — no breadth confound.
- **Signal:** leak-free contrarian funding z-score (rich-positive funding =
  over-leveraged longs → short; deep-negative → long), entered through the
  **same** `simulate_idx` fill engine, with the **real funding cash-flow** accrued
  per held bar (a short collects positive funding).
- **Harness:** the exact `portfolio_equity_sized` + `deflated_sharpe_ratio` +
  in-sample-only selection used for the conviction book. OOS = held-out last 50%
  of calendar time (a crypto downturn).
- **Pre-registered grid (8 cells, frozen before running):** window ∈ {30, 90}
  funding events × thr ∈ {1.0, 2.0} × exit ∈ {bracket, hold-to-flip}. DSR deflated
  by the grid size; headline cell chosen on **in-sample Sharpe only**.

## Headline (real numbers)

| Book | IS-best | OOS ret | OOS Sharpe | n | DSR | note |
|---|---|--:|--:|--:|--:|---|
| **Conviction book** (baseline, this data) | adx20/rsi25-65 | **+75.8%** | **+1.57** | 242 | **0.327** (36) | the book alone |
| **Funding sleeve** (standalone) | w30/thr2/bracket | **−28.8%** | **−1.63** | 122 | 0.006 (8) | loses OOS |
| **Combined** (book ⊕ funding, cap 6) | — | +25.3% | **+0.56** | 387 | **0.065** (44) | funding *drags it down* |

Funding-sleeve **IS→OOS Spearman corr = −0.33**; sleeve-vs-book per-bar
**ρ = −0.10**.

## Why it's a real negative, not one unlucky cell

The whole pre-registered grid is **0/8 OOS-positive**:

| window | thr | exit | IS Sharpe | OOS ret | OOS Sharpe | n |
|--:|--:|---|--:|--:|--:|--:|
| 30 | 1.0 | bracket | −0.51 | −54.0% | −1.40 | 314 |
| 30 | 1.0 | flip | 0.30 | −54.0% | −0.90 | 837 |
| 30 | 2.0 | bracket | 1.05 | −28.8% | −1.63 | 122 |
| 30 | 2.0 | flip | 0.66 | −28.8% | −2.93 | 157 |
| 90 | 1.0 | bracket | −0.88 | −29.2% | −0.53 | 296 |
| 90 | 1.0 | flip | −0.05 | −47.9% | −0.77 | 758 |
| 90 | 2.0 | bracket | −0.55 | −15.7% | −0.89 | 101 |
| 90 | 2.0 | flip | −1.54 | −15.0% | −1.87 | 138 |

**Whole-grid OOS Sharpe: mean −1.37, best −0.53, positive 0/8.** Every cell loses
forward. The in-sample-best cell (w30/thr2/bracket, IS Sharpe +1.05) is among the
worst out-of-sample (−1.63) — the **negative IS→OOS correlation** is this
project's signature overfit pattern (the cut strategies had −0.65 to −0.73), and
it is the opposite of the conviction book's *positive* +0.38.

## The pre-registered bar (no goalpost-moving)

Written before the run: **KILL** if standalone OOS Sharpe ≤ 0 **or** IS→OOS corr
< 0. Both fired (−1.63 and −0.33). **FOLD IN** would have required combined DSR >
book DSR with Sharpe ≥ 1.15 and |ρ| < 0.5 — combined DSR *fell* (0.327 → 0.065).
Disposition: **KILL**, documented here.

## Honest read

Funding-as-contrarian-positioning is dominated by — and worse-timed than — the
momentum the regime book already captures. In a downtrend the regime gate is
*already* short; funding extremes tend to mark local capitulation/squeeze points
where a fresh contrarian short gets run over (price bounces precisely when funding
is most extreme). So the sleeve doesn't supply independent information; it supplies
worse-timed correlated risk. The low ρ (−0.10) doesn't rescue it because an
uncorrelated stream that simply loses money cannot lift a portfolio's DSR.

This joins the project's documented negatives — **breadth (24-coin), naive
leverage, cross-sectional factors, uniform trailing** — as another orthogonal idea
that was tested honestly and **did not clear the bar**. The correlation wall
holds: positioning data did not buy independent edge on this universe/window.

### One real side-finding (positive)

Recomputing the conviction book on **native Binance 4h** data (this experiment's
baseline) gives **DSR 0.327** — roughly double the legacy-data headline of 0.166,
and the highest the project has measured — consistent with the paper trader's note
that native 4h bars give cleaner first-touch fills. Still **< 0.5 (not
deflation-provable)** and still one macro regime, but the book is stronger on clean
data than its documented number, not weaker.

## Reproduce

```
cd backend
.venv/bin/python -m study.funding_pipeline --coins BTC ETH SOL   # one-off data pull
.venv/bin/python -m study.funding_sleeve                          # prints the verdict
```
