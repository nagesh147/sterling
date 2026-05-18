# TODO-AI: Sterling Triple-Track Adaptive Crypto Engine (TTACE)

> **Purpose.** This file is the executable plan for upgrading Sterling from a negative-expectancy single-track trend-follower into a statistically-defensible regime-routed ensemble that wins a crypto-trading hackathon.
>
> **Audience.** An AI coding agent (Claude Code, Cursor, or human engineer) executing tasks top-to-bottom. Each task is self-contained, has acceptance criteria, and references the canonical specs.
>
> **Companion docs.** `docs/STERLING_HANDOFF.md` (architecture), `STERLING-V4-SPEC.md` (canonical strategy), `CLAUDE.md` (invariants).
>
> **Status.** Draft v1.0 — 2026-05-18. Branch: `ttace`.

---

## 0. TL;DR

- **Problem.** Current Sterling strategy is negative-expectancy: OOS Sharpe -207, 0% WR over 26 walk-forward windows. 6-month replay across BTC/ETH/SOL on 15m+1H produced PF < 1 for 5/6 configurations.
- **Solution.** Three regime-gated alpha tracks (Trend / Mean-Reversion / Volatility-Breakout), gated by an XGBoost meta-filter, sized with adaptive fractional Kelly, capped by drawdown circuit breaker, validated with CPCV + Deflated Sharpe.
- **Target.** CAGR +38%, Sharpe 1.9, Max DD -9%, Win rate 51%, Deflated SR p<0.10 — all with realistic costs (slippage + funding + spread).
- **Build cost.** ~72 engineering hours, touching ~12 files in an established codebase (718 tests, FastAPI + React).
- **Win condition.** Demonstrable outperformance vs. buy-and-hold, EMA crossover, and Sterling v3 baseline, with deflated-Sharpe p-value judges will respect.

---

## 1. Strategy Overview

### 1.1 The Triple Tracks

| Track | Regime trigger | Edge thesis | Position | Bars covered |
|---|---|---|---|---|
| **A. Trend-Continuation** (existing, fixed) | `BULL_TREND` / `BEAR_TREND` w/ ADX>20, ATR%>50 | Crypto autocorrelation in trends; Heikin-Ashi alignment | Directional futures 3-5x, ATR Chandelier trail | ~25% |
| **B. Mean-Reversion** (NEW) | `RANGING` / `IDLE`, ATR%<35, RSI extremes | Crypto majors mean-revert in low-vol; funding-rate fade | Tight 0.5R stops, fade BB extremes | ~50% |
| **C. Volatility-Breakout** (NEW) | `VOLATILE` regime, BB+KC squeeze->expansion | Squeeze release pays asymmetric R | OCO bracket, 3R target | ~15% |
| **D. Stand-down** | High funding window + dead zone | Adverse selection >> edge | No trade | ~10% |

### 1.2 DRiFT Composite Ranker

A trade fires only when:

```
DRiFT(structure) = structure.score / 100
                 * meta_filter.predict(features)       # XGBoost P(profitable)
                 * (1 - correlation_penalty(open))     # existing v3
                 * (1 - vol_of_vol_penalty(vov))       # existing v3
                 * kelly_fraction(adaptive_WR, rr)     # adaptive
```

Gate: `DRiFT >= 0.55` AND rolling-30-day deflated Sharpe p-value < 0.20.

### 1.3 KPIs (Targets)

| Metric | Conservative | Stretch | Source |
|---|---|---|---|
| CAGR | +35% | +85% | 6-mo replay |
| Sharpe (calendar-time) | 1.8 | 2.6 | fixed performance.py |
| Calmar | 2.5 | 4.0 | CAGR / Max DD |
| Max DD | -12% | -7% | Drawdown CB at 8% |
| Win rate | 48% | 55% | MR + BO boost |
| Profit factor | 1.6 | 2.2 | Asymmetric exits |
| Deflated Sharpe p-val | < 0.10 | < 0.05 | Bailey & Lopez de Prado |

---

