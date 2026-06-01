# Derivatives Edge Study + Native Strategy — Design

_Date: 2026-06-02 · Branch context: `feat/realtime-iv-stream` · Status: Phase 1 spec (Phase 2 outlined)_

## Problem

The Sterling derivatives layer (`engines/derivatives/selector.py` + `instrument_chooser.py`)
is a **routing + admission gate**, not a strategy. It takes a long-only spot signal from the
shared edge strategies (`engines/edge/strategies.py`) and either routes it to futures, wraps it
as a long call mirroring the spot direction, or **DEFERs / force-routes to futures** when a
constraint trips (IVR cap, option spread > 12%, pinning gate, premium budget, funding cost,
liquidity floors).

Two consequences:

1. **A good directional signal can be refused derivatives routing** purely because of the gate
   constraints — the user's core observation.
2. **The system never generates a derivatives-native signal.** Options are only ever a long call
   echoing a spot long — the most theta/vol-premium-expensive way to express direction. Genuine
   options alpha (vol-risk-premium, skew, term structure, GEX/pinning, theta harvesting) is only
   ever a *veto*, never a *source* of trades.

We want: (a) **real, overfit-resistant stats** on the best tradeable edge across a full config
grid, (b) a **quantified** answer to "is the gate over-filtering," and (c) a **derivatives-native
strategy** that generates its own trades, coexisting with the existing gate behind a UI **toggle**,
with the validation methodology itself selectable in the UI.

## Data reality (binding constraint)

- **Underlying — real, multi-year:** `backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet`
  (1-minute OHLCV + ~90 TA indicators incl. ATR), ~2023-12 → 2026-05. ~1.1–1.2M rows each.
  → **Futures backtests are fully real.**
- **Options surface — real but live-only:** Delta India `/v2/tickers`
  (`underlying_asset_symbols=BTC|ETH|SOL`, `contract_types=call_options,put_options`) returns a
  rich **live cross-section**: per-strike `mark_iv`/`bid_iv`/`ask_iv`, greeks, `best_bid`/`best_ask`,
  `oi`, `volume`, across ~9 live expiries (daily→monthly). Verified reachable from this env
  (HTTP 200, 547 BTC tickers).
- **Options history — does not exist.** `get_dvol()→None`, `get_dvol_history()→[]` (both stubs);
  `get_candles()` fetches the **perp**, not option instruments; local `iv_history`/`option_iv_ticks`
  tables are **empty** (`iv_surface_params` holds 11 snapshots from one ~1h window on 2026-06-01).
  → A historical IV time series for vol-*timing* (IV-rank over years) **cannot be backtested today**.

**Therefore:** futures edge = real; options edge = **modeled but calibrated to the live surface**
(method 1, below) — strictly more honest than the current optimistic realized-vol model. A genuine
historical options validation requires **forward collection** (the idle `delta_iv_recorder` exists).

## Decisions (locked with user)

- **Options validation = method 1 (calibrate-to-live + forward-collect)** is the default. Methods
  1/2/3 become a **UI selector** (test / analyze / report / choose). 2 = real-only/deferred,
  3 = live-snapshot characterization only.
- **Coexistence = new derivatives-native strategy as a new mode; existing routing-gate kept; toggle
  between them**; new mode active when selected.
- **Sweep = full grid** (params + SL/TP + filters + exits), staged coarse→refine.
- **Sequencing = run Phase 1 to completion and bring real numbers BEFORE designing Phase 2 in
  detail.** (This spec fully specifies Phase 1; Phase 2 is outlined and gets its own spec.)

---

## Phase 1 — Empirical edge study (this spec)

### Objective

A reproducible study producing real, OOS-robust stats that answer:
1. Best tradeable edge per `instrument × symbol × TF × strategy × SL/TP × filter × exit × direction`.
2. **Does options ever beat futures, and in which regimes?** (calibrated-to-live pricing).
3. **Is the routing gate over-filtering?** — the PnL of signals it blocks vs admits, with reasons.

Deliverable: a report + result CSVs + a "Phase 2 seed" recommendation. **No new strategy engine,
no toggle, no UI** — those are Phase 2.

### Components (isolated units)

1. **`study/data.py`** — load underlying parquet, resample to each TF, recompute ATR(14). Reuses
   `engines/edge/strategies.resample`. One responsibility: TF-ready OHLCV+ATR frames.
2. **`study/surface_snapshot.py`** — pull the Delta live chain once, persist to
   `study/fixtures/delta_surface_<date>.json` (reproducibility), and expose measured parameters:
   - ATM IV per expiry → **term structure**,
   - IV by moneyness → **skew**,
   - **VRP = ATM_IV ÷ trailing realized-vol** per symbol,
   - **spread% by moneyness/OI bucket** (real round-trip cost).
   Uses the existing `DeltaIndiaAdapter.get_option_chain` + `IVSurface` fit.
3. **`study/futures_sim.py`** — real bar-by-bar first-touch SL/TP (extend
   `comprehensive_backtest.simulate`). Adds: **ATR-trailing exit**, **short-side mirror**,
   **regime filters**. Round-trip fee 0.10% (Delta taker ~0.05%/side). Time-stop 200 bars.
4. **`study/options_sim.py`** — same captured entries/exits (`simulate_capture`), priced via
   **calibrated BSM**: IV(strike, moneyness, dte) from the fitted surface, scaled to each trade's
   regime realized vol × measured VRP; subtract measured spread% round-trip; long option capped at
   −100%. Honestly labeled "modeled, calibrated to <date> live surface."
