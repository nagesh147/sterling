# Sterling — Engineer Handoff (v3 + MTF, v4 spec in flight)

> **Audience.** A new engineer or quant joining the project who needs to read code, ship changes, and reason about strategy outcomes within their first week.
> **Status as of 2026-05-18.** v3 unified engine in production, MTF backtest landed 2026-05-17, v4 spec written but live OrderRouter NOT yet implemented. Strategy is currently **paper-only**.
> **Companion docs.** `README.md` (user-facing), `STERLING-V4-SPEC.md` (canonical strategy spec & C1–C4 contradiction resolutions). When this doc and code disagree, code wins; when this doc and `STERLING-V4-SPEC.md` disagree on a number, the spec wins and the code is the bug.

---

## 0. TL;DR (read this even if you read nothing else)

- **What Sterling is.** A FastAPI + React platform that watches BTC/ETH/SOL/XRP/NIFTY/BANKNIFTY across 4H/1H/15m, classifies macro regime, generates directional setups, routes each setup to the best instrument (option long, option short, defined-risk spread, or leveraged futures) based on IV Rank, then sizes the trade with fractional Kelly under hard score/spread/OI vetoes. Trades land in a paper-trade store backed by SQLite; live order routing is **not** wired.
- **The one thing newcomers get wrong.** "Score" is overloaded. There are three different scores:
  1. `signal.signal_score` (0–20) — 1H confluence (Supertrends + RSI + BB/KC squeeze + volume + HA).
  2. `regime.score` (0–20) — 4H trend strength (ADX × ATR percentile).
  3. `structure.score` (0–100) — composite ranking of a *specific candidate structure*. This is what the **75 / 85** hard gates compare against.
  - Walk-forward tunes against `signal.signal_score`. Live execution gates on `structure.score`. Mixing them up will burn you.
- **The strategy you'll touch most.** Files under `backend/app/engines/directional/` (regime/signal/setup/scoring/structure/sizing) and `backend/app/engines/backtest/backtest_mtf.py`. Indicators live in `backend/app/engines/indicators/`. Risk gates in `backend/app/engines/risk/`. Adaptive state in `backend/app/services/calibration.py`.
- **The known-bad state.** Latest persisted walk-forward (`wf_results` row 3): **OOS Sharpe -207.72, 0% win rate over 26 windows, 5 trades total**. A fresh 6-month replay across BTC/ETH/SOL on 15m+1H produced PF < 1 for 5/6 configurations. The strategy in its current form does **not** meet elite benchmarks. See § 11 for the playbook out of this.
- **The fastest way to learn the system.** Run `pytest -q` (718 tests, no network), then read `engines/directional/orchestrator.py` top-to-bottom — every other module is reached through it.

---

## 1. Repository layout

```
Sterling/
├── README.md                      user-facing reference (API + strategy summary)
├── STERLING-V4-SPEC.md            canonical strategy spec (C1–C4 contradictions resolved)
├── CLAUDE.md                      AI-collaborator instructions (v3 invariants)
├── AGENTS.md / GEMINI.md / .cursorrules   alt-agent files (same content theme)
├── Makefile                       common dev targets
├── docker-compose.yml             backend + frontend + sqlite volume
├── docs/                          (this folder — keep handoff/spec/runbooks here)
│
├── backend/                       FastAPI + Python 3.12
│   ├── main.py                    app factory, lifespan, adapter stack assembly
│   ├── sterling_paper.db          SQLite (positions, signals, calibration, ohlcv, …)
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── tests/                     718+ tests, all mocked. `pytest -q`.
│   ├── evidence_report.py         CLI evidence dump for an underlying
│   └── app/
│       ├── core/                  config, logging, rate_limit, trading_mode
│       ├── schemas/               Pydantic models (market, directional, execution,
│       │                          risk, instruments, positions, backtest, …)
│       ├── engines/
│       │   ├── indicators/        ema, atr, adx, rsi, supertrend, bollinger,
│       │   │                      keltner, heikin_ashi  — pure numpy, no I/O
│       │   ├── directional/       regime_engine, signal_engine, setup_engine,
│       │   │                      policy_engine, execution_engine,
│       │   │                      option_translation_engine, structure_selector,
│       │   │                      sizing_engine, scoring, monitor_engine,
│       │   │                      contract_health_engine, dynamic_tp,
│       │   │                      orchestrator, mtf, microstructure
│       │   ├── analytics/         walk_forward, performance, sensitivity,
│       │   │                      correlation  — v3, pure functions
│       │   ├── risk/              circuit_breaker, slippage, greeks_budget,
│       │   │                      cooldown, microstructure_veto, vol_of_vol_gate,
│       │   │                      regime_adaptive_sizer  — v3 stateful singletons
│       │   └── backtest/          backtest_engine, backtest_mtf, sweep, bs_pricing
│       ├── services/              cache, retry, db, paper_store, calibration,
│       │                          alert_service/store, eval_history, snapshot_cache,
│       │                          arrow_store, ohlcv_store, pnl_history, fees,
│       │                          live_safety, exchanges/, execution/, notifications/
│       └── api/v1/endpoints/      health, instruments, directional, positions, config,
│                                  backtest, exchanges, account, alerts, options,
│                                  webhooks, stats, session, analytics, risk_dashboard,
│                                  trading, trading_mode, candles, ohlcv
│
└── frontend/                      React 19 + TS 5.9 + Vite 8
    └── src/
        ├── types/                 mirrors backend pydantic schemas
        ├── utils/api.ts           thin axios wrapper + fmt helpers
        ├── store/                 Zustand 5 (selected underlying, mode)
        ├── hooks/                 30 React Query hooks, one per resource
        ├── components/            33 UI components (panels, badges, charts)
        └── pages/                 Dashboard.tsx, Terminal.tsx (pro),
                                   SimpleTerminal.tsx (beginner)
```