## 2. Architecture Delta

### 2.1 New / modified files

```
backend/app/engines/
| directional/
| | tracks/                          <- NEW
| |   trend_track.py                 <- wraps existing scoring
| |   mean_reversion_track.py        <- NEW
| |   breakout_track.py              <- NEW
| | meta_filter/                     <- NEW
| |   feature_builder.py
| |   xgb_filter.py
| |   train_meta_filter.py           <- offline trainer
| | drift_ranker.py                  <- NEW (composite)
| | orchestrator.py                  <- MODIFIED to fan out -> tracks
| backtest/
| | backtest_mtf.py                  <- FIX W4/W5/W6
| analytics/
| | performance.py                   <- FIX W10
| | deflated_sharpe.py               <- NEW
| | cpcv.py                          <- NEW
| risk/
|   slippage.py                      <- WIRE into backtest

backend/app/api/v1/endpoints/
  demo.py                            <- NEW replay endpoint
  ensemble.py                        <- NEW ensemble stats

frontend/src/components/
  DRiFTPanel.tsx                     <- NEW
  EnsembleEquityCurve.tsx            <- NEW
  DeflatedSharpeBadge.tsx            <- NEW
  BenchmarkComparePanel.tsx          <- NEW

xgb_model.json                       <- trained meta-filter artifact (committed)
```

### 2.2 Invariants (DO NOT VIOLATE)

From `CLAUDE.md`:
- `CorrelationTracker.update()` called on EVERY `evaluate()` with 1H close
- `DrawdownCircuitBreaker.update()` called FIRST inside `evaluate()`, before any strategy logic
- `CalibrationService.record_trade()` called on EVERY position close
- Walk-forward MUST NOT use test-window data to select the threshold (lookahead veto)
- Pure functions in `engines/*` — no I/O, no `time.time()`, no DB calls
- Pydantic schemas additive-only (Optional with defaults)
- OHLCV `time` is in **seconds** — multiply by 1000 when constructing `Candle`
- Use `code-review-graph` MCP tools before Grep/Read

---

## 3. Task Queue (Execute In Order)

Each task has: **Goal -> Files -> Steps -> Acceptance -> Test command**.

---

### T1. Truthful Backtest Costs (Tier S, addresses W4/W5)

**Goal.** Eliminate look-ahead bias and bake real-world costs into the MTF backtest so reported metrics survive judge scrutiny.

**Files.**
- `backend/app/engines/backtest/backtest_mtf.py`
- `backend/app/engines/risk/slippage.py` (already exists; just wire it)
- `backend/tests/test_truthful_costs.py` (NEW)

**Steps.**
1. Change entry fill: `candles[i].close` -> `candles[i+1].open`. Same for exits — fill at next-bar open, not signal-bar close.
2. Import `effective_entry(leverage, oi_tier)` from `risk/slippage.py`; apply on both entry and exit.
3. Add funding accrual for futures: `pnl_pct -= 0.0001 * (hold_hours / 8.0)`.
4. Add option half-spread cost per leg: `pnl_pct -= (ask - bid) / (2 * mid)`.
5. Replace `_FEE_RT_PCT = 0.001` with `make_cost_model(structure_type)` that returns total round-trip pct.

**Acceptance.**
- A synthetic +2R trend trade now nets ~15-25 bps less than the old frictionless number.
- BTC 6-month replay (15m profile) total return drops by 8-15 percentage points vs. current optimistic backtest.
- All existing backtest tests still pass.

**Test.**
```bash
cd backend && pytest -q tests/test_truthful_costs.py tests/test_backtest_mtf.py
```

---

### T2. Honest Performance Metrics (Tier S, addresses W10)

**Goal.** Fix the Sharpe/Sortino/Calmar/PF bugs in `analytics/performance.py` so reported ratios are not biased by ~10x.

**Files.**
- `backend/app/engines/analytics/performance.py`
- `backend/app/engines/analytics/deflated_sharpe.py` (NEW)
- `backend/tests/test_performance_metrics.py` (extend)
- `backend/tests/test_deflated_sharpe.py` (NEW)

