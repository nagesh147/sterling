# Strip Sterling to Engine-only — remove Stat Arb, RSI Mean-Rev, Signals & Calibration tabs

**Date:** 2026-06-03
**Branch:** `feat/sterling-only`
**Status:** Approved design — ready for implementation plan

## Goal

Reduce the basic-mode terminal (`SimpleTerminal`) to the **Sterling engine** plus its
utility tabs, removing four competing feature tabs and all their dedicated code, while
guaranteeing **zero functional/UI/UX impact** to the existing Sterling engine views.

### Keep tabs
- `scalping` → **STERLING ENGINE**
- `positions` → **POSITIONS**
- `backtest` → **BACKTEST**

### Remove tabs
- `statarb` → STAT ARB
- `strategy` → RSI MEAN-REV (backed by the `triple_st` engine)
- `signals` → SIGNALS
- `calibration` → CALIBRATION

## Core principle: separate "the tab" from shared infrastructure

The removal must distinguish a tab's *dedicated* code (delete) from *shared* infrastructure
it merely displayed (keep). Three shared assets are consumed by Sterling and/or the pro
`Terminal` and **must survive**:

| Shared asset | Why it stays | Live consumers (kept) |
|---|---|---|
| Backend **signal feed** + hooks `useSignals`, `useSignalFeed`, `useSignalStream`, `useSignalAlerts` | Sterling consumes the signal feed | `ScalpingTab`, `TradingTicket`, `ArrowAlert`, `StreamBadge`, `TradingModeSelector`, derivatives candidate tables |
| `SignalPane` | Left pane of the pro 3-pane `Terminal` | `Terminal.tsx` |
| `CalibrationPanel` + `useCalibration` + `GET /api/v1/risk/calibration/{underlying}` + `CalibrationService` | Bottom panel of pro `Terminal`, `StatusBar`; `CalibrationService.record_trade()` runs on every paper close (Sterling invariant) | `BottomPanel`, `StatusBar`, paper-close path |

Consequences:
- **CALIBRATION removal is tab-only** — drop the tab entry/branch/import in `SimpleTerminal`;
  delete **no** component, hook, endpoint, or service.
- **SIGNALS removal keeps the feed** — delete only the standalone signal-*browsing* UI
  (`SignalsTable` / `SignalsBar` / `SignalsList`) and the one hook orphaned by that deletion
  (`useAllSignalsStream`). The feed, `SignalPane`, and the four shared hooks remain.

## Dependency facts established during design

- `ScalpingTab` (Sterling) does **not** import any statarb/strategy code — cleanly separable.
- `<SignalsTable>` live usages: `SimpleTerminal` signals tab (removed) + `Dashboard.tsx:292`
  (dead/unreachable legacy render). After both are removed → no live consumers → delete.
- `<SignalsBar>` usage: only `Dashboard.tsx:310` (dead) → delete.
- `<SignalsList>` usage: imported in `Dashboard.tsx:55` but **never rendered** → already dead → delete.
- `useAllSignalsStream` consumer: only `SignalsTable` → delete.
- `useStatArb` / `useStrategy` consumers: only `StatArbTab` / `StrategyTab` → delete.
- `DerivativesPanel` matching `StrategyTab` was a **false positive** (`DerivStrategyTab`
  interface, not the component). Only `SimpleTerminal` imports the strategy tab components.
- `CalibrationPanel` is also rendered by `BottomPanel.tsx:82` (live in pro `Terminal`) → keep.
- Backend `triple_st` is referenced by `derivatives/profiles.py`, `derivatives/schemas.py`
  (comments), and a `triple_st` candidate block in `derivatives.py` (~lines 1166–1184).
  `statarb` is referenced by `derivatives/profiles.py` and a background trader in `main.py`.
  `Dashboard.tsx` legacy render is fully unreachable (it returns `SimpleTerminal`/`Terminal`
  before reaching the tab body) — touch only what must compile.

## Changes

### Frontend — delete files
- `frontend/src/components/statarb/` (StatArbTab)
- `frontend/src/components/strategy/` (StrategyTab)
- `frontend/src/components/SignalsTable.tsx`
- `frontend/src/components/SignalsBar.tsx`
- `frontend/src/components/SignalsList.tsx`
- `frontend/src/hooks/useStatArb.ts`
- `frontend/src/hooks/useStrategy.ts`
- `frontend/src/hooks/useAllSignalsStream.ts`

