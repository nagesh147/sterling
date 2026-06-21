# Kite Sterling Kite Engine Options Engine — Design

**Date:** 2026-06-13
**Branch:** `KiteEngine`
**Status:** Locked (user-approved 2026-06-13)

## 1. Goal

A self-contained, **Kite-exclusive** options-buying engine that, on a 1H Heikin-Ashi
**Sterling Kite Engine** trend filter, scans the Indian-market universe (Nifty 50 / Bank
Nifty / FinNifty / Sensex constituent stocks + the NIFTY / BANKNIFTY / FINNIFTY /
SENSEX index options), emits a **Signal** whenever an underlying enters full
trend-alignment, picks an **ATM/ITM** option strike (never OTM), surfaces "ready"
signals in the Kite **right sidebar**, lets the user click a signal to **see the setup
drawn on a 1H chart**, and **optionally auto-executes** (toggle, default OFF) through
the existing Kite order path under the live-safety gate.

## 2. Hard constraints

1. **Kite is exclusive.** The engine and its Kite wiring import **no** strategy / signal /
   options / derivative logic from any other engine — specifically NOT
   `app.engines.derivatives` (the `DerivativesSelector` / `decide_both` / `SignalContext`),
   nor `edge`, `directional`, `scalping`, or `sterling_*`. The strike picker and the
   auto-exec adaptation are written fresh, for Kite only.
2. **Allowed shared primitives** (math/data types, not strategy logic):
   - `app.engines.indicators.compute_heikin_ashi(opens, highs, lows, closes)`
   - `app.engines.indicators.compute_supertrend(highs, lows, closes, period, multiplier)`
   - `app.domain.models.Signal` (canonical broker/market-agnostic output schema)
3. **Engine stays broker/market-agnostic.** Pure: no Kite/adapter imports, no order calls.
   It takes a closed `Candle` series and returns `list[Signal]`. Conforms to
   `StrategyProtocol` (`generate(*args, **kwargs) -> list[Signal]`).
4. **Closed candles only.** The data layer drops the forming 1H bar before the engine sees it.

## 3. Sterling Kite Engine logic (the spec)

Operate on the underlying's 1H candles. Convert raw OHLC → Heikin-Ashi, then compute
three SuperTrends on the HA high/low/close (params verbatim; "fast/mid/slow" named by
flip-responsiveness, which the multiplier drives):

- `ST_fast = compute_supertrend(ha_h, ha_l, ha_c, 21, 1)`
- `ST_mid  = compute_supertrend(ha_h, ha_l, ha_c, 14, 2)`
- `ST_slow = compute_supertrend(ha_h, ha_l, ha_c, 7, 3)`

**Warm-up:** `warmup = max(periods) = 21`. `compute_supertrend` seeds `trend[period]=1`,
so a "fresh transition" is only evaluated for bar `i` where both `i` and `i-1` have all
three trends valid (non-seed). Practically `i >= warmup + 1`.

**Regime (per bar i):**
- `bull = t_fast[i]==+1 and t_mid[i]==+1 and t_slow[i]==+1`
- `bear = t_fast[i]==-1 and t_mid[i]==-1 and t_slow[i]==-1`
- otherwise `flat` (mixed → no new entry)

**Entry — fresh transition only** (was NOT fully aligned at `i-1`, IS now at `i`):
- bull transition → `Signal(direction="long",  instrument_type="options", …)` → CE
- bear transition → `Signal(direction="short", instrument_type="options", …)` → PE
- One open position per underlying. `Signal.stop_loss = ST_trail.line[i]` at entry
  (trail target, default `ST_mid`). `take_profit=None` (trailing is the only exit).
  `source="sterling_kite_engine"`, `score`/`strength` from alignment conviction.

**Trailing stop / exit (only exit, no fixed target):**
- Trail line = the trail-target SuperTrend line (default `ST_mid` (14,2)).
- Each new closed bar, re-read the trail line and **ratchet the stop only favorably**
  (up for long, down for short).