**Steps.**
1. Rewrite `compute()`:
   - Sharpe = `(mean_daily_ret / std_daily_ret) * sqrt(365)` where daily returns aggregated by calendar date, NOT by trade.
   - Sortino = `mean_daily / sqrt(LPM(0, 2))` where `LPM(0,2) = mean(min(r,0)**2)`.
   - PF: return `math.inf` when `sum(losses) == 0`.
   - Add CAGR (CAGR = (final/initial)^(365/days) - 1).
   - Add Ulcer index, Pain ratio, tail_ratio (95th/5th return pct).
2. Create `deflated_sharpe.py`:
   ```python
   def deflated_sharpe_ratio(sr: float, n_trials: int, T: int,
                              skew: float, kurt: float) -> tuple[float, float]:
       """Bailey & Lopez de Prado DSR. Returns (DSR, p_value)."""
   ```

**Acceptance.**
- Sharpe on a known-good fixture (constant +0.1% daily) returns ~1.6, not 9.x.
- DSR on a noise series (0 true SR, 100 trials) returns p > 0.5.
- DSR on Sharpe = 2.5 with n=200, 10 trials returns p < 0.10.

**Test.**
```bash
cd backend && pytest -q tests/test_performance_metrics.py tests/test_deflated_sharpe.py
```

---

### T3. CPCV Validation Engine (Tier B #10)

**Goal.** Replace single-rolling walk-forward with Combinatorial Purged Cross-Validation (Lopez de Prado) so threshold selection isn't overfit to one path.

**Files.**
- `backend/app/engines/analytics/cpcv.py` (NEW)
- `backend/tests/test_cpcv.py` (NEW)

**Steps.**
1. Implement `cpcv_splits(n_samples, n_splits=10, n_test_groups=2, embargo=...)`:
   - Standard combinatorial purged CV with embargo period = `2 * max_hold_bars`.
2. Implement `run_cpcv(candles, signal_fn, threshold_grid, config) -> CPCVResult`:
   - Returns per-fold metrics + probability of backtest overfitting (PBO).
3. Test against a synthetic dataset where the true edge is at threshold=8: PBO should drop monotonically as n_splits grows.

**Acceptance.**
- `run_cpcv` returns 45 train/test combinations for `n_splits=10, n_test_groups=2`.
- Embargo correctly removes overlapping bars at fold boundaries.
- PBO < 0.5 on synthetic dataset with known edge.

**Test.**
```bash
cd backend && pytest -q tests/test_cpcv.py
```

---

### T4. Mean-Reversion Track (NEW alpha source)

**Goal.** Harvest the 38% IDLE bars currently thrown away by adding a mean-reversion track gated by funding-rate sign.

**Files.**
- `backend/app/engines/directional/tracks/__init__.py`
- `backend/app/engines/directional/tracks/mean_reversion_track.py` (NEW)
- `backend/tests/test_mr_track.py` (NEW)

**Steps.**
1. Define:
   ```python
   def evaluate_mr(
       regime: RegimeResult,
       signal: SignalResult,
       candles_signal_tf: list[Candle],
       funding_rate: float,
   ) -> Optional[TradeStructure]:
       ...
   ```
2. Entry conditions:
   - `regime.macro_regime in {RANGING, IDLE}` OR (`VOLATILE` AND `regime.adx < 18`)
   - `RSI(2) < 10` (long) OR `RSI(2) > 90` (short)
   - Last bar touched lower BB (long) or upper BB (short)
   - `sign(funding_rate)` opposes trade direction (we fade the carry)
   - `abs(funding_rate) < 0.015`
3. Exit:
   - 50% off at BB middle band; rest at mean
   - Hard stop at `0.5 * ATR(signal_TF)` beyond entry
   - Time stop: `hold_bars // 2`

**Acceptance.**
- Track produces 30+ trades per asset on 6-month replay.
- Win rate on MR-only replay > 55%.
- Average R > 0 with truthful cost model from T1.

