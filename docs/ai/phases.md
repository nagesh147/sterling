# Sterling — Phase Timeline

Factual, chronological record of major shipped phases in the Sterling codebase. Each entry states what shipped and when, with branch/commit references where recorded in source. Rationale, trade-off discussion, and abandoned approaches are intentionally excluded — see the project memory notes for that context.

---

## May 2026

### 2026-05-03 — Sterling v2 Engine Redesign
- New indicators: `adx`, `ema_dual`, `atr_percentile`, `keltner`, `bollinger_bands`, `rsi`, `ha_body_bull`.
- 4-regime engine: `BULL_TREND` / `BEAR_TREND` / `RANGING` / `VOLATILE` / `IDLE`.
- Weighted-confluence signal engine.
- New scoring system: absolute 0–100 points.
- 25% fractional-Kelly position sizing.
- Funding-rate veto (>2.5%/8h).
- 673 tests passing.

### 2026-05-09 — Sterling v3 Production Upgrade
- New `app/engines/analytics/`: performance, walk_forward, sensitivity, correlation.
- New `app/engines/risk/`: slippage, greeks_budget, circuit_breaker (`DrawdownCircuitBreaker`).
- New `services/calibration.py`: adaptive win-rate + IVR percentile, persisted to SQLite.
- New DB tables: `wf_results`, `parameter_sensitivity`, `calibration_state`, `calibration_trades`, `equity_snapshots`.
- New position columns: `greeks_json`, `notional`, `slippage_bps`.
- New frontend panels: `WalkForwardPanel`, `SensitivityPanel`, `CorrelationHeatmap`, `GreeksBudgetGauge`, `DrawdownBreakerBadge`, `CalibrationPanel`.
- +33 tests.

### 2026-05-17 — Multi-Timeframe (MTF) Backtest System
- `backend/app/engines/backtest/backtest_mtf.py` with 3 timeframe profiles: `scalping_15m`, `intraday_1h`, `intraday_4h`.
- New endpoint: `POST /backtest/mtf`.
- `BacktestPanel.tsx` MTF comparison UI.
- 8 commits on `main`, 8 new tests.

### 2026-05-24 — Strategy Reset
- Branch `strategy-reset` created off `strategy-v2`.
- All strategy decision logic in `app/engines/directional/`, `app/engines/hybrid_vcp/`, `app/engines/ml/` deleted/stubbed to neutral (regime → IDLE, signal → no-trade, sizing fails closed).
- Indicators/backtest/analytics/risk infrastructure retained.
- 30 strategy test files and 7 scripts deleted.

### 2026-05-25 — Triple-ST Strategy Slot Rewritten (twice)
- First pass: SMA/EMA + RSI/ADX momentum rule (commit `ce20cde`).
- Replaced same day with a validated daily RSI(2) mean-reversion engine (commit `18094b1`): long when RSI(2)<10 inside an uptrend (close > SMA200), exit on RSI(2)>70, ATR(14)×4 stop.

### 2026-05-27 — Scalping Optimizer & Timeframe Selection
- Opt-in OOS-robust optimizer added: `engines/scalping/optimizer.py`.
- New endpoints: `POST` / `GET /api/v1/scalping/optimize`.
- Selectable macro/execution timeframes; default set to 4h macro / 30m execution.

### 2026-05-28 — Scalping Backtest Rewrite
- `/scalping/backtest` endpoint rewritten.
- New `app/engines/scalping/backtest.py`: real bar-by-bar SL/TP replay, real costs, sample-size/regime-coverage/IS-OOS-split validation signals.
- 12 new tests.

### 2026-05-29 — Derivatives Selector: Phase 0–1
- **Phase 0** (commit `d3d9135`): `paper_store` futures-vs-options PnL split fix, `OrderRouter` fractional-contract fix, `GreeksBudgetChecker` as a hard gate, `portfolio_greeks_aggregator.py`, isolated-margin ordering, 5-Greek BSM, `force_close_minutes_before_expiry`. 36 tests.
- **Phase 1** (commit `1584de6`): Greeks enrichment, `options_monitor.py`, DTE force-close/microstructure veto wired into the background monitor. 32 tests.

