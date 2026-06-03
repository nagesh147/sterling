# SterlingV2 — Toggle-Isolated Engine Redesign

**Design spec** · Date: 2026-06-03 · Branch: `redesignV2`
Status: **Approved design — pending implementation plan**

> Companion context (real-data baseline this design improves on):
> [`STERLING_TRADING_REPORT_BASELINE.md`](../../../STERLING_TRADING_REPORT_BASELINE.md) ·
> [`STERLING_TRADING_REPORT_BEFORE_AFTER.md`](../../../STERLING_TRADING_REPORT_BEFORE_AFTER.md)

---

## 0. Goal

Deliver a new, toggle-isolated **SterlingV2** mode that demonstrably improves the trade
metrics — **win rate, profit factor (PF), net profit, Sharpe, and max drawdown** — over the
existing Sterling baseline, **proven on the real 1-minute parquet vector stores under
leak-free validation**, and wired into the live (paper) path behind a UI chip toggle.

**Hard constraints (from the brainstorm):**

1. **Additive isolation.** The existing **Sterling engine and Grok engine must remain
   byte-for-byte unchanged.** SterlingV2 is a parallel slice surfaced only when a new
   `SterlingV2` chip toggle is ON. Promotion into the main Sterling dashboard happens later,
   only after full verification — out of scope here.
2. **No Kronos / no torch.** The "trade fewer, better" conviction filter is achieved with
   interpretable models on the TA features already in the parquet (no foundation model, no
   GPU dependency).
3. **Real-data-proof.** Every claimed improvement is measured on
   `vector_store_1m_{BTC,ETH,SOL}USD.parquet` (~Dec 2023 → May 2026, ~3.56M 1m bars) through
   a leak-free harness, reported on an untouched test set.
4. **Both research and live.** Deliver a validated OOS research result **and** wire the
   validated logic into the live signal path behind the toggle (paper mode, auto-execute OFF).
5. **Composite objective.** Optimize a composite of Sharpe + drawdown, PF/win, and net
   profit (Section 4).

---

## 1. Critique of the existing engine (what we are fixing)

Verified against the real code:

**Architecture**
- `engines/directional/orchestrator.py:1-96` is a **stub** — the regime→signal→setup→sizing
  pipeline was stripped in the strategy reset; `run_once`/`preview` return `IDLE`/`NEUTRAL`.
  Live signals actually come from `engines/edge/signals.py` + the scalper.
- `engines/edge/strategies.py` — every strategy is a one-line, **long-only** vectorized
  trigger (EMA 9/21 cross, 20-bar Donchian, RSI cross-up, bullish engulfing, FVG). No
  individual edge; fired on every occurrence over a mostly-up market.
- **No conviction/regime gate** sits between signal and router → the system fires every
  signal. This is the structural flaw the real-data reports identify: median config PF < 1.0
  at every timeframe; the 10 in-sample "winners" bleed **−$674** out-of-sample.

**Measurement bugs (why current numbers are not yet trustworthy)** — `comprehensive_backtest.py`:
- **Sharpe mis-annualized:** `√252 × mean/std` on per-trade returns for *every* timeframe
  (`:194-197`); `BARS_PER_YEAR` (`:41-44`) is defined but unused.
- **No funding/slippage/spread:** `simulate()` applies only a flat 0.1% fee (`:120,135`),
  yet the report bills futures as "leverage + funding + fees."
- **In-sample selection:** `main()` ranks all configs on full history and picks winners
  (`:232-276`); no train/test separation.
- **DSR under-corrects:** robustness gate gets `num_trials=21` (`:261`) vs a true search space
  of ~378 → multiple-testing deflation too lenient.
- **Intrabar lookahead** in trailing: trail updates from `high[i]` then exit-checks the same
  bar (`:106-132`); entries fill at signal-bar `close[i]`.
- **No portfolio:** "$5,000" is 10 independent $500 sleeves, not a correlation-aware book,
  even though `correlation_tracker` and `dd_circuit_breaker` exist on the engine.

---

## 2. Isolation architecture (the toggle)

**Principle: additive only.** No edits to `engines/directional/*`, `engines/edge/*`,
`engines/scalping/*`, Grok components, or existing endpoints — except a single additive
`include_router(...)` line.