**Test.**
```bash
cd backend && pytest -q tests/test_mr_track.py
```

---

### T5. Volatility-Breakout Track (NEW alpha source)

**Goal.** Capture asymmetric R from squeeze releases — a regime where trend-following arrives late.

**Files.**
- `backend/app/engines/directional/tracks/breakout_track.py` (NEW)
- `backend/tests/test_bo_track.py` (NEW)

**Steps.**
1. Entry conditions:
   - `regime.macro_regime == VOLATILE` OR (`signal.squeeze_released` AND `regime.atr_slope > 0`)
   - BB+KC squeeze active on prior bar; current bar breaks out (close beyond BB band)
   - Volume > 2x median(last 20)
   - Close beyond 5-bar high (long) or 5-bar low (short)
2. Exit:
   - 3R bracket as OCO
   - Trailing `1.5 * ATR(signal_TF)` Chandelier
   - Time stop: `hold_bars`

**Acceptance.**
- Track produces 15+ trades per asset on 6-month replay.
- Average R-multiple > 1.5 (asymmetric exit pays).
- Win rate >= 40% (lower WR ok if R is high).

**Test.**
```bash
cd backend && pytest -q tests/test_bo_track.py
```

---

### T6. XGBoost Meta-Filter

**Goal.** Add ML credibility without ML-prediction risk. The model predicts `P(trade profitable)` given regime + signal + microstructure features; used as a final veto only.

**Files.**
- `backend/app/engines/directional/meta_filter/__init__.py`
- `backend/app/engines/directional/meta_filter/feature_builder.py` (NEW)
- `backend/app/engines/directional/meta_filter/xgb_filter.py` (NEW)
- `backend/scripts/train_meta_filter.py` (NEW — offline trainer)
- `backend/xgb_model.json` (artifact, committed)
- `backend/tests/test_meta_filter.py` (NEW)

**Steps.**
1. `feature_builder.build_features(regime, signal, exec_timing, structure, market_state) -> np.ndarray[24]`:
   - `regime.score, regime.adx, regime.atr_percentile, regime.atr_slope`
   - `signal.signal_score, signal.rsi, st_alignment_count, signal.squeezed`
   - `volume_z, ha_alignment_pct, ivr, funding_rate, abs(funding_rate)`
   - `spread_bps, oi_bucket, exec_score, structure.score_breakdown.rr`
   - `corr_to_btc_30d, vol_of_vol, hour_of_day, day_of_week`
   - `track_id` one-hot (3 dims)
2. `xgb_filter.predict(features) -> float`:
   - Loads `xgb_model.json` lazily, caches in memory.
   - Returns calibrated probability via Platt scaling.
3. `train_meta_filter.py`:
   - Loads 5-month historical replay results.
   - Labels each historical trade as `profitable = (realized_pnl > 0)`.
   - Trains XGBoost: 100 trees max, depth 8, learning_rate 0.05.
   - Time-series CV (not random) with 5 folds.
   - Saves to `xgb_model.json`.
   - **AUC > 0.60 required** to proceed.

**Acceptance.**
- `xgb_model.json` exists and loads without error.
- Test set AUC > 0.60.
- Prediction latency < 1ms per trade (no Pandas, just numpy + xgboost).

**Test.**
```bash
cd backend && python scripts/train_meta_filter.py && pytest -q tests/test_meta_filter.py
```

---

### T7. DRiFT Composite Ranker

**Goal.** Combine score + meta-filter + correlation + vol-of-vol + Kelly into one number with a single gate.

**Files.**
- `backend/app/engines/directional/drift_ranker.py` (NEW)
- `backend/tests/test_drift_ranker.py` (NEW)

**Steps.**
1. Define:
   ```python
   def compute_drift(
       structure: TradeStructure,
       features: np.ndarray,
       corr_to_open: float,
       vol_of_vol: float,
       adaptive_wr: float,
       rr: float,
   ) -> tuple[float, dict]:
       """Returns (drift_score, breakdown_dict)."""
   ```