- **Exit** when the trail SuperTrend's `trend` sign flips against the position on a closed
  HA candle (HA close crosses the trail line).
- Knob `trail_target ∈ {"fast"(21,1), "mid"(14,2), "slow"(7,3)}`, default `"mid"`
  (tighten → fast, loosen → slow).
- **Optional early-lock:** when unrealized profit ≥ `early_lock_profit_r` × initial risk
  (`|entry − initial_stop|`), also allow exit on `ST_slow` flip. Default `early_lock=False`.

## 4. Backend module layout — `backend/app/engines/sterling_kite_engine/`

(Mirrors the `sterling_engine/` package shape; **no** cross-engine imports.)

- `config.py` — `SterlingKiteEngineConfig` (frozen dataclass): the three `(period,mult)`
  pairs, `trail_target`, `early_lock`, `early_lock_profit_r`, `warmup`. Sensible defaults.
- `regime.py` — **pure** core, fully testable, no I/O:
  - `compute_regime(candles, cfg) -> RegimeSeries` (HA + 3 ST + per-bar bull/bear/flat +
    the three trend arrays + the three lines)
  - `entry_transitions(regime) -> mask` (fresh full-alignment transitions)
  - `trail_line(regime, cfg) / trail_trend(regime, cfg)` (selected by `trail_target`)
- `engine.py` — `SterlingKiteEngine` (conforms to `StrategyProtocol`):
  - `generate(candles, underlying) -> list[Signal]` — emits an entry Signal **only when the
    latest closed bar is a fresh transition** and there is no open position for `underlying`.
  - stateful per-underlying lifecycle (`_positions: dict[str, _OpenPos]`):
    `manage(underlying, candles) -> ManageResult` ratchets the stop and reports an exit when
    the trail trend flips (+ early-lock `ST_slow` flip). No order calls.
- `schemas.py` — pydantic `EngineSignalRow`, `EngineState`, `SetupChart` (for the API/UI).
- Tests: `backend/tests/engines/sterling_kite_engine/` — regime alignment, warm-up skip,
  fresh-transition-only entry, trail ratchet monotonicity, trail-flip exit, `trail_target`
  knob, early-lock, one-position-per-underlying, `StrategyProtocol` conformance, Signal
  field correctness (options / long↔CE / short↔PE / stop_loss==trail line).

## 5. Kite wiring (the only Kite-specific code)

All under the Kite namespace; **exclusive** — built fresh, no other-engine imports.

### 5a. Universe — `backend/app/engines/sterling_kite_engine/kite_universe.py` (or a Kite service module)
Build the scan set from the Kite instruments dump (`InstrumentCache.load`):
underlyings with listed options (NFO + BFO equity options) ∪ the four indices
(NIFTY 50, NIFTY BANK, NIFTY FIN SERVICE/FINNIFTY, SENSEX). Backed by an editable
`universe.json` so baskets are tunable.
*Caveat: index membership drifts; the JSON is the source of truth.*

### 5b. Throttled scanner (background, per active Kite user)
- 1H-candle cache, refreshed every few minutes; semaphore-throttled (~3 rps Kite limit).
- Runs `SterlingKiteEngine` over the universe; collects "ready" signals
  (fresh transition on latest **closed** bar) → writes to a store the sidebar polls.
- *Caveat: first full scan is slow; cache makes re-scans cheap; needs paid historical sub.*

### 5c. Kite ATM/ITM strike picker — fresh, Kite-only
Uses `KiteClient.get_option_chain(instrument)` (returns strike / moneyness / dte):
- bull → CE, bear → PE; **ATM or ITM only, never OTM**.
- `strike_moneyness ∈ {"ATM","ITM1","ITM2"}`, default `"ATM"`.
- nearest viable expiry with a small DTE floor (skip same-day theta cliff).
- index options exchange: NIFTY/BANKNIFTY/FINNIFTY → NFO, SENSEX → BFO.