There is also a code-review-graph database at `.code-review-graph/` — 1,534 nodes / 9,322 edges, used by the `code-review-graph` MCP server. Prefer it over Grep when exploring (`CLAUDE.md` rule).

---

## 2. The 4-layer strategy pipeline

Every evaluation funnels through `orchestrator.run_once(instrument, adapter)` (see `engines/directional/orchestrator.py`). It calls each layer in order. Any layer can short-circuit with `state=FILTERED`.

```
              ┌────────────┐
   4H candles │   Layer 1  │   regime_engine.compute_regime()
              │   MACRO    │ → RegimeResult{macro_regime, score 0-20,
              └────────────┘    adx, atr_percentile, atr_slope, ema21/55}
                    │
              ┌─────▼──────┐
   1H candles │   Layer 2  │   signal_engine.compute_signal()
              │   SIGNAL   │ → SignalResult{trend, signal_score 0-20,
              └────────────┘    green/red_arrow, rsi, squeezed, st_trends}
                    │
              ┌─────▼──────┐
              │   Layer 2b │   setup_engine.evaluate_setup(regime, signal)
              │   SETUP    │ → SetupResult{state, direction, reason}
              └────────────┘    state ∈ {IDLE, EARLY_SETUP_ACTIVE,
                    │            CONFIRMED_SETUP_ACTIVE, FILTERED}
              ┌─────▼──────┐
              │   Layer 3  │   policy_engine.apply_policy(direction, IVR)
              │   POLICY   │ → PolicyResult{ivr_band, allowed_structures,
              └────────────┘    avoid_long_premium}
                    │
              ┌─────▼──────┐
  15m candles │   Layer 4  │   execution_engine.assess_timing()
              │   TIMING   │ → ExecTimingResult{mode, confidence, exec_score 0-15}
              └────────────┘
                    │
              ┌─────▼──────┐
              │   Build    │   option_translation_engine → calls/puts
              │   STRUCT.  │   structure_selector.build_structures() → list of
              └────────────┘   TradeStructure (naked, spread, futures)
                    │
              ┌─────▼──────┐
              │   SCORE    │   scoring.rank_structures()
              │  +HARD VET │   for each candidate, run
              └────────────┘   _check_hard_vetoes → _score_macro_regime →
                    │         _score_signal_v2 → _score_exec_timing_v2 →
                    │         _score_contract_health_v2 → _score_dte_v2 →
                    │         _score_rr_v2 → _score_session_bonus
                    │         → total 0..100 (clipped) + score_breakdown dict
                    │         Then passes_score_threshold(75 / 85) drops failures.
                    │
              ┌─────▼──────┐
              │   SIZE     │   sizing_engine.size_trade()
              └────────────┘   25% fractional Kelly × min(struct cap, port cap,
                    │         max_position_pct, scalp ceiling, corr penalty,
                    │         regime-adaptive multiplier)
                    │
              ┌─────▼──────┐
              │  COMPARE   │   if best.score > score_no_trade(regime, signal, policy)
              │  TO        │     → state ENTRY_ARMED_*, recommendation = struct_type
              │ NO_TRADE   │   else                 → state FILTERED, no_trade
              └────────────┘
```

### Layer 1 — Macro regime (`regime_engine.py`, 4H candles)

| Output | Source |
|---|---|
| `macro_regime` enum | `BULL_TREND` / `BEAR_TREND` / `RANGING` / `VOLATILE` / `IDLE` |
| `score` 0-20 | `min(ADX/40, 1)*12 + min(ATR_pct/80, 1)*8` for trends; 0 for ranging/idle; 8 fixed for volatile |
| `adx`, `atr_percentile`, `atr_slope` | exposed for UI strips |

**IDLE detection** is the single biggest signal sink — it consumes ~38% of bars in the 6-month replay:
- `atr_percentile < 30` on two consecutive bars, OR
- `atr_slope < 0` AND `atr_percentile < 35`

**ADX thresholds** (lower than FX/equity convention because crypto trends earlier):
- `< 15` → RANGING
- `15–20` → still RANGING (partial signal allowed via setup_engine promotion)
- `≥ 20` → trending (full alignment admitted)

**Mode `macro_filter="off"`** (scalping mode) bypasses ADX/ATR gating — just uses EMA21 direction.

### Layer 2 — Signal confluence (`signal_engine.py`, 1H candles)

Three Supertrends (configurable per profile), Heikin-Ashi alignment, BB/KC squeeze, RSI gate, volume spike, HA/Real divergence. Weighted sum (max 20, clipped) is the **`signal_score`**.