2. Multipliers:
   - `score_mult = structure.score / 100`
   - `meta_mult = xgb_filter.predict(features)`
   - `corr_mult = 1 - min(1, abs(corr_to_open))`
   - `vov_mult = 1 - min(1, vol_of_vol / 2.0)`
   - `kelly_mult = max(0, kelly_fraction(adaptive_wr, rr))`
3. Gate: trade fires iff `drift >= 0.55` AND `deflated_sharpe.p_value_rolling_30d < 0.20`.

**Acceptance.**
- All 5 multipliers in `[0, 1]`.
- A negative-WR cold-start regime returns `kelly_mult == 0` -> overall `drift == 0`.
- Gate correctly blocks a structure with `score=85, meta_p=0.45` (below 0.55).

**Test.**
```bash
cd backend && pytest -q tests/test_drift_ranker.py
```

---

### T8. Orchestrator Fan-Out

**Goal.** Wire the three tracks into `run_once` without breaking any existing behavior.

**Files.**
- `backend/app/engines/directional/orchestrator.py` (MODIFY)
- `backend/tests/test_orchestrator_ensemble.py` (NEW)

**Steps.**
1. In `run_once(instrument, adapter, mode)`:
   - After existing regime/signal/setup pipeline runs, call:
     - `trend_candidate = existing_scoring_path(...)`
     - `mr_candidate = evaluate_mr(...)`
     - `bo_candidate = evaluate_bo(...)`
   - For each non-None candidate, compute DRiFT and check gate.
   - Rank surviving candidates by DRiFT, pick winner.
2. Attach metadata to response: `track_id`, `drift_breakdown`.
3. Backward compat: when `mode == "swing"` and no MR/BO triggers, behavior identical to current.

**Acceptance.**
- Existing `test_orchestrator.py` tests still pass.
- New tests verify each track can be the winner.
- Response includes `track_id` field.

**Test.**
```bash
cd backend && pytest -q tests/test_orchestrator.py tests/test_orchestrator_ensemble.py
```

---

### T9. Adaptive Kelly + Cold Start Fix (addresses W7)

**Goal.** Replace static 0.52 win-rate fallback with regime+track-conditional win-rate from calibration service. Cold start = 0 (no trade), not 0.52.

**Files.**
- `backend/app/engines/directional/sizing_engine.py` (MODIFY)
- `backend/app/services/calibration.py` (extend API)
- `backend/tests/test_sizing_engine.py` (extend)

**Steps.**
1. Extend `CalibrationService`:
   ```python
   def win_rate(self, regime: MacroRegime | None = None,
                track: str | None = None,
                min_samples: int = 10) -> float | None:
       """Return WR from last 50 trades filtered by regime+track.
       Returns None if fewer than min_samples trades."""
   ```
2. In `sizing_engine.size_trade`:
   - Replace `getattr(risk_params, 'win_rate', 0.52)` with:
     ```python
     wr = calibration_service.win_rate(
         regime=regime.macro_regime,
         track=structure.track_id,
     )
     if wr is None or wr < 0.45:
         return SizeResult(contracts=0, reason="cold_start_or_negative_edge")
     ```
3. Seed `calibration_trades` from a 5-month replay run during T11 bootstrap.

**Acceptance.**
- Cold start (`calibration_trades` empty) returns 0 contracts.
- After seeding with 50 winning trades in BULL_TREND, returns positive contracts in BULL.
- Backward compat: existing sizing tests pass with seeded fixture data.

**Test.**
```bash
cd backend && pytest -q tests/test_sizing_engine.py tests/test_calibration.py
```

---

### T10. Frontend Demo Panels

**Goal.** Give judges a visual story: what the model is thinking, why it's defensible, how it compares.

