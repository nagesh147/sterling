# TTACE — Foundation Done; What Comes Next

Status: TTACE foundation merged on the `ttace` branch. This document
defines the *next* sequence of work and the gates each piece must pass.

The order below is deliberate. Skipping ahead is what produced the
contaminated baseline we just replaced.

---

## What changed under TTACE (already on this branch)

1. **Truthful MTF backtest costs and fills**
   * Fills land on the OPEN of the bar after the signal bar (was: signal-bar
     close). No more single-bar lookahead on entry/exit.
   * `compute_trade_costs` in `app/engines/backtest/costs.py` attributes
     slippage (using `risk/slippage.py`), taker fees, perpetual funding
     scaled by hold time, and optional option half-spread cost.
   * Trades carry `gross_pnl_pct`, `net_pnl_pct`, `cost_pct`,
     `entry_price`, `exit_price`, `hold_hours`, and `forced_end`.
   * End-of-data closeouts are explicitly marked.
2. **Honest performance metrics**
   * Sharpe defaults to calendar-time daily returns when timestamps exist;
     falls back to per-bar annualisation by `signal_bar_ms`; the old
     8760-everywhere annualisation is gone.
   * Sortino uses LPM downside deviation.
   * Profit factor returns `+inf` for "winners and no losers" (was 0.0).
   * Adds CAGR, ulcer index, pain ratio, tail ratio.
   * `deflated_sharpe(...)` returns the Bailey / Lopez de Prado probability;
     more trials → lower probability; higher Sharpe → higher probability.
3. **Cold-start risk safety**
   * `CalibrationService.win_rate()` returns `None` on insufficient samples.
     Legacy 0.52 is available only via `win_rate(fallback=0.52)`.
   * `RiskParams.win_rate_known` (default True) lets callers explicitly
     mark "edge unknown" so the sizer fails closed.
   * `size_trade` returns `contracts=0` + `blocked_reason` when the edge is
     unknown OR when fractional Kelly is non-positive.
4. **Immutable research event ledger**
   * `app/engines/backtest/event_ledger.py` is a pure module — no I/O, no
     DB, no exchange calls. Backtest emission is opt-in via
     `run_mtf_backtest(..., emit_events=True)`. Default API shape is
     unchanged.
5. **Baseline report**
   * `backend/baseline_report.py` produces a truthful, conservative report
     (deflated Sharpe gated on n>=50, regime buckets warn under 10, etc.).
     Does NOT read from the live `positions` aggregate stats — those are
     pre-TTACE contaminated.

---

## Revised task order

### Step 1 — Replay the canonical universe with TTACE
1. Generate / load a real-data 1H + 4H universe per asset (BTC, ETH).
2. Run `run_mtf_backtest(..., emit_events=True, apply_slippage=True,
   funding_8h_pct=<observed mean>)` for each profile.
3. Feed the trade list into `build_report` per asset / profile.
4. Hold the resulting numbers as the new "honest baseline".

**Gate:** every result must come with a `warnings` list. If `deflated_sharpe`
is `None`, the run is not a baseline — it's a smoke test.

### Step 2 — Walk-forward validation on the directional track
1. Use the existing `engines/analytics/walk_forward.py` over the same
   universe.
2. Lookahead veto: parameter selection must not see the test window.
3. Acceptance: deflated Sharpe > 0.95 in 2 of 3 windows on at least
   one profile, **after** costs.

**Gate before Step 3:** without this passing, *no* candidate-track or ML
work is justified. Either the edge survives walk-forward or there is no
edge.

### Step 3 — Candidate-track architecture
The directional track is one of multiple tracks the ledger already
distinguishes by `track` tag. Future tracks should plug into the same
event ledger and the same calibration interface
(`CalibrationService.win_rate(track="mean_reversion")`).

#### 3a. Mean-reversion / range-quality track
A clean range-quality signal is a Bollinger / Keltner squeeze score
combined with proximity to a mean (EMA20 / VWAP) plus an ADX ceiling.
The hypothesis: in low-ADX, high-squeeze regimes, fades back to the mean
have positive expectancy after costs. Trades exit at mean touch or on
ADX breakout.

Acceptance gates (must pass before ML or UI work):
* Track tagged trades reach >=200 sample size.
* `CalibrationService.win_rate(track="mean_reversion")` calibrates without
  fallback.
* Deflated Sharpe > 0.95 on walk-forward after costs.

#### 3b. Breakout-quality track
Squeeze + ATR percentile + volume z-score gating, followed by a structural
break (e.g. close beyond N-bar range) with an ATR-multiple trailing exit.
Same acceptance gates.

### Step 4 — Validation gates before ML
ML (XGBoost, etc.) is *only* useful once feature streams are honest and the
non-ML tracks survive walk-forward. The order:

1. Honest truthful backtest — done (TTACE Phase 1).
2. Honest metrics — done (TTACE Phase 2).
3. Cold-start safety — done (TTACE Phase 3).
4. Event ledger — done (TTACE Phase 4) → ML features are derived from this
   ledger, not from anything the engines compute live.
5. At least one track survives walk-forward with deflated Sharpe > 0.95.
6. Cross-asset (BTC + ETH minimum) sanity: same direction of signal.
7. **Only then** introduce a model layer. Recommended starting point:
   classification of `candidate` events into "took, profitable" /
   "took, unprofitable" / "rejected". Train / validate / test split on
   non-overlapping calendar windows.

### Step 5 — Why XGBoost is deferred
* The trade table the model would be trained on was previously contaminated
  by signal-bar fills and silent 0.52 win rate. Any model trained on that
  inherits the bias.
* Without walk-forward survival of a hand-coded track, the model has no
  reference point. A model that out-performs a broken baseline is not
  evidence of skill.
* ML compounds noise when feature reliability is unknown. The ledger from
  Phase 4 gives us reproducible features; we need to verify they are
  predictive *without* a model first.

### Step 6 — Frontend / demo work
None of the DRiFT, ensemble, demo-replay, or live paper-run frontends
should be expanded until Step 2 passes. The current UI claims rely on
contaminated metrics; ship better numbers before shipping more pixels.

---

## What must pass before frontend or demo work

* TTACE foundation tests are green (see `tests/test_backtest_costs.py`,
  `tests/test_analytics_performance_honest.py`,
  `tests/test_cold_start_safety.py`, `tests/test_event_ledger.py`,
  `tests/test_baseline_report.py`).
* Step 1 replay produces a baseline report with no `warnings` containing
  `low_sample_size`.
* Step 2 walk-forward returns deflated Sharpe > 0.95 in >=2/3 windows on
  at least one profile / asset.
* Cross-asset replay (BTC + ETH minimum) agrees on sign of expectancy.

If any of those fails, fix the engine — do not paper over it with UI
copy or more profiles.

---

## File map for reviewers

* `backend/app/engines/backtest/costs.py` — TTACE Phase 1
* `backend/app/engines/backtest/backtest_mtf.py` — wired Phase 1+4
* `backend/app/engines/analytics/performance.py` — TTACE Phase 2
* `backend/app/services/calibration.py` — TTACE Phase 3
* `backend/app/engines/directional/sizing_engine.py` — TTACE Phase 3
* `backend/app/schemas/risk.py`, `backend/app/schemas/execution.py` —
  additive schema fields
* `backend/app/engines/backtest/event_ledger.py` — TTACE Phase 4
* `backend/baseline_report.py` — TTACE Phase 5