| Component | Weight | Pass condition |
|---|---|---|
| Supertrend flip | 3 | Current bar transitions to N-of-3 same direction |
| RSI gate | 2 | Long: 42 < RSI < 70 · Short: 30 < RSI < 57 |
| RSI momentum bonus | 1 | Long: 55–68 · Short: 32–45 |
| BB+KC squeeze breakout | 4 | Squeezed on prior bar + breakout this bar |
| Volume spike | 4 | `volume > 1.5 × median(last 20)` |
| HA body aligned | 4 | HA close direction matches trend |
| HA/Real divergence < 0.3% | 2 | Real-vs-HA close discrepancy below threshold |
| **Total** | **20** | |

A **staleness penalty** subtracts up to 3 pts from `earned` when the same alignment has held for `bars_active // 5` periods (caps at 3) — prevents loading into late-stage trends.

Strength buckets:
- `signal_score / 20 ≥ 0.75` → **STRONG** (≥ 15)
- `≥ 0.35` → **SIGNAL** (≥ 7)
- below → **NONE**

### Layer 2b — Setup state machine (`setup_engine.py`)

Maps `(macro_regime, signal.trend, signal.signal_score, green/red_count)` → setup state.

- `IDLE` / `CHOPPY` regime → **FILTERED** (hard veto)
- Bull/Bear trending + full ST alignment + arrow → **CONFIRMED_SETUP_ACTIVE**
- Trending + 2/3 ST aligned (no arrow yet) → **EARLY_SETUP_ACTIVE**
- Ranging + all-aligned + `signal_score ≥ 16` → **CONFIRMED_SETUP_ACTIVE** (promotion)
- Volatile + all-aligned + `signal_score ≥ 16` → **CONFIRMED_SETUP_ACTIVE**
- Anything else → **EARLY** or **FILTERED**

The ranging/volatile promotion is the only way the strategy trades in the ~25% of bars that aren't trending; without it, signal frequency drops below break-even.

### Layer 3 — Policy & IVR routing (`policy_engine.py`)

`apply_policy(direction, instrument, ivr)` returns `PolicyResult.ivr_band` and an `allowed_structures` set. See `STERLING-V4-SPEC.md` § C2 for the canonical IVR table:

| IVR | Band | Allowed structures |
|---|---|---|
| < 40 | LOW | naked long, debit spreads |
| 40–60 | NORMAL | all (debit preferred) |
| 60–70 | ELEVATED | debit + credit spreads (no naked long) |
| > 70 | HIGH | naked short, credit spreads, futures |
| `None` | **UNKNOWN** | **fail-closed: debit spreads + futures only** |

### Layer 4 — Execution timing (`execution_engine.py`, 15m candles)

| Mode | Conditions | exec_score |
|---|---|---|
| **PULLBACK** | Price within 1.5 ATR of ST(7,3) S/R, EMA20 aligned, rejection wick | 14 |
| **CONTINUATION** | Close beyond 5-bar range + 2× volume | 10 |
| **WAIT** | Neither | 0 |

Pullback is preferred — it has a tighter stop and a measurable mean reversion edge in crypto majors.

### Build + score candidate structures (`scoring.py`)

`rank_structures(structures, regime, signal, exec_timing, policy)` calls `score_structure` on each candidate then drops any below the **75 / 85 hard gate**:

```
total = macro_regime(0-20) + signal(0-20) + exec_timing(0-15) +
        contract_health(0-20) + dte(0-10) + rr(0-15) + session_bonus(0-3)
      → clipped to 100
```

**Hard vetoes** (set score=0 and exclude):
- Spread > 10% of mid (5% for naked shorts)
- OI < 50 (≤ 100 for naked shorts)
- Dead zone 02:00–05:00 UTC
- Funding window ±15 min of 00/08/16 UTC
- `|funding_rate| > 0.025`

**Hard score gate** (`passes_score_threshold`):
- ≥ 75 for normal trades (futures ≤ 5×, options long, debit spreads).
- ≥ 85 for naked shorts and futures ≥ 10×.

**Score-vs-no-trade comparison.** Orchestrator computes `score_no_trade(regime, signal, policy)` (a counter-score that rises when avoiding premium, when signal trend is 0, when regime score is weak, when IVR is unavailable). The trade only fires if `best.score > no_trade_score`.

### Sizing (`sizing_engine.py`)

```
target_risk_pct = min(
    fractional_kelly_25(win_rate, rr),
    base_cap_for_structure,            # 1.0% short / 1.5% long / 2.0% futures
    risk_params.max_position_pct,      # default 5%
    0.005 if leverage >= 50 else +inf, # scalp ceiling
    correlation_penalty,               # v3 multiplier
    regime_adaptive_multiplier,        # v3 ATR-bucket multiplier
)
contracts = max(1, min(target_risk_pct * capital / max_loss_per_contract,
                       risk_params.max_contracts))
```

`win_rate` defaults to **0.52** if no calibration history. This is a **known land-mine** — see § 11.

---

## 3. Backtest stack

Three subsystems, all in `backend/app/engines/backtest/` and `backend/app/engines/analytics/`.

### 3.1 Single-asset replay — `backtest_engine.py`

Used by `POST /api/v1/backtest/run`. Replays indicator signals + optional Black-Scholes option P&L over a fixed-window candle history. **Closed-bar only** (no look-ahead).

