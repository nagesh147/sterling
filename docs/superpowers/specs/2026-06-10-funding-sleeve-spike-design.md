# Funding-Carry Sleeve Spike — Design

**Date:** 2026-06-10
**Branch:** `feat/dsr-deflation-gate`
**Status:** approved (design); spec under review
**Scope:** research-only. Nothing wired into `SterlingEngine` / `app.state`.

## Problem

The project's best book — the conviction regime book (adx=20, RSI<25/>65,
vol-target sizing, sleeve exits) — is a **real, validated, out-of-sample edge**
(+43.2% OOS, Sharpe 1.15, beats HODL by 62 pts at half the drawdown; paper-trades
+63–85% on real Binance data). But its **DSR = 0.166 ≪ 0.5 — not
deflation-provable**. The documented bottleneck is the **correlation wall**: 24
crypto coins are ~0.8-correlated, so stacking more *price-directional* books adds
trade count but not independent information. Breadth, naive leverage,
cross-sectional factors, and trailing stops were all tested and cut.

The only way past a correlation wall is a signal driven by a **different
information source** than price momentum/mean-reversion. This spike tests one such
source: **perpetual funding rate** (crowd positioning), as an orthogonal sleeve,
measured through the exact same harness the conviction book passed through.

## Why funding, and why not options VRP (the adversarial cut)

Options vol-risk-premium is the more glamorous "options" play but is **data-blocked
for honest validation today**. There is no real historical IV surface in the repo
— only a live snapshotter (`study/surface_snapshot.py`) and a forward recorder
that, per its own docstring (`study/forward_surface.py`), returns "few/no surfaces"
until it accrues. Validating a VRP sleeve through the DSR harness now would require
months of recorder accrual or sourcing external Deribit data (large lift; Binance/
Delta options history is thin). **VRP is parked with this written reason.**

Funding-rate carry, by contrast:
- has **real, free, multi-year data today** (Binance `fapi` funding-rate history,
  8h cadence);
- runs through the **exact** `study.sim.simulate_idx` + `study.robustness` (DSR) +
  anchored walk-forward harness, unchanged;
- is **genuinely orthogonal** — it measures crowd positioning (who is paying to
  hold the trade), not price action;
- is already a first-class *measured* quantity in the live engine
  (`funding_cost_gate.py`, `selector.py`, `leverage_engine.py`), so there is no
  fabrication risk.

## Approach chosen

**Positioning-tilt sleeve** (over two-leg carry-harvest and over "both"):

- Funding **z-score** as a *contrarian directional* signal — richly positive
  funding = over-leveraged longs → **short** bias; deeply negative funding →
  **long** bias.
- Entries go through the **same ATR bracket via `simulate_idx`** the conviction
  book uses (first-touch SL/TP, 0.10% round-trip fee), so the fill/cost machinery
  is identical and already trusted.
- The **real funding cash-flow** is accrued per bar held (a short collects funding
  when the rate is positive; a long pays it; inverse when negative). This is the
  one new, real cash-flow term.

Rejected: *carry-harvest* (short perp / long spot to collect funding delta-hedged)
needs two-leg spot+perp accounting → more new trusted code for the same question.
*Both* = multiple-comparisons fishing.

## Architecture & data flow

New, isolated under `backend/study/` (mirrors the existing OHLCV pipeline split of
impure fetch / pure transform / IO):

- **`study/funding_pipeline.py`** — paginating fetcher, same cursor pattern as
  `ohlcv_pipeline.fetch_history`.
  - Endpoint: `GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=<COIN>USDT&limit=1000&startTime=<ms>`.
  - Fields used: `fundingTime` (ms), `fundingRate` (str→float).
  - Output: `data/funding/<COIN>_funding.parquet` with columns `time` (unix s,
    int), `funding_rate` (float). One coin per file.
  - Pure transform `funding_to_frame(raw)`; impure `fetch_funding_history`;
    IO `write_funding_frame`. `main()` CLI: `python -m study.funding_pipeline
    --coins BTC ETH SOL --start 2023-12-29`.

- **`study/funding_sleeve.py`** — leak-free signal + sleeve wiring.
  - **Alignment:** funding (8h) forward-filled onto the existing 4h price bars the
    conviction book uses; signal at bar *t* uses only funding observations with
    `time ≤ t` (unit-tested, no lookahead).
  - **Signal:** rolling funding z-score over window `W` (past-only mean/std);
    `z > +thr → short`, `z < −thr → long`, else flat.
  - **Sign convention:** Binance `fundingRate > 0` ⇒ longs pay shorts ⇒ crowd
    long ⇒ contrarian **short**. Cash-flow per held bar: short position earns
    `+rate · notional` per funding interval when rate > 0, pays when rate < 0;
    long is the inverse.
  - **Exit variants (frozen, see grid):** (a) **ATR-bracket** — entry + exit both
    run through `simulate_idx` first-touch SL/TP, fully reusing the trusted fill
    engine; (b) **hold-to-flip** — entry uses the same fill/cost assumptions, but
    the exit is signal-driven (close when z crosses back through 0 / flips sign),
    which is a *separate, small exit path* (not `simulate_idx` brackets) and
    therefore carries its own unit test. The fee/slippage model is identical
    across both variants.