5. **`study/grid.py`** — the staged sweep driver (below). Emits both legs per config.
6. **`study/robustness.py`** — wraps existing `robustness_scan.py` (verified: produces `oos_sharpe`
   via `analytics/cpcv.calculate_pbo` + `p_loss` via `analytics/monte_carlo`, gate `MAX_P_LOSS=0.35`):
   CPCV OOS Sharpe + Monte-Carlo p(loss). **Winners gated on OOS, never IS.** Reports IS↔OOS Sharpe
   correlation as the overfit alarm. **Runs only on base-gate survivors** (net-positive, trades ≥ 50)
   — CPCV (15 splits) + 3000-path MC per config is intractable across all ~25k grid configs, so the
   cheap base metrics filter first, then the expensive robustness runs on the surviving few hundred.
7. **`study/gate_audit.py`** — replays `instrument_chooser.choose` + selector over gate-passing
   signals using the live-surface context; tallies DEFER / force-futures reasons; compares realized
   PnL of blocked-options vs admitted. Answers the over-filtering question with a number.
8. **`study/report.py`** — writes `DERIVATIVES_EDGE_STUDY.md` + CSVs.

### The grid (staged)

**Stage A — coarse (~25k configs, both legs):**
- symbols: BTC, ETH, SOL (3)
- TFs: 15m, 30m, 1h, 2h, 4h (5) — sub-15m excluded (known fee-loss; confirmed in prior runs)
- strategies: ma_crossover, mean_reversion, breakout, price_action, smc (5)
- SL/TP ATR pairs with TP>SL: SL∈{1.0,1.5,2.0,2.5} × TP∈{2,3,4,5} → 14 valid pairs
- regime filters: {none, EMA200-trend, ADX>20, ATR-percentile band} (4)
- exits: {fixed TP, ATR-trailing, time-stop-only} (3)
- direction: {long, short} (2)

**Stage B — refine:** around Stage A's top ~50 robust regions, finer entry-param grids
(EMA pairs {9/21, 20/50, 8/34}; RSI entry {25,30,35}; Donchian {20,55}; engulfing/FVG lookbacks)
and a finer SL/TP grid.

Compute note (for the plan, not a spec constraint): pre-resample once per (sym,TF); compute signals
once per (sym,TF,strategy,direction,entry-param); the first-touch sim should be vectorized/numba'd —
naive Python loop × 25k configs × 1h-series is too slow.

### Metrics + acceptance

Per config: trades, win_rate, PF, Sharpe, expectancy, net_return, max_dd, pnl_usd — for **both**
the real-futures leg and the calibrated-options leg.

A config is a **reported winner** only if: trades ≥ 50 (prefer ≥100), **OOS** net_return > 0 and
**OOS** Sharpe ≥ 0.8, Monte-Carlo **p(loss) ≤ 0.35** (aligned to `robustness_scan.py` `MAX_P_LOSS`),
and IS↔OOS Sharpe correlation not strongly negative. Mirrors the existing live `EdgeGate` but
enforced on OOS.

### Outputs

- `DERIVATIVES_EDGE_STUDY.md`: composite-ranked winners; **futures-vs-options verdict** (when, if
  ever, calibrated options beat futures); **gate over-filter finding** (the number);
  per-symbol/strategy/TF/filter/exit rollups; robustness badges; caveats (options = modeled).
- CSVs: `study_results_futures.csv`, `study_results_options.csv`, `study_robustness.csv`,
  `study_gate_audit.csv`.
- **Phase 2 seed** section: concrete recommendation for what the native strategy should do, derived
  from the evidence (e.g. "futures-by-default for direction; options only in measured-cheap-IV /
  high-asymmetry regimes on 4h").

### Non-goals (Phase 1)

No new strategy engine, no mode toggle, no UI, no production wiring, no forward-collector activation
(that's a Phase 2 one-liner). Phase 1 is analysis + report only.

### Honesty / anti-overfit invariants

- OOS-only gating; never select thresholds on the test window (existing project invariant).
- Options results always labeled "modeled, calibrated to <date> live surface."
- Reproducible: the live snapshot is persisted as a fixture and the report cites its timestamp.
- Realistic fees + spreads; sample-size floors enforced.

---

## Phase 2 — Native strategy + toggle + UI (outline; own spec later)

To be designed **after** Phase 1 numbers land. Anticipated scope:

- **`engines/derivatives_native/`** — a strategy that generates its own trades from derivatives-native
  signals (VRP / skew / term-structure / GEX-pinning), with futures-by-default for pure direction.
  Rules dictated by Phase 1 evidence.
- **Mode toggle** — `routing_gate` (existing, untouched) ↔ `native` (new), in derivatives config +
  a FE toggle; new mode active when selected. Existing path is preserved, not replaced.
- **UI validation-method selector (1/2/3)** — calibrate-to-live / real-only / snapshot, each running
  and rendering its own report.
- **Forward IV collector** — switch on the idle `delta_iv_recorder` so a genuine IV history accrues
  for true (non-modeled) future validation.

## Open questions for Phase 2 (deferred)

- Does the native strategy short vol (sell options) or only buy defined-risk? (depends on Phase 1
  VRP findings + account constraints on naked/defined-risk on Delta India).
- How does the toggle interact with `algo_mode` auto-execute and the existing per-strategy profiles?