### 3.2 MTF replay — `backtest_mtf.py` (the one in active use)

Three timeframe profiles (`PROFILES` dict in the file):

| Profile key | Signal TF | Regime TF | Supertrend configs | hold_bars | Forward horizons |
|---|---|---|---|---|---|
| `scalping_15m` | 15m | 1H | (5,2.5)(10,1.5)(14,1.0) | 6 (= 90 min) | 1H / 4H / 12H |
| `intraday_1h` | 1H | 4H | (7,3.0)(14,2.0)(21,2.0) | 8 (= 8 h) | 4H / 12H / 24H |
| `intraday_4h` | 4H | 1D | (10,3.0)(20,2.0)(28,1.5) | 12 (= 2 d) | 24H / 48H / 96H |

Entry on `state == CONFIRMED_SETUP_ACTIVE` with `signal_score >= score_min` and `signal.trend != 0`. Exit on whichever fires first:

1. Held ≥ `hold_bars`
2. ATR R-multiple: `+2R` gain OR `-1R` loss (R = ATR(14) on regime TF)
3. Trend reversal: `signal.trend` flips against the position

Per-trade cost = flat `_FEE_RT_PCT = 0.001` (10 bps round-trip). Slippage and funding are **not** modeled.

Endpoint: `POST /backtest/mtf` returns one `MTFProfileResult` per profile, with regime breakdown, equity curve, forward-return win rates, and the standard four ratios. Frontend renders it in `BacktestPanel.tsx` (`MTFSection` comparison table + `MTFSparkline` per profile).

### 3.3 Walk-forward — `analytics/walk_forward.py`

Two flavours:

- **`run()`** — legacy bps-momentum proxy. Treats `score_threshold` as basis points, fast, kept for backward-compat tests. Selection metric: Sharpe on train window.
- **`run_real()`** — real engine replay (`_engine_replay_trades`). Sweeps `score_thresholds_to_test` (default `[0,3,5,8,10,12,15]`) on each train window, picks the threshold with the highest train-window Sharpe, applies it OOS, aggregates.

Config (`WalkForwardConfig`):
- `train_bars` (default 180), `test_bars` (60), `step_bars` (30).
- Underlying defaults `"BTC"`.

Result persisted to `wf_results` table (config_json, result_json, recommended_threshold, oos_sharpe).

**Beware:** The 1H walk-forward uses a hard-coded `hold_bars=8` in `_engine_replay_trades`. MTF profiles cannot be tuned via WF in the current code.

### 3.4 Performance metrics — `analytics/performance.py`

`PerformanceReport(sharpe, calmar, sortino, max_drawdown, win_rate, avg_rr, profit_factor, total_trades, regime_breakdown)`.

| Metric | Implementation | Caveat |
|---|---|---|
| `sharpe` | `mean(rets)/std(rets) × √8760` (hourly annualisation) | Hard-coded periods_per_year; fed a *per-trade* curve, so the √8760 is wrong by a factor of √(hold_bars). See § 11 W10. |
| `sortino` | `mean / std(negatives) × √8760` | Uses std of only negative returns, not LPM(0). Overstates Sortino vs. convention. |
| `max_drawdown` | `(eq - cummax)/cummax → min` | Standard. |
| `calmar` | `annualised_return / |MDD|` | Inherits the Sharpe annualisation bug. |
| `profit_factor` | `Σwins / Σ|losses|` | Returns `0.0` when there are no losers (should be `inf`). |
| `avg_rr` | `mean(wins) / |mean(losses)|` | Mislabeled — this is "expectancy ratio", not R-multiple. |
| `regime_breakdown` | per-regime trade_count / win_rate / avg_pnl / sharpe_proxy | `sharpe_proxy = mean/std` (no annualisation). |

The metrics module is **the surface where new contributors get tripped up most often** — every "Sharpe = 27" or "Sharpe = -207" in `wf_results` rolls out of these formulas, not from the trading itself.

### 3.5 Parameter sensitivity — `analytics/sensitivity.py`

Runs a Cartesian sweep across configurable parameters at startup (background task) and weekly. Cached in `parameter_sensitivity` table for 7 days. Surfaced via `/api/v1/analytics/sensitivity`.

### 3.6 Correlation tracker — `analytics/correlation.py`

Fed 1H close prices on every `evaluate()`. Computes pairwise 30-bar rolling Pearson correlation across all watched underlyings. Used by `OrderRouter` (future v4) and the `CorrelationHeatmap.tsx` UI.

---

## 4. Risk modules (`engines/risk/`)

All v3, all stateful singletons on `app.state.*`. **Confusingly, two circuit breakers exist** — read this twice.