### 2.1 Backend (new, isolated)

New package `app/engines/sterling_v2/`:

| File | Purpose |
|---|---|
| `signals.py` | Long **and short** symmetric signals (mirrors the 5 entries) |
| `regime.py` | Interpretable conviction/regime gate (no torch) |
| `exits.py` | Exit engine: ATR trailing + partial scale-out + breakeven + time-stop |
| `sizing.py` | Volatility-targeted / fixed-fractional position sizing |
| `portfolio.py` | Correlation-aware multi-asset allocation + portfolio vol target |
| `harness.py` | Leak-free research simulator (single source of truth) |
| `config.py` | V2 defaults (thresholds, caps, toggles) |

New endpoint `app/api/v1/endpoints/sterling_v2.py`, `APIRouter(prefix="/sterling-v2",
tags=["sterling_v2"])`, registered with **one additive `include_router` line** where the other
v1 routers are registered. Endpoints:

- `GET  /sterling-v2/signals` — live gated long/short signals (same code as harness)
- `POST /sterling-v2/backtest` — run the leak-free harness on chosen symbols/TFs/levers
- `GET  /sterling-v2/research` — latest validated research report (test-set metrics)
- `GET|POST /sterling-v2/config` — V2 knobs (default OFF/paper)

**Reused, never modified:** `analytics/cpcv.py` (`run_cpcv`, `calculate_pbo`,
`CPCVConfig.from_hold_bars`), `analytics/walk_forward.py` (`run_real`),
`analytics/monte_carlo.py` (p-loss), `risk/slippage.py`, `risk/circuit_breaker.py`
(`DrawdownCircuitBreaker`), `risk/regime_adaptive_sizer.py`, `analytics/correlation.py`.

### 2.2 Frontend (new, isolated)

- `store/useStore.ts`: add `sterlingV2: boolean` (persisted key `sterling_v2_enabled`,
  default **false**) + `useSterlingV2()` / `setSterlingV2()`. **No change to `engineMode`.**
- A **chip toggle "SterlingV2"** rendered only inside the Sterling view. OFF → existing
  Sterling UI unchanged. ON → mounts a new `SterlingV2Tab` + panes that call `/sterling-v2/*`.
- New components only (`SterlingV2Tab`, signal pane, research/backtest pane, before/after
  panel). GrokTab and existing Sterling panes untouched.

---

## 3. The foundation: leak-free research harness (built first, gates everything)

`sterling_v2/harness.py` is built and validated **before** any lever, and is the **sole
arbiter** of every later change. It fixes the Section 1 measurement bugs:

| Bug | Fix |
|---|---|
| Constant `√252` Sharpe | Annualize via **realized trade frequency** from actual timestamps |
| No costs | Per-bar **funding** (perp) + **slippage** (`risk/slippage.py`) + spread on entry/exit; stops fill at stop ± slippage |
| In-sample selection | **Train / validation / test** chronological split (default **60/20/20**) with purge + embargo at boundaries; thresholds chosen on train+val only; metrics reported on untouched test. **Plus** purged-embargoed walk-forward (`walk_forward.run_real`) and **CPCV** (`run_cpcv`) for robustness |
| DSR `num_trials=21` | Pass the **true** search-space size → honest Deflated Sharpe; report **PBO** (`calculate_pbo`) and Monte-Carlo **p-loss** |
| Intrabar lookahead | Trailing uses only bars **≤ i−1**; entries fill **next-bar open**, not signal-bar close |

**Outputs:** one reproducible artifact per experiment — a results CSV plus a markdown report
carrying test-set Sharpe / PF / win / net / max-DD + p-loss + PBO + DSR + trade count.

**Correctness gate (Phase 2):** the harness must **reproduce the existing baseline numbers**
(within tolerance) before any lever is trusted — proving the simulator is right, not just
different.

---

## 4. Improvement levers (approach 1 + 3, no Kronos)

Each lever is a toggleable module, measured **independently** then **stacked**, accepted only
if it improves the test-set composite without raising PBO. Priority order:

1. **Short side** — mirror the 5 signals symmetrically. De-biases the long-only/up-market
   skew; ~doubles opportunity.