### 5d. Endpoints (under `/api/v1/kite`, e.g. an `engine/` sub-path)
- `GET /api/v1/kite/engine/signals` — current "ready" signals (instrument, regime, CE/PE,
  chosen strike/expiry, trailing stop). Polled by the sidebar.
- `GET /api/v1/kite/engine/setup/{token}` — `SetupChart`: 1H closed candles + the three ST
  line series + entry marker + ratcheted trailing-stop line (for click-to-visualize).
- `GET/POST /api/v1/kite/engine/config` — knobs (`trail_target`, `strike_moneyness`,
  `early_lock`, **`auto_execute`** toggle). `auto_execute` defaults **OFF**.

### 5e. Auto-execute (toggle, default OFF) — Kite order path, not other engines
When ON: a new "ready" signal with no open position for that underlying → pick ATM/ITM
strike → place via the **Kite** order path (`client.place_order_option`, generalized for
NFO/BFO) under the existing `live_safety` gate (kill-switch / daily-loss / idempotency),
exactly as manual Kite orders do. One position per underlying. The crypto `OrderRouter`
and other-engine selectors are **not** used.
*Caveat: real money on Indian markets — gated, default off, same safety as manual placement.*

## 6. Frontend — Kite right sidebar

- `frontend/src/components/kite/SterlingKiteEnginePane.tsx` placed in the `KiteLayout`
  `rightSidebar` slot (replacing the empty `<div>` in `KiteTab.tsx:54`); styled with the
  existing `kiteUI` tokens (Kite orange `#ff5722`).
  - Header: engine status + **auto-execute toggle** + knobs (trail target, moneyness).
  - List: **only "ready"** signals — instrument, BULL/BEAR, fast/mid/slow alignment chips,
    CE/PE + chosen strike & expiry, trailing stop. Click a row →
  - **Click-to-chart**: open the 1H chart (reuse the `InstrumentPane` lightweight-charts v5
    setup) drawing **HA candles + the 3 SuperTrend lines + entry marker + trailing-stop line**.
- `useSterlingKiteEngine` hook (in `useKite.ts` or a new file) polls `engine/signals` and
  fetches `engine/setup/{token}` on click.

## 7. Build order (phased, each independently testable)

1. **Engine core** (`config`, `regime`, `engine`, `schemas`) + full TDD suite. ← the heart.
2. **Universe** builder + `universe.json`.
3. **Throttled scanner** + candle cache + signals store.
4. **ATM/ITM strike picker** (Kite-only).
5. **Endpoints** (`signals`, `setup/{token}`, `config`).
6. **Right-sidebar pane** + `useSterlingKiteEngine` hook (advisory display).
7. **Click-to-chart** setup visualization.
8. **Auto-execute** wiring (toggle, default OFF) through the Kite order path + `live_safety`.

## 8. Defaults (locked)

- Auto-execute **OFF** by default (opt-in toggle).
- Strikes **ATM** default; **ITM** optional; **OTM excluded**.
- Universe = **all F&O-eligible names + 4 indices**, from the instruments dump (not hardcoded).
- Scan timeframe **1H**; cache-refreshed background scan.
- Sidebar shows **only "ready"** signals (fresh full-alignment transition).
- `trail_target = "mid"`, `early_lock = False`.

## 9. Honest caveats / risks

- Kite historical API is **rate-limited** and requires the **paid historical subscription**;
  the universe scan is throttled + cached accordingly. First scan is slow.
- Index **constituent membership drifts** — `universe.json` is editable source-of-truth.
- Auto-execute places **real orders on Indian markets** — default OFF, gated by `live_safety`.
- Not all listed names have liquid options/weeklies; the strike picker skips names with no
  viable ATM/ITM contract at an acceptable DTE.
- This is the **first** strategy wired to Kite (previously manual-only). It remains
  advisory unless the user flips auto-execute.