| Module | Singleton attr | Role |
|---|---|---|
| `circuit_breaker.py` (DrawdownCircuitBreaker) | `app.state.dd_circuit_breaker` | Portfolio drawdown threshold; trips when 90-day rolling drawdown breaches a configurable %. Halts new entries. |
| (older `CircuitBreaker` in services/execution/) | `app.state.circuit_breaker` | **Execution-level**: trips on rapid consecutive losses or burst order failures. NOT the same as drawdown one. |
| `slippage.py` | (stateless) | Tiered market-impact bps lookup `(leverage, OI tier)`. Wired by OrderRouter (v4); **not yet wired into backtest_mtf.py**. |
| `greeks_budget.py` | `app.state.greeks_budget` | Max simultaneous |Δ|, |Γ|, |V|, |Θ| across open positions. |
| `cooldown.py` | (per-key TTL store) | Blocks re-entries by `(underlying, mode, direction)` for a mode-defined window. |
| `microstructure_veto.py` | (stateless) | Last-stage veto on order book imbalance / aggressor-side print pressure. v4 spec; not wired into MTF backtest. |
| `vol_of_vol_gate.py` | (stateless) | IVR-of-IVR stability check; blocks naked premium when vol regime is unstable. |
| `regime_adaptive_sizer.py` | (stateless) | Multiplier on size based on `RegimeResult.atr_percentile` bucket (0.5×/1.0×/1.25×/0.75×). |

**Invariants every contributor must respect** (from `CLAUDE.md`):
- `CorrelationTracker.update()` is called on EVERY `evaluate()` with 1H close.
- `DrawdownCircuitBreaker.update()` is called FIRST inside `evaluate()`, before any strategy logic.
- `CalibrationService.record_trade()` is called on EVERY position close in `paper_store`.
- Walk-forward MUST NOT use test-window data to select the threshold (lookahead veto).

---

## 5. Adaptive state — `services/calibration.py`

`CalibrationService` keeps:
- A 90-reading IVR history per underlying (deque, persisted in `calibration_state.ivr_history_json`).
- The last 50 closed trades (deque, persisted in `calibration_trades`).

API:
- `record_ivr(underlying, ivr)` — call on every snapshot.
- `record_trade(pnl_pct, regime)` — call on every position close.
- `ivr_bands(underlying)` → 30th/70th percentile, falls back to `(30, 70)` if < 20 readings.
- `win_rate(regime=None)` → trailing WR from last 50 trades, regime-filtered if requested, falls back to `0.52` if < 10 trades.

**Current state of these tables in `sterling_paper.db`:**
- `calibration_state`: **0 rows**.
- `calibration_trades`: **0 rows**.

The adaptive loop is wired but cold. Sizing therefore uses the static 0.52 fallback — see § 11 W7.

---

## 6. Data & persistence

SQLite at `backend/sterling_paper.db` (path overridable via `STERLING_DB_PATH`). **47 MB at last check.**

| Table | Row count | What it stores |
|---|---|---|
| `ohlcv` | 343,058 | Per-symbol-resolution candles. `time` is **UNIX seconds**, NOT ms. |
| `positions` | 58 | Paper trades (`data` is a JSON blob with full trade context). |
| `signal_history` | 98 | Per-bar evaluation snapshot (state, direction, IVR, exec_mode). |
| `arrows` | 760 | Green/red arrow events with 7-day TTL. |
| `pnl_history` | 40 | Per-position P&L snapshots over time. |
| `alerts` | 1 | User-defined alert conditions. |
| `webhooks` | 0 | Discord/Telegram/HTTP delivery configs. |
| `equity_snapshots` | 2 | Portfolio value + drawdown + CB state samples. |
| `exchange_configs` | 1 | API key/secret per exchange (encrypted on disk if STERLING_KEY set). |
| `iv_history` | 0 | Reserved for historical IV. |
| `parameter_sensitivity` | 1 | Cached weekly sensitivity sweep. |
| `wf_results` | 3 | Walk-forward results (config_json, result_json, recommended_threshold, oos_sharpe). |
| `calibration_state` / `calibration_trades` | 0 / 0 | Adaptive WR / IVR. Empty. |
| `system_config` | 6 | Misc runtime config. |

**`positions` row format gotcha.** The top-level columns (`entry_price_real`, `notional`, `slippage_bps`) are `NULL` on every existing row. The actual trade data lives inside the `data` TEXT column as JSON: `id, underlying, sized_trade{structure{legs[…]}}, entry_timestamp_ms, entry_spot_price, exit_timestamp_ms, exit_spot_price, realized_pnl_usd, notes, run_once_state`. Several existing rows have `entry_spot_price == 0`, which fabricates fake $21k "wins" — those rows are corrupt seed data; **don't trust positions-derived stats**.

**OHLCV time unit gotcha.** `ohlcv.time` is in **seconds** (delta between consecutive 1H rows = 3600). Code paths that build `Candle(timestamp_ms=…)` from this column must `*1000`.

**In-memory only (lost on restart):**
- arrow events
- live P&L snapshots
- snapshot cache (45s TTL)
- correlation tracker state
- circuit breaker state

---

## 7. API surface (FastAPI, prefix `/api/v1`)

Endpoint files under `backend/app/api/v1/endpoints/`. The full list is in `README.md`; here is the **mental model**:

- **directional/** — evaluate, snapshot, watchlist, preview, run-once, run-all, history, SSE stream, arrows, regime-trend, volatility-scan. The "what should I do right now?" surface.
- **positions/** — CRUD on paper positions + enter, monitor, monitor-all, summary, greeks, pnl-live, close-all, pnl-history, notes, analytics, export. Everything trade-lifecycle-related.
- **backtest/** — `/run` (single-asset BS-aware) + `/mtf` (multi-TF) + walk-forward + sensitivity (under analytics).
- **analytics/** — walk-forward run/list/get, sensitivity sweep, performance reports.
- **risk_dashboard/** — correlation matrix, greeks budget gauge, drawdown CB status, calibration summary.
- **config/** — hot-reload risk params, scoring weights, eval history cap, data source, system info.
- **exchanges/** — adapter CRUD + activate + activate-data-source + test.
- **account/** — balances, positions, orders, fills, exports (proxies the active exchange).
- **alerts/**, **webhooks/**, **options/** (chain browser), **stats/**, **session/** (state export/reset).
- **trading/**, **trading_mode/** — v4 OrderRouter scaffolding (paper / shadow / live modes). **Live mode not yet implemented.**

SSE stream: `GET /api/v1/directional/stream/{underlying}?interval=30` — emits one JSON event per evaluation cycle and writes into `snapshot_cache` for the background poller to reuse.

---

## 8. Frontend — React 19 + TS 5.9 + Vite 8

Three pages share the same backend:

| Page | File | For |
|---|---|---|
| Dashboard | `pages/Dashboard.tsx` | 8-tab classic layout — Analysis / Option Chain / Account / Alerts / Backtest / Positions / Watchlist / Config |
| Pro Terminal | `pages/Terminal.tsx` | Multi-pane grid, tickets, charts |
| Simple Terminal | `pages/SimpleTerminal.tsx` | One-screen guided flow |

**Hooks** wrap React Query around the API; **components** are kept presentational. Both share Zustand store for selected underlying / trading mode.

Important new components from v3 → v4 evolution:
- `WalkForwardPanel`, `SensitivityPanel`, `EquityCurve`
- `CorrelationHeatmap`, `CorrelationWarning`
- `GreeksBudgetGauge`, `DrawdownBreakerBadge`
- `CalibrationPanel` (shows trailing WR + IVR percentile counts)
- `LiveControlPanel`, `GoLivePanel` (v4 — kill switch, daily-loss meter, retry queue, mode selector)
- `RegimeSparkline`, `PnLSparkline`
- `BacktestPanel` — includes the new `MTFSection` comparison table (2026-05-17)
- `PositionsStrip` (top-of-page strip showing open trades)
- `ShadowDiff` (v4 — paper vs live fill diff)

Currently dirty in `git status`: `PositionsStrip.tsx`, `SimpleTerminal.tsx`. Check `git diff` before assuming master state.

---

## 9. Running and testing

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Full stack via Docker
docker compose up --build

# Tests (718+ tests, all mocked, no network)
cd backend && pytest -q
```

**Environment variables that matter:**
- `STERLING_DB_PATH` — override SQLite path.
- `EXCHANGE_ADAPTER` — default adapter (`deribit` / `okx` / `delta_india` / `binance` / `zerodha`).
- `STERLING_KEY` — symmetric key for encrypting API secrets in `exchange_configs`.

**Hot-swap data source** without restart:
```bash
curl -X POST http://localhost:8000/api/v1/config/data-source \
  -H 'Content-Type: application/json' \
  -d '{"exchange":"delta_india"}'
```

**Adapter stack assembly** (in `main.py` lifespan):
```
CachingAdapter(TTL per resource)
  └── RetryingAdapter(3 attempts, 0.4s base, 8s timeout)
        └── <ConcreteAdapter>
```

Tests do not hit live exchanges — every adapter has a fixture under `tests/`. Run `pytest -k <name>` for targeted reruns.

---

## 10. Mode-aware candle routing (`core/trading_mode.py`)

`run_once(instrument, adapter, mode="swing")` looks up `MODES[mode]` to get (macro_tf, signal_tf, exec_tf). This is what closes the "scalp leak" bug: a scalp request now genuinely reads scalp-grade candles, not the old default 4H/1H/15m.

The MTF backtest profiles in `backtest_mtf.PROFILES` should be kept symmetrically aligned with `MODES` — when you add a new mode, add a parallel `TFProfile`.

---

## 11. Known weaknesses & upgrade playbook

This is the most important section. The strategy is currently a **negative-expectancy** filter; the persisted walk-forward (`wf_results` row 3) reads OOS Sharpe -207 / 0% WR for a reason. A clean replay across 6 months of OHLCV in `sterling_paper.db` confirms the picture:

| Asset / TF | n | WR | PF | MDD | Total |
|---|---|---|---|---|---|
| BTC 15m | 220 | 41.4% | 0.95 | -9.4% | -3.5% |
| BTC 1H | 24 | 33.3% | 0.70 | -5.9% | -5.1% |
| ETH 15m | 186 | 38.2% | 0.70 | -21.8% | -21.8% |
| ETH 1H | 22 | 31.8% | 0.39 | -22.6% | -18.6% |
| SOL 15m | 187 | 48.1% | 0.86 | -20.5% | -11.8% |
| SOL 1H | 30 | 56.7% | 1.09 | -5.7% | +1.4% |

Artefacts: `/tmp/sterling_summary.json` (per-threshold sweep + Monte Carlo bootstraps), `/tmp/sterling_fast.py` (fast vectorized replay used to produce them), `/tmp/sterling_out.log` (console log of the sweep run on 2026-05-18).

### Weakness register (ranked by P&L impact)

| # | Where | Issue | Effect |
|---|---|---|---|
| W1 | regime_engine + setup_engine | Signal starvation: only 0.6–1.4% of bars produce a CONFIRMED setup. IDLE consumes ~38% of bars. | < 30 trades / 6 mo on 1H. Below significance floor. |
| W2 | scoring + sweep | `signal_score` thresholds 0/4/8 produce identical PF in most assets — score is non-discriminating. | Threshold-tuning doesn't separate winners from losers. |
| W3 | walk_forward.run_real | Train Sharpe with 1–3 trades is noise. `best_threshold` flips 0/8/12/15 across windows. | Overfit. |
| W4 | backtest_mtf | `_FEE_RT_PCT=0.001` only; **no slippage, no funding, no options spread**, even though `risk/slippage.py` exists. | Backtest is optimistic by ~10–30 bps per trade. |
| W5 | backtest_mtf | Entry fill at `candles[i].close`, not `candles[i+1].open`. | Look-ahead bias of 50–150 bps per trade. |
| W6 | backtest_mtf | Stop / target use ATR(regime_TF) on signal_TF prices — 4H ATR is too wide for 1H entries. | Asymmetric exit; consec losses up to 8. |
| W7 | sizing_engine | `getattr(risk_params, "win_rate", 0.52)` — calibration_trades is empty, so Kelly always uses 0.52. | Recommends positive size even on negative-expectancy combos. |
| W8 | scoring.score_no_trade | Purely additive 20+40+20+20+15 — does not encode adverse selection. | "No-trade" message fires too often / for the wrong reasons. |
| W9 | scoring._check_hard_vetoes | Funding-window + dead-zone vetoes remove ~25% of bars before scoring. | Compounds W1. |
| W10 | analytics/performance.py | `periods_per_year=8760` on a per-trade equity curve; PF returns 0 when no losses; Sortino uses std of negatives. | Every reported ratio is biased. |
| W11 | backtest_mtf._replay_profile | O(N²) regime slice rebuild per bar. | 5 min+ for one 6-month run; frontend timeouts. |
| W12 | overall | Strategy is pure trend-following on a tape that's only ~37% trending. | Structural cap on edge. |

### Upgrade playbook (Tier S/A/B/C in priority order)

**Tier S — must-do before any live capital flips.**

1. **Truthful cost model.** `backtest_mtf.py:19` — wire `risk/slippage.effective_entry` by leverage/OI tier, add funding accrual `0.0001 × (hold_hours/8)` for futures, add option half-spread `(ask-bid)/(2*mid)` per leg.
2. **Entry-fill realism.** Enter at `candles[i+1].open + slippage`, symmetric on exit.
3. **Fix performance metrics.** Compute Sharpe in calendar time (use trade durations), add CAGR/Calmar/MAR/Ulcer/Pain/tail_ratio, fix PF inf-case, use LPM(0) for Sortino.
4. **Stop tuning thresholds with Sharpe on n<10 train trades.** Switch to bootstrap-stable composite (median of `Calmar × √(n/30)` over 500 samples) and run a **deflated Sharpe** test before accepting a threshold. If no threshold has deflated p < 0.10, report **no edge**.

**Tier A — real edge upgrades.**

5. **Asymmetric exits + Chandelier trail.** Replace fixed 1R/2R with 1.2× ATR(signal_TF) stop and Chandelier(N) trail; book 50% at +1R, trail the rest.
6. **HTF momentum z-score.** Add 4H 50-bar momentum z-score gate (long if z>+0.5, short if z<-0.5) as a regime-score component.
7. **Adaptive Kelly with regime priors.** Replace static 0.52 fallback with `calibration_service.win_rate(regime=…)`. Cold start = 0.0 (not 0.52). Add a negative-edge zero gate.
8. **Volatility-bucket sizing instead of IDLE veto.** Don't drop 38% of bars; size them down to `risk_pct × 0.25`.
9. **Wire microstructure_veto and vol_of_vol_gate into backtest.** Keep train/live distributions identical.

**Tier B — validation infra.**

10. **CPCV (López de Prado)** with embargo = `2 × hold_bars`. Replace single-rolling WF. Compute PBO.
11. **Strategy decay tracker** — rolling 90-day Sharpe per (regime, symbol, profile), auto-disable on negative drift.
12. **Live vs. backtest reconciliation** — write `expected_pnl_pct` next to `realized_pnl_pct` on every trade; alert on > 2σ drift across 5 trades.
13. **Vectorize `_replay_profile`** — pre-compute indicators once (see `/tmp/sterling_fast.py`); 60× faster.

**Tier C — new alpha sources.**

14. Order-flow delta-volume proxy.
15. Multi-asset correlation drawdown limiter (uses existing `correlation_tracker`).
16. Mean-reversion track for IDLE/low-ATR regimes (counter-trend, tight 0.5R stops).

---

## 12. Conventions & gotchas

- **Pure functions vs. stateful singletons.** Everything under `engines/` should be pure (no I/O, no time.time, no DB). State lives on `app.state.*` or in services under `app/services/`. If you find yourself reaching for `time.time()` inside an engine module, you're about to make a backtest-vs-live divergence.
- **Schemas are additive-only.** New fields on existing Pydantic models must be `Optional` with defaults. The frontend mirrors backend schemas; breaking a field name breaks the panel that uses it.
- **Backward-compat shims.** `score_macro_regime`, `score_signal`, `score_exec_timing`, `score_structure_rr` in `scoring.py` are wrappers for older tests; do not extend them. New code should call the internal `_score_…_v2` functions directly via `score_structure` only.
- **Two circuit breakers.** `app.state.dd_circuit_breaker` (drawdown) vs `app.state.circuit_breaker` (execution-level). Don't mix.
- **`CircuitBreaker` is an alias for `DrawdownCircuitBreaker`.** Both names appear in tests.
- **OHLCV `time` is seconds, not ms.** Always multiply by 1000 when constructing `Candle`.
- **`positions` JSON corruption.** Some seed rows have `entry_spot_price=0`. Filter them before computing any aggregate stats.
- **`compute_signal` is O(N) but called per-bar in `_replay_profile`** — backtest is O(N²) total. Use the vectorized form in `/tmp/sterling_fast.py` until § 11 B-13 is merged.
- **Funding-window dead-zone** removes ~25% of UTC bars before scoring. If you're debugging "no signals fired", check `_check_hard_vetoes` first.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| **R-multiple** | Profit/loss expressed as multiples of the stop distance (1R). Sterling's exit code targets +2R / -1R but the actual `avg_rr` reported is `mean(wins)/|mean(losses)|`. |
| **IVR / IV Rank** | (Current IV − 1y min) / (1y max − 1y min) × 100. Sterling falls back to HV percentile when no DVOL data. |
| **Setup state** | One of `IDLE`, `EARLY_SETUP_ACTIVE`, `CONFIRMED_SETUP_ACTIVE`, `ENTRY_ARMED_PULLBACK`, `ENTRY_ARMED_CONTINUATION`, `ENTERED`, `PARTIALLY_REDUCED`, `EXITED`, `FILTERED`. |
| **Macro regime** | `BULL_TREND`, `BEAR_TREND`, `RANGING`, `VOLATILE`, `IDLE` (v2 names; v1 names like `BULLISH`, `BULL_RANGING` still in the enum for compat). |
| **Mode** | `swing` (default 4H/1H/15m), `scalp`, `intraday_1h`, etc. — controls candle resolution routing in `run_once`. |
| **Profile** | MTF backtest counterpart of mode. Three exist: `scalping_15m`, `intraday_1h`, `intraday_4h`. |
| **Score breakdown** | Dict on `TradeStructure.score_breakdown` showing each scoring component: `{macro_trend, signal, entry, contract_health, dte, rr, session_bonus, total}`. |
| **No-trade score** | Counter-score (0–100) computed by `score_no_trade`; the orchestrator picks "no trade" if it exceeds best structure score. |
| **Hard gate** | Score ≥ 75 (normal) or ≥ 85 (high-leverage / naked short). Below the gate, structures are **excluded** from the ranked output, not just down-ranked. |
| **Adapter stack** | `CachingAdapter → RetryingAdapter → ConcreteAdapter`. All exchange access goes through this. |

---

## 14. Where to look first when…

| Symptom | First file to open |
|---|---|
| "Why no signal on BTC right now?" | `engines/directional/orchestrator.py` then `setup_engine.evaluate_setup` |
| "Why was this trade filtered?" | `engines/directional/scoring.py:_check_hard_vetoes` |
| "Why is sizing X contracts?" | `engines/directional/sizing_engine.py` |
| "Why is the score 78 vs 82?" | `engines/directional/scoring.py:score_structure` (look at `score_breakdown` in the response) |
| "Why is the regime IDLE?" | `engines/directional/regime_engine.py:compute_regime` (ATR percentile + slope) |
| "Why does the MTF backtest take so long?" | `engines/backtest/backtest_mtf.py:_replay_profile` (O(N²) regime slice) |
| "Sharpe number looks wrong" | `engines/analytics/performance.py` (annualisation bugs) |
| "Walk-forward picked threshold X" | `engines/analytics/walk_forward.py:run_real` |
| "Position closed with weird PnL" | `services/paper_store.py` + `engines/directional/monitor_engine.py` |
| "Frontend chart blank" | matching React Query hook in `frontend/src/hooks/use<Resource>.ts` |
| "Adapter returned stale data" | `services/cache.py` (TTL config) + `services/snapshot_cache.py` |
| "Live mode rejected an order" | (v4) `services/execution/order_router.py` + `services/live_safety.py` |

---

## 15. Suggested first-week checklist

- [ ] `pytest -q` passes (~30 s).
- [ ] `uvicorn main:app --reload` + `npm run dev`; open Dashboard, switch underlyings.
- [ ] Hit `POST /api/v1/directional/run-once?underlying=BTC` and read every field of the response against this doc.
- [ ] Hit `POST /api/v1/backtest/mtf` for BTC with the three profiles; verify the result matches `BacktestPanel` UI.
- [ ] Read `engines/directional/orchestrator.py` top to bottom, then `scoring.py`.
- [ ] Run `/tmp/sterling_fast.py` (vectorized replay) for SOL on `intraday_1h` and verify your number matches `/tmp/sterling_summary.json`.
- [ ] Read `STERLING-V4-SPEC.md` for the canonical resolution of C1–C4 (score×leverage, IVR `None`, sizing chain, veto order).
- [ ] Pick one item from § 11 Tier S and write the unit test for it before touching code.

Welcome aboard.