2. **Conviction/regime gate (interpretable Kronos replacement)** — gate entries on a
   transparent regime score from the **93 TA features already in the parquet**: higher-
   timeframe trend agreement + ADX + volatility state + a small **logistic / gradient-boosted
   classifier trained with purged CV**. Delivers "trade fewer, better" without a foundation
   model. This is the highest-impact lever (the baseline's core failure is firing every signal).
3. **Exit engine** — ATR trailing + partial scale-out + breakeven + time-stop. (Logic exists
   in the old harness but is absent from default profiles; reports note "trailing is the main
   edge.") Lifts PF, cuts DD.
4. **Vol-targeted sizing** — size each trade to a target volatility / fixed-fractional risk
   (reuse `risk/regime_adaptive_sizer.py`), replacing flat $500. Lifts Sharpe, caps tails.
5. **Correlation-aware portfolio** — combine the durable edges (4h BTC/ETH/SOL) into one book
   with a portfolio vol target, correlation penalty (`analytics/correlation.py`), and the
   `DrawdownCircuitBreaker` as a hard DD cap.

---

## 5. Validation protocol & acceptance gates

**Objective:** maximize **test-set Sharpe subject to max-DD ≤ 20%**, while **not degrading**
test-set **PF, win rate, or net profit** versus baseline.

**Pre-registered robustness gates (fixed before the test set is touched):**

- OOS (test-set) Sharpe **> 0**
- **PBO < 0.5** (probability of backtest overfitting)
- Monte-Carlo **p-loss ≤ 35%**
- **DSR > 0** (deflated for the true trial count)
- **≥ ~100 test trades** for statistical meaning

A lever ships **only if** it beats baseline on the **test set** under all gates. Anything that
wins only in-sample is **rejected and documented**. The test set is evaluated **once**, at the
end of each lever's tuning, to prevent the double-dip that invalidated the Kronos result.

**Lookahead placebo test:** random/shuffled signals must score ~0 net edge after costs through
the harness — a CI guard against accidental leakage.

---

## 6. Live wiring behind the toggle

- `GET /sterling-v2/signals` runs the **same validated logic** live (long+short, gated, with
  exit/sizing metadata) on streaming candles — identical code path to the harness (single
  source of truth, mirroring the existing `edge/strategies.py` discipline).
- Routes through the **existing** paper order router in **paper mode**; **auto-execute OFF**.
  The existing router is untouched (V2 only calls it).
- The V2 tab surfaces: live gated signals, the test-set backtest report, equity curve, and a
  **before/after vs baseline** panel.

---

## 7. Testing strategy

- **Unit:** harness correctness (Sharpe annualization vs hand-computed; cost application;
  next-bar-open fills), each lever module, and the new endpoints.
- **No-lookahead assertions:** the placebo/shuffle test (Section 5) plus explicit assertions
  that gate/trail inputs reference only bars ≤ i−1.
- **Reproduction test:** Phase-2 baseline reproduction within tolerance.
- **Isolation test:** a smoke test confirming existing Sterling/Grok endpoints and the
  `engineMode` flow are unchanged with the toggle OFF.

---

## 8. Phasing

1. **Skeleton + isolation** — new package, new router (additive), FE chip toggle (default OFF),
   empty V2 tab. Verify existing engines untouched.
2. **Harness + baseline reproduction** — leak-free simulator; reproduce existing numbers.
3. **Levers one-by-one** — short side → conviction gate → exits → sizing, each with test-set
   evidence and gate compliance.
4. **Portfolio assembly** — correlation-aware book + DD circuit breaker.
5. **Live wiring** — `/sterling-v2/signals` + paper router + V2 UI panes.
6. **Final report** — before/after vs baseline on the test set, reproducible.

---

## 9. Out of scope

- Kronos / any torch or GPU dependency.
- Modifying the existing Sterling or Grok engines, or promoting V2 into the main dashboard.
- Options × V2 dollar backtesting (no historical IV chain; win%/PF-only at most, deferred).
- Live (real-money) auto-execution.

---

## 10. Reproducibility

- Data: `vector_store_1m_{BTC,ETH,SOL}USD.parquet`, ~Dec 2023 → May 2026.
- Harness, configs, and per-experiment CSV/markdown artifacts committed under the V2 package /
  a `docs/` results path.
- Baseline for comparison: `STERLING_TRADING_REPORT_BASELINE.md` and the before/after report.