### Frontend — edit
- **`SimpleTerminal.tsx`**
  - Remove imports: `StrategyTab`, `StatArbTab`, `SignalsTable`, `CalibrationPanel`.
  - Narrow `activeSection` union (both the `useState` generic and the inline cast on the tab list) to `'scalping' | 'positions' | 'backtest'`; default stays `'scalping'`.
  - Tab list → only `['scalping','STERLING ENGINE']`, `['positions','POSITIONS']`, `['backtest','BACKTEST']`.
  - Remove the `statarb`, `strategy`, `signals`, `calibration` render branches.
  - Keep `ThreeColumnLayout`, `RightSection`, `V4AnalyticsDashboard`, `useSelectedUnderlying` — still used by the BACKTEST branch.
- **`Dashboard.tsx`** (dead legacy render, must still compile)
  - Remove imports + JSX for `SignalsTable`, `SignalsBar`, `SignalsList`.
  - Leave `CalibrationPanel` import/usage intact (component still exists).

### Backend — delete files
- `backend/app/engines/statarb/` (config.py, schemas.py, scanner.py, `__init__.py`)
- `backend/app/engines/triple_st/` (config.py, engine.py, schemas.py, features.py, exits.py, backtest.py, `__init__.py`)
- `backend/app/api/v1/endpoints/statarb.py`
- `backend/app/api/v1/endpoints/strategy.py`

### Backend — edit
- **`main.py`**
  - Remove the `statarb_config` restore block (imports `StatArbConfig`/`default_statarb_config`, sets `app.state.statarb_config`).
  - Remove `statarb_task = asyncio.create_task(_background_statarb_trader(...))` and its `cancel()/await` in shutdown.
  - Remove the entire `_background_statarb_trader` async function.
  - Remove `strategy_router` import + `include_router`.
  - Remove `statarb_router` import + `include_router`.
- **`derivatives/profiles.py`** — remove the `"statarb"` and `"triple_st"` `StrategyDerivativesProfile` entries and their docstring bullets.
- **`derivatives.py`** — remove the `triple_st` candidate block (`strategy_filter == "triple_st"` branch reading `app.state.triple_st_config` and importing `app.engines.triple_st.backtest`), **preserving** the scalping/price_action and edge candidate paths. Verify by reading the surrounding loop/branch structure before editing.
- **`derivatives/schemas.py`** — tidy comments referencing statarb/triple_st (cosmetic only; no functional change).

### Backend — tests
- Delete `backend/tests/test_phase5_strategy_wiring.py` (strategy/triple_st-specific).
- Update derivatives tests to drop statarb/triple_st references while keeping the rest passing:
  `test_phase3_derivatives_api.py`, `test_edge_wiring.py`, `test_candidates_from_cache.py`,
  `test_phase7_dual_tables.py`, `test_phase2_selector.py`. (Inspect each; only remove the
  statarb/triple_st-specific assertions/fixtures.)
- Search for any dedicated `test_statarb*` file and delete if present.

## Verification gates (must all pass before finishing)

1. **Backend imports:** `app.main` imports cleanly (no references to deleted modules).
2. **Grep clean:** zero remaining importers of `app.engines.statarb`, `app.engines.triple_st`,
   or the deleted frontend files (`SignalsTable`, `SignalsBar`, `SignalsList`, `useStatArb`,
   `useStrategy`, `useAllSignalsStream`, `StatArbTab`, `StrategyTab`).
3. **Backend tests:** derivatives + scalping test suites pass (the kept ones).
4. **Frontend types/build:** `tsc --noEmit` (or `vite build`) passes — no orphaned imports/types.
5. **Sterling untouched (manual smoke):** STERLING ENGINE / POSITIONS / BACKTEST tabs render;
   pro `Terminal` still shows `SignalPane` + `BottomPanel`→`CalibrationPanel`; `StatusBar`
   calibration chip still works.

## Out of scope
- No changes to the pro `Terminal` 3-pane layout (it has none of the removed tabs).
- No deletion of `CalibrationService`, the signal feed/background refresh, `SignalPane`,
  `TradingTicket`, `ArrowAlert`, or the scalping engine's own `mean_reversion.py`
  (a Sterling sub-strategy, distinct from the removed RSI MEAN-REV `triple_st` tab).
- No refactor of `Dashboard.tsx`'s dead legacy render beyond what's required to compile.