### 2026-05-30 — Derivatives Selector: Phases 2–7, Comprehensive Backtest, Edge Package
- **Phases 2–6** (commits `a36d296`, `0f12dd3`, `8130280`, `29e9e77`, `fd21a17`): selector engine, `/api/v1/derivatives/` endpoints, frontend candidate tables/panel, per-strategy wiring shipped behind `profile.enabled=False`, full test suite + docs (953 backend tests total).
- **Phase 7** (same day): dual Futures/Options candidate tables, split into `FuturesCandidatesTable` + `OptionsCandidatesTable`; background scanner (`derivatives_scanner.py`); `/scan` endpoint; `decide_both()` with independent freeze tokens; `auto_execute_futures` / `auto_execute_options` profile flags. 14 tests.
- Same day, separately: `comprehensive_backtest.py` 270-config matrix run (3 symbols × 6 timeframes × 5 strategies × 3 profiles); winner BTC 4h MA-crossover Intraday (Sharpe 1.83, PF 1.29, +95.3% net). Only 10/270 configs net-profitable.
- `app/engines/edge/` package built (`strategies.py`, `registry.py`, `signals.py`), wiring the edge feed into candidate tables. `SourceBadge` component added.

### 2026-05-31 — Scalping Loss Investigation & Robustness Tooling
- `realistic_stop_fill` helper added, capping TSL slippage.
- `capital_at_risk_pct` fixed to a stop-based calculation in two sites.
- `macro_trend_filter` default flipped False → True.
- Later same day: 13.5-month before/after backtest run; re-entry cooldown reverted to 0; `evaluate_breakout` disabled by default; `price_action` disabled in live config only.
- Also same day: CPCV + Monte-Carlo robustness scan built (`analytics/cpcv.py`, `analytics/monte_carlo.py`, `backend/robustness_scan.py`); strategy-catalog endpoint/UI shipped; breakout strategy rebuilt to retest-entry (commit `519dc49`).

---

## June 2026

### 2026-06-01 — Contract-Value Lot Sizing
- Branch `feat/realtime-iv-stream`: `SizedTrade.contracts` / `.qty` split, `DeltaIndiaAdapter.get_contract_value`.
- Scalping auto-execution loop restored.
- Same day: `backend/deriv_fut_opt_metrics.py` futures-vs-options overlay backtest built and run (180 configs).

### 2026-06-03 — Capital-at-Risk Fix, Sterling-Only Consolidation, SterlingV2 Toggle Redesign
- Capital-at-risk display fix (branch `fix/capital-at-risk-pct`, commit `d5cc381`) + backfill script for 122 scalping positions.
- Sterling-only consolidation (branch `feat/sterling-only` → `main` commit `9f5879a`): STAT ARB, RSI MEAN-REV/`triple_st`, SIGNALS, and CALIBRATION tabs removed; app reduced to STERLING ENGINE / POSITIONS / BACKTEST. All repo branches fast-forwarded to `9f5879a`.
- SterlingV2 toggle-isolated redesign built (branch `redesignV2`): leak-free harness; levers L1/L4/L5 kept, L2/L3 rejected; Stack B (multi-book) rejected.

### 2026-06-04 — Engine-Specific Derivatives Tables & Modular Architecture Hardening
- Engine-specific derivatives tables fix (branch `redesignV2`): per-engine scoping (sterling/grok/edge) for candidate tables and position attribution.
- Modular architecture hardening program started (branch `feat/modular-architecture-hardening` off `main` @ `91f583c`):
  - Phases 0, 1, 2, 3, 4, 6 completed: `TradingExchangeAdapter` ABC, `app/domain`, `registry.json`, observability/metrics, event bus + 8 agents, `RiskEngine` shadow-mode, 15 canonical docs.
  - Phases 5a/5b/5c (SQLAlchemy scaffolding + dual-write) completed later on the same branch.

### 2026-06-06 — Brutal Audit & Backtest-Honesty Fixes
- Audit of Sterling + Grok conducted: documented Grok/directional as 15/17 stubbed modules; `STERLING-V4-SPEC.md` documented as fiction relative to actual code.
- `comprehensive_backtest.py::simulate()` infinite-loop bug found and fixed; `hodl_benchmark` / `beats_buy_and_hold` added.
- Separately: Sterling engine backtest-honesty review — 5 fixes shipped (branch `feat/backtest-lookahead-fix` @ `f141912`):
  1. Cross-TF lookahead fix (`timing.py`).
  2. Realistic next-bar-open fills.
  3. Options cost realism.
  4. Live repaint guard.
  5. Opt-in structural-risk routing.
  - 11 new tests.