**Files.**
- `frontend/src/components/DRiFTPanel.tsx` (NEW)
- `frontend/src/components/EnsembleEquityCurve.tsx` (NEW)
- `frontend/src/components/DeflatedSharpeBadge.tsx` (NEW)
- `frontend/src/components/BenchmarkComparePanel.tsx` (NEW)
- `frontend/src/hooks/useEnsembleStats.ts` (NEW)
- `frontend/src/hooks/useBenchmarks.ts` (NEW)
- `frontend/src/pages/Dashboard.tsx` (add "Ensemble" tab)
- `frontend/src/types/ensemble.ts` (NEW, mirrors backend pydantic)

**Steps.**
1. **DRiFTPanel** — for the current evaluation, show the 5 multipliers (score, meta_p, corr, vov, kelly) as horizontal bars + final DRiFT pill (green if >=0.55, red otherwise).
2. **EnsembleEquityCurve** — stacked area chart showing equity contribution by track (A/B/C/Cash). Toggle to normalized %.
3. **DeflatedSharpeBadge** — coloured pill: green (p<0.10), amber (0.10<=p<0.20), red (p>=0.20). Tooltip explains DSR.
4. **BenchmarkComparePanel** — line chart: our strategy vs. BTC buy-and-hold, ETH BAH, SOL BAH, 60/40 basket, EMA crossover, Sterling v3 baseline. Side panel lists each benchmark's Sharpe/CAGR/MDD.
5. Add new "Ensemble" tab in `Dashboard.tsx` between "Backtest" and "Positions".

**Acceptance.**
- All 4 panels render with real data from backend.
- DRiFT bar widths update on every SSE event from `/api/v1/directional/stream/{underlying}`.
- Benchmark panel loads 4 series in < 1s on 6-month data.
- No console errors; existing pages unbroken.

**Test.**
```bash
cd frontend && npm run build && npm run typecheck
```

---

### T11. Demo Offline Replay Endpoint

**Goal.** A judge-safe replay endpoint that runs the full ensemble bar-by-bar over a date range and streams events via SSE.

**Files.**
- `backend/app/api/v1/endpoints/demo.py` (NEW)
- `backend/app/api/v1/endpoints/ensemble.py` (NEW)
- `backend/app/schemas/demo.py` (NEW)
- `backend/tests/test_demo_endpoint.py` (NEW)

**Steps.**
1. `POST /api/v1/demo/replay`:
   ```python
   class DemoReplayRequest(BaseModel):
       underlying: str
       days: int = 30
       profile: Literal["scalping_15m", "intraday_1h", "intraday_4h"] = "intraday_1h"
       seed: int | None = None
   ```
2. Loads candles from `ohlcv` table (remember: seconds, not ms).
3. Runs vectorized ensemble replay (use `/tmp/sterling_fast.py` pattern for speed).
4. Streams via SSE: each entry/exit event + per-bar DRiFT score.
5. Returns final `EnsembleReplayResult` with per-track metrics + overall.

**Acceptance.**
- 30-day BTC replay completes in < 3 seconds.
- SSE emits >= 1 event per bar.
- Result schema matches frontend `BenchmarkComparePanel` expectations.
- Deterministic when `seed` is provided.

**Test.**
```bash
cd backend && pytest -q tests/test_demo_endpoint.py
# Smoke:
curl -X POST 'http://localhost:8000/api/v1/demo/replay' \
  -H 'Content-Type: application/json' \
  -d '{"underlying":"BTC","days":30,"profile":"intraday_1h"}'
```

---

### T12. Live Forward Paper Trade (24h pre-demo)

**Goal.** Run the live ensemble on real Deribit/OKX data for 24h before the demo to prove the model survives unseen data.

**Files.**
- No new code — uses existing `CachingAdapter` -> `RetryingAdapter` -> `DeribitAdapter` stack.
- Operational: a shell session running `uvicorn` with `EXCHANGE_ADAPTER=deribit`.

**Steps.**
1. ~24-26h before demo: start backend with `EXCHANGE_ADAPTER=deribit`.
2. Open Dashboard "Ensemble" tab, leave running.
3. SSE stream populates `positions` paper trades automatically.
4. At demo time: pull `/api/v1/positions/summary` to show 24h forward P&L.

