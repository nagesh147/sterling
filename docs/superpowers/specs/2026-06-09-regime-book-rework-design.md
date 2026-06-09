# Regime Book — Strategy Rework Design

**Date:** 2026-06-09
**Branch:** `feat/dsr-deflation-gate` (continues the audit/deflation work)
**Status:** Approved design → implementation

## Problem

The current edge stack (7 strategies in `app/engines/edge/strategies.py`) is
profitable in-sample but collapses out-of-sample, and nothing survives the
deflated-Sharpe bar (best DSR ≈ 0.10 ≪ 0.5). The failures are **structural**,
not parameter-tuning:

1. **Long-only.** All 7 signal fns ignore `simulate_idx(direction="short")`.
   A long-only book in the −34% OOS BTC tape is structurally doomed — this is
   why `ma_crossover` went +119% IS → −11% OOS.
2. **No regime gate.** Momentum fires in downtrends; mean-reversion fires in
   crashes. The right strategy runs in the wrong regime.
3. **Single-symbol streams.** 3 separate ~150-trade backtests keep n below the
   deflation bar. Pooling the 3 symbols into one book ~3×'s n.

Hard data constraint: only **3 symbols locally** (BTC/ETH/SOL 1-min parquet).
The "15–30 coin basket" path is not runnable here.

## Goal & success bar

Optimize for **forward (anchored walk-forward, out-of-sample) performance**,
scored through the **existing unflattering harness** — `deflated_sharpe_ratio`,
`beats_buy_and_hold`, Monte-Carlo P(loss). No new metric that flatters.

- **Primary:** turn the long-only single-symbol book into a **symmetric, pooled,
  regime-gated book** that is **forward-green and beats buy-and-hold** across
  BTC/ETH/SOL in the OOS span (where BTC fell −34%).
- **Stretch:** clear DSR ≥ 0.5. Honestly a long shot with 3 symbols; if it
  doesn't clear, we say so plainly and ship the best forward-green stack.
- **Discipline:** every added degree of freedom must beat the simpler version
  **out-of-sample** or it is cut. Additions earn their place vs a walk-forward
  baseline, never an in-sample one.

## Approach (chosen)

**B-spine + one measured regime knob.**

- **Spine (B):** shorts + multi-symbol pooling, minimal degrees of freedom.
- **+1 knob (A):** a leak-free regime gate, added *on top of* the spine and
  accepted only if it beats the spine out-of-sample.
- Rejected: **C (ML meta-labeling/ensemble)** — overfit risk too high on 3
  symbols; dishonest given the data.

The deflation `num_trials` grows with every knob, so minimizing DoF is itself a
strategy for clearing the bar — each knob is added deliberately and measured.

## Components

New research module `backend/study/regime_book.py` (pure functions, no live
wiring), reusing/extending `study/sim.py`. Nothing is wired into the live edge
feed until it clears the registry gate — consistent with the audit discipline.

### 1. Regime classifier — `classify_regime(df) -> np.ndarray[int]`
Leak-free (only past/current bars via `.shift`/rolling). Returns per-bar regime:
`+1` uptrend, `-1` downtrend, `0` range. Built from ADX(14) trend strength + a
slow-MA slope sign. Threshold(s) are the *single* regime knob (kept minimal).

### 2. Sleeve signals — long **and** short
Reuse existing `signals_*` for the long side; add mirrored short triggers:
- Momentum short: bearish MA cross while regime `-1`.
- MR short: fade the upper Bollinger band while RSI hot, in regime `0`.
Router maps regime → (sleeve, allowed directions):
`+1 → momentum long`, `-1 → momentum short`, `0 → mean-reversion long+short`.

### 3. Portfolio sim — `simulate_portfolio(frames, ...)`
One $500 capital book across the 3 symbols. Each symbol contributes signals to
a single equity stream; a **max-concurrent-positions / risk-per-name cap**
prevents stacking all capital into one move. Built on `simulate_idx` per symbol,
then merged on entry timestamp into one ordered pnl stream.

### 4. Exit upgrade (A/B) — ATR trailing + time stop
Extend `simulate_idx` with an optional chandelier/ATR-trailing stop and a hard
time stop, A/B'd against the fixed bracket. Off by default; accepted only if it
beats the fixed bracket OOS.

### 5. Honest scoring — unchanged harness
Anchored walk-forward (select-on-past) → stitched OOS stream → `sharpe`,
`deflated_sharpe_ratio(num_trials=grid)`, `beats_buy_and_hold`, P(loss).

## Data flow

```
1m parquet × {BTC,ETH,SOL}
   → resample(4h/2h)  [study/strategies.resample]
   → classify_regime per symbol           (leak-free)
   → route → long/short sleeve signals
   → simulate_idx per symbol (long & short, optional trailing)
   → merge into one timestamp-ordered book  [simulate_portfolio]
   → anchored walk-forward (select-on-past)  [no lookahead]
   → DSR / beats-hold / P(loss)              [existing harness]
   → before/after report  (docs/)
```

## Testing (TDD — tests first)

Load-bearing tests (the no-lookahead guarantees):
- `classify_regime` uses no future bars (truncating the tail can't change an
  earlier bar's regime).
- Short routing: a known synthetic downtrend produces profitable shorts; a
  long-only run on the same data loses.
- `simulate_portfolio` respects the concurrent-position cap and merges streams
  in timestamp order (no double-spend of capital).
- Walk-forward selection ignores trades at/after the cutoff (reuse the pattern
  from `test_mean_reversion_wf.py`).
- Trailing-exit math: a trade that runs then reverses exits at the trailed
  stop, not the fixed stop.

Run with `PYTHONWARNINGS=ignore` and `.venv/bin/python`.

## Deliverables

1. `backend/study/regime_book.py` + tests (all green, zero-regression vs suite).
2. Before/after report `docs/regime_book_before_after.md` on the same $500 real
   data: long-only single-symbol baseline → symmetric pooled regime book, FULL /
   IS / OOS columns, with the DSR / hold-beat verdict.
3. A plain-English verdict on whether the regime gate earned its complexity and
   whether anything clears DSR ≥ 0.5.

## Out of scope (YAGNI)

- No live-feed wiring, no new endpoints, no UI. Research + honest report only.
- No new data sources / extra symbols (not available locally).
- No ML/ensemble layer.

## Honest expectation

With 3 symbols, pooled n maxes ~3×; DSR ≥ 0.5 remains a long shot. Realistic
win: a forward-green, hold-beating book in a bear tape via shorts + regime gate,
and a proof of whether the regime gate is worth its degrees of freedom.