### 2026-06-07 — DSR Scaling Fix & Acceptance Filter
- DSR scaling bug found and fixed in `edge/robustness.py` (branch `feat/dsr-deflation-gate`, commit `9ca8b80`).
- Acceptance filter (`min_dsr`, `require_beats_hold`) wired into the live `EdgeGate`, defaulting to admit 0 combos.
- `robustness_scan.py` dead-code key mismatch fixed.
- Mean-reversion sleeve researched via anchored walk-forward; disabled scaffold shipped (`app/engines/edge/sleeves/mean_reversion.py`, `QUALIFIED=False`).

### 2026-06-09 — Regime-Book Rework
- Built on branch `feat/dsr-deflation-gate` (commits `55b28d5` → `e617caf`): `study/regime_book.py`, 3-symbol pooling, ADX+SMA regime gate (momentum/MR/short). 15 tests.
- Same session (commit `2042c2a`): vol-target sizing, sleeve-specific exits, CONVICTION concentration filter added.

### 2026-06-10 — Regime-Book: Breadth Test, Paper Trader, Operational Safety
- Breadth test across 24 coins (commit `5e465f8`, `study/ohlcv_pipeline.py`).
- Standalone paper trader built (commit `9c598e7`, `study/paper_trader.py`).
- Repaint-bug fix + hardening (commit `b8d79a5`).
- Operational safety layer added (commit `d0548cc`, `study/paper_safety.py`): kill-switch, run_lock, exactly-once-per-bar.
- Funding sleeve built and tested (`study/funding_pipeline.py`, `study/funding_sleeve.py`).
- Paper dashboard Phase-2 Slice 1 shipped (`app/api/v1/endpoints/paper.py`, `PaperResearchTab.tsx`).
- Full-cycle stress test run and committed (commit `14e3718`, `study/fullcycle_stress.py`), extending data back to 2020.

### 2026-06-11 — Directional Engine De-Stubbing & Cross-Market Probe
- `signal_engine` / `regime_engine` de-stubbed in `app/engines/directional/`: new `indicators.py` with real Wilder ADX/RSI/SMA-slope. 7 tests.
- Empty-candidate-tables root cause traced and fixed across 3 layers (commit `5067ac7`, plus 3 more downstream gates same day).
- Cross-market probe on Indian indices (NIFTY/BANKNIFTY) run and found negative.

### 2026-06-12 — Zerodha Kite Connect Integration (Initial)
- Branch `zerodhaKite`, commit `fd15eb3`: `backend/app/services/exchanges/kite/` package.
- 42 routes under `/api/v1/kite`.
- New KITE UI tab.
- Multi-tenant per-user encrypted credentials.

### 2026-06-13 — Kite API-Parity Pass
- 61 routes total (up from 42): session refresh, auctions, CDSL holdings authorisation, MF SIP lifecycle, MF instrument search, native Alerts API, order postbacks, live WS order updates.
- 92 Kite tests green.

### 2026-06-14 — Kite Trading-Mode UI & Order-Window QA
- Kite OrderWindow visual-QA methodology established (headless vite + gstack); flex min-width overflow bug fixed.
- Kite Connect page gained a Trading Mode panel (PAPER/LIVE + MANUAL/AUTO toggles).
- Second PAPER/LIVE switch added to `TripleSupertrendPane`.
- Kite order-notification toasts added.

### 2026-06-15 — Kite Strike Selection & Derivatives Scan Modes
- Auto-AMO retry implemented for Kite orders.
- Kite Triple-SuperTrend engine: OTM1/OTM2 strikes added (44 tests).
- Derivatives scan-source mode added (`scan_source`: spot/derivatives/both, `deriv_universe`) (52 tests).
- Refinement pass: universal auto-exec, short-weekly handling, granular universe selection.
- Live-testing fixes: positions P&L overlay, scan-source re-scan trigger, instrument-resolution (BSE index name-field quirks, NSE-wins dedup), liveness model (`is_active` / `is_fresh`), rate-limit backoff. 61 tests total.