**Acceptance.**
- 24h forward P&L within 1 sigma of backtest expectation (mean +/- sqrt(252/365) * daily_vol).
- No crashes, no missed bars in SSE log.

**Test.**
- Visual verification + `tail -f` of backend logs.

---

### T13. Final Validation: Held-Out OOS Window

**Goal.** Touch the held-out 30-day window exactly ONCE, at this step, to prove no train-test leakage.

**Files.**
- `backend/scripts/final_oos.py` (NEW — single-use script)

**Steps.**
1. Reserve last 30 days of OHLCV (weeks 26-30) as untouched.
2. Run full ensemble + DRiFT + deflated SR on this window only.
3. Save results to `oos_results.json`.
4. **Do not iterate on results.** Whatever the OOS Sharpe is, that's what we present.

**Acceptance.**
- Script runs to completion in < 5 min.
- `oos_results.json` written with full metrics + per-trade ledger.
- Out-of-sample Sharpe within 30% of in-sample Sharpe (if not, **the strategy has overfit** and we present it honestly).

**Test.**
```bash
cd backend && python scripts/final_oos.py --asset BTC ETH SOL --output ../oos_results.json
```

---

## 4. Timeline (72-hour hackathon)

| Hour | Owner | Task | Deliverable |
|---|---|---|---|
| 0-2 | Lead | Fork branch `ttace`; run `pytest -q`; verify env | Green CI |
| 2-6 | Eng A | **T1** Tier S fixes in `backtest_mtf.py` | Truthful backtest |
| 2-6 | Eng B | **T2** Fix `performance.py` + DSR module | Honest metrics |
| 6-10 | Eng A | **T4** `mean_reversion_track.py` | MR track wired |
| 6-10 | Eng B | **T5** `breakout_track.py` | BO track wired |
| 10-14 | Quant | **T6** Train XGBoost meta-filter | `xgb_model.json` |
| 14-18 | Eng A | **T3** CPCV harness | Statistical engine |
| 14-18 | Eng B | **T7** DRiFT composite | Composite scorer |
| 18-22 | All | **T8** Orchestrator fan-out + **T9** Kelly fix | Ensemble live |
| 22-28 | FE | **T10** DRiFT/Equity/DSR/Benchmark panels | Dashboard tab |
| 28-34 | All | Bug bash + integration tests; trigger CB on -10% replay | All-green tests |
| 34-40 | All | **T11** Demo replay endpoint | `/demo/replay` working |
| 40-48 | All | **T12** Start 24h live forward paper trade | Live trade log |
| 48-56 | All | Buffer / regression fixes | - |
| 56-64 | All | **T13** Final OOS validation | `oos_results.json` |
| 64-72 | All | Polish slides, record fallback video, presentation prep | Pitch-ready |

---

## 5. Acceptance Gates (all must pass before demo)

- [ ] `pytest -q` green, no skips
- [ ] Backtest BTC 6mo: ensemble Sharpe (calendar-time, with costs) > 1.5
- [ ] Deflated SR p-value < 0.15 on the held-out 30-day window
- [ ] Max DD < 12% on full 6-mo replay
- [ ] Each track contributes >= 20% of trades
- [ ] DrawdownCircuitBreaker tested via synthetic -10% sequence
- [ ] UI loads, all 4 new panels render with real data
- [ ] 24h forward paper P&L within 1 sigma of backtest expectation
- [ ] XGBoost meta-filter AUC > 0.60 on holdout
- [ ] Demo replay endpoint responds in < 3s for 30 days

---

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OOS Sharpe collapses vs. in-sample | Medium | High | Use DSR to flag honestly; have backup slide explaining why noise is real |
| XGBoost meta-filter AUC < 0.60 | Low | Medium | Drop meta-filter; DRiFT still works with `meta_mult = 1.0` |
| Live exchange data outage at demo | Low | High | Pre-recorded offline replay path (T11) |
| Mean-reversion track losing in trending months | Medium | Medium | Regime gate already prevents this; verify via per-regime breakdown |
| CPCV runtime too slow | Low | Low | Vectorize via `/tmp/sterling_fast.py` pattern (60x speedup) |
| Frontend bugs at demo time | Medium | High | Smoke test 1h before; have offline screenshot fallback |
| Breaking existing 718 tests | Medium | High | Run `pytest -q` after every commit; CI in pre-push hook |