- **Price source (explicit approximation):** both sleeves use the **same existing
  4h spot bars** (`data/ohlcv`) for price-PnL, so the orthogonality comparison has
  no price-series confound. Funding is overlaid as the only new cash-flow. Using
  perp **mark-price** bars is the stricter follow-up *if the sleeve survives* —
  out of scope for the spike.

- **Universe:** BTC + ETH + SOL only — the **same 3-coin universe** the conviction
  book was validated on. Do not reintroduce breadth here; that was tested and is a
  separate confound.

## Measurement — the actual prize

The question is not "is the funding sleeve good alone" but **"does it add
*independent* information past the correlation wall."** Two stages, both read
out-of-sample on the held-out last 50% of calendar time:

1. **Standalone:** sleeve alone through `simulate_idx` (cap-3 pooled, one per name)
   → `robustness` DSR + anchored walk-forward. Report OOS ret / Sharpe / maxDD /
   DSR / IS→OOS rank-corr / whole-grid OOS mean.
2. **Combined:** equal-weight (rebalanced) combination of the two sleeves' net
   per-period **return streams** (conviction book + funding sleeve). Report:
   - combined Sharpe and **combined DSR**, penalized by the **funding grid size
     (8 trials)** — the book is already fixed/paid-for, so only the new search is
     charged;
   - **pairwise return correlation ρ** between the two sleeves.

## Pre-registered grid & pass/kill bar (frozen BEFORE running)

**Grid = 8 cells**, deflated by 8 in the DSR penalty:
- `W` ∈ {30 bars ≈ 5d, 90 bars ≈ 15d}
- `thr` ∈ {1.0 (moderate), 2.0 (extreme)}
- exit ∈ {ATR-bracket, hold-to-flip}

Headline threshold selected on **in-sample Sharpe only** (no selection-on-test).

**KILL immediately** (write the honest negative-result doc, do **not** fold in)
if either:
- standalone OOS Sharpe ≤ 0, **or**
- IS→OOS rank-corr < 0 (this project's overfit detector — the cut strategies had
  −0.65 to −0.73).

**FOLD IN** only if **all** hold:
- combined DSR > 0.166 by a clear margin (the standalone book's current best), **and**
- combined Sharpe ≥ 1.15, **and**
- funding-sleeve return stream low-correlated with the price book: **|ρ| < 0.5**.

Anything between KILL and FOLD IN (e.g., positive but correlated, or DSR
unchanged) is documented as an **honest negative** — the sleeve is correlated
noise and does not earn a place. This is the same disposition breadth /
cross-sectional / leverage / trailing received.

## Testing (TDD)

- `test_funding_pipeline.py` — fixture raw JSON → parquet schema; pagination
  cursor advances; incomplete/forming interval dropped. **No network.**
- `test_funding_sleeve.py` — leak-free (signal at *t* uses only funding ≤ *t*);
  z-score correctness; sign convention (positive funding → short); cash-flow
  accrual sign & magnitude; flat when |z| < thr.
- `test_funding_combine.py` — combined return stream; correlation calc; DSR
  penalty uses grid size; **regression: book-alone path is byte-identical when the
  funding weight = 0.**

Run convention: `PYTHONWARNINGS=ignore` (per project test-suite gotchas).

## Deliverables

- `study/funding_pipeline.py`, `study/funding_sleeve.py` + the three test files.
- `docs/funding_sleeve_result.md` — written **after** running, landing as either
  "FOLDED IN, DSR 0.166 → X" **or** a documented negative, with the whole-grid
  table and IS→OOS corr, in the style of `docs/regime_book_before_after.md`.

## Phase 2 — Packaging (contingent, NOT designed here)

If/once Phase 1 resolves: OrderRouter (idempotency keys + retry queue) +
shadow→live promotion gate wrapping the existing `paper_trader`/`paper_safety`,
plus the unified Pro/Guided UI (Greeks, vol curves, risk overlays, kill-switch).
**Whether it wraps "book + funding sleeve" or "book alone" is decided by Phase 1's
result**, so its internals are out of scope until then.

## Non-goals

- No live wiring, no `app.state`, no `SterlingEngine` changes.
- No options/VRP work (parked, data-blocked).
- No new symbols / breadth (separate, already-negative confound).
- No leverage tuning (separate, already-cut).