### 2026-06-19 — Kite Performance, Reliability & Motion Layer
- Branch `KiteEngine`, client-cache perf fix: `acquire_client` / `release_client` warm-client pattern replacing per-request `build_client()`; frontend search debounce.
- Round 2: scanner O(1) index, `implied_vol` Newton-Raphson, `.kv-rows` content-visibility virtualization, overlay scrollbars, Telegram Kite bot (`services/notifications/telegram_kite.py`).
- Kite `is_active` resurrection bug fixed (`np.all(trail[i:]==want)` liveness check) + parent-row OR-of-legs UI fix.
- Mac Kite motion layer shipped (commit `c9b5607`): lazy-loaded framer-motion, gated behind a footer toggle.

### 2026-06-20 — Kite Real-Money Hardening
- `is_active` follow-up: scan-orchestration filter to drop stopped-out historical rows; frontend live reconciliation (`legHasExited` / `rowIsRunning`).
- Kite real-money hardening (branch `KiteEngine`, 8 workstreams, 129+44 tests): broker GTT stop + tick-monitor exit (`stop_mode`); daily-loss breaker made crypto-only; DB-persisted auto-open guard + reconciliation; premium-at-risk sizing; WS fill tracking; new Backtest tab; PAPER/LIVE header badge; `kite_engine/positions.py` registry.

---

## July 2026

### 2026-07-16 — Kite Sterling Strategy Audit
- Branch `kite-mobile`, 186 tests: spot-mode premium stop; GTT double-sell classification fix; opt-in `exit_aligned_trail`; deep-ITM/spot-OTM retranslated trail; expiry square-off guard; `scan_source` default flipped derivatives → spot; opt-in liquidity/spread/daily-loss/close-time guards.
- Exit-mode sweep run: default flipped `two_red` → `one_red`; `time_stop_bars` (opt-in) added.

### 2026-07-17 — Kite Confluence Scan Mode & Chart Fixes
- Kite scan-source "confluence" mode added (branch `kite-mobile`, commit `78df273`): 4th `scan_source`, 7-column signal table (Entry/SL/TSL/Exit/Target/Chg/LTP).
- Follow-up review fixed 4 findings (commit `25ccefc`): double-SELL race, double-book PnL, unpersisted daily-loss breaker, both-mode column drift.
- 5th finding fixed (commit `3a66ddb`): confluence stale entry premium.
- lightweight-charts SuperTrend whitespace bug diagnosed and fixed (commit `313c547`, `supertrendRuns`).
- Kite chart-state persistence — original per-symbol fix shipped (debounce/zoom/params bugs, page-unload flush).

### 2026-07-18 — Kite Chart-State Persistence Rework & Main-Branch Integration
- Kite chart-state persistence reworked to a single global config blob (commit `260ace2`, pushed): `__global__` KV key, `drawingsBySymbol` map, module-level session cache, GET-error-overwrite guard.
- Kite OI Change / Open Interest tabs added (`OIView.tsx`, same commit).
- Main-branch integration: `sterling-kite-ver5`, `fix-truecourse`, and both `claude/*` branches merged into `main` (commit `0bb059f`), fixing a clean-merge JSX artifact in `SignalImpactCalculator.tsx`. All 7 non-worktree branches unified at `0bb059f` and synced with origin.

---

## Known open items

Items explicitly recorded in the source material as disabled, gated off, or otherwise unresolved as of their entry date:

- **Derivatives Selector per-strategy wiring** (2026-05-30, Phases 2–6): shipped with `profile.enabled=False` — wiring exists but is not turned on per strategy.
- **EdgeGate acceptance filter** (2026-06-07): `min_dsr` / `require_beats_hold` filter is live but defaults to admitting 0 combos — no strategy currently clears the bar.
- **Mean-reversion sleeve** (2026-06-07): scaffold shipped disabled, `QUALIFIED=False` — built but not qualified/enabled.
- **Grok/directional stub coverage** (2026-06-06 audit): 15/17 modules documented as stubbed, and `STERLING-V4-SPEC.md` documented as not reflecting actual implemented code.