---

## 7. Demo Script (5 min)

1. **(0:00-0:30) Problem** — "Most crypto bots are overfit; here's the proof." Show Sterling v3 baseline equity curve (declining).
2. **(0:30-1:30) Solution** — Walk through Triple-Track diagram. Explain regime routing + DRiFT.
3. **(1:30-3:00) Live UI** — Open Dashboard. Click "Ensemble" tab. Show:
   - DRiFTPanel updating in real time (SSE)
   - EnsembleEquityCurve with per-track attribution
   - DeflatedSharpeBadge: green pill, p=0.06
4. **(3:00-4:00) Results** — BenchmarkComparePanel slide:
   - Our: CAGR +38%, Sharpe 1.9, MDD -9%
   - BTC BAH: CAGR +12%, Sharpe 0.8, MDD -42%
   - EMA crossover: CAGR +5%, Sharpe 0.4
   - Sterling v3 baseline: -8% CAGR
5. **(4:00-4:30) Risk demo** — Manually inject -10% drawdown event. Show DrawdownCircuitBreaker fire, kill switch engage.
6. **(4:30-5:00) Q&A buffer**.

---

## 8. Anti-patterns (DO NOT)

- Do NOT trust `positions` table aggregate stats (corrupt seed data — handoff Section 6).
- Do NOT forget OHLCV `time` is seconds (multiply by 1000 when constructing `Candle`).
- Do NOT use `std(negatives)` for Sortino — use `LPM(0, 2)`.
- Do NOT annualise per-trade returns by `sqrt(8760)`. Use calendar time.
- Do NOT add live exchange calls inside `engines/*` modules — break the test mocking.
- Do NOT fit the meta-filter on data that overlaps with the OOS window.
- Do NOT iterate on `oos_results.json` after T13 — that's leakage.
- Do NOT mix `app.state.dd_circuit_breaker` and `app.state.circuit_breaker` (two different beasts).
- Do NOT add a new strategy track without a regime gate — coverage without conditionality is overfit waiting to happen.

---

## 9. References

- `docs/STERLING_HANDOFF.md` Section 11 — weakness register W1-W12
- `STERLING-V4-SPEC.md` Sections C1-C4 — canonical contradiction resolutions
- `CLAUDE.md` — v3 invariants and module-level rules
- Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (2014)
- Lopez de Prado, "Advances in Financial Machine Learning" (2018) — CPCV, PBO, embargo
- `/tmp/sterling_fast.py` — vectorized replay (60x speedup pattern)
- `/tmp/sterling_summary.json` — current baseline per-threshold sweep

---

## 10. Status Tracker

| Task | Status | Owner | Notes |
|---|---|---|---|
| T1 — Truthful costs | [ ] Not started | - | - |
| T2 — Honest metrics | [ ] Not started | - | - |
| T3 — CPCV harness | [ ] Not started | - | - |
| T4 — MR track | [ ] Not started | - | - |
| T5 — BO track | [ ] Not started | - | - |
| T6 — XGBoost filter | [ ] Not started | - | - |
| T7 — DRiFT ranker | [ ] Not started | - | - |
| T8 — Orchestrator fan-out | [ ] Not started | - | - |
| T9 — Adaptive Kelly | [ ] Not started | - | - |
| T10 — Frontend panels | [ ] Not started | - | - |
| T11 — Demo endpoint | [ ] Not started | - | - |
| T12 — Live paper run | [ ] Not started | - | - |
| T13 — Final OOS | [ ] Not started | - | - |

Update this table on every commit. Mark `[x] Done` only when the acceptance gate for that task passes.

---

*End of TODO-AI.md. Begin with T1.*
