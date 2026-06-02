# Strip Sterling to Engine-only — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the STAT ARB, RSI MEAN-REV, SIGNALS, and CALIBRATION tabs (and their dedicated frontend + backend code) from the Sterling app, leaving only the STERLING ENGINE / POSITIONS / BACKTEST tabs, without altering existing Sterling-engine behavior, UI, or UX.

**Architecture:** Surgical removal that distinguishes a tab's *dedicated* code (deleted) from *shared* infrastructure it merely displayed (kept). Frontend: prune `SimpleTerminal` tabs, delete orphaned components/hooks, fix dead-code references in `Dashboard`. Backend: delete `engines/statarb` + `engines/triple_st`, their endpoints/routers, the stat-arb background trader, the `triple_st` candidate block in `derivatives.py`, and the two strategy-profile entries; relocate the two profiles into local test fixtures where tests use them as generic vehicles. Shared assets that survive: the backend signal feed + `useSignals`/`useSignalFeed`/`useSignalStream`/`useSignalAlerts`, `SignalPane`, `CalibrationPanel` + `useCalibration` + `/risk/calibration` + `CalibrationService`.

**Tech Stack:** React + TypeScript + Vite (frontend), FastAPI + Pydantic + pytest (backend).

**Spec:** `docs/superpowers/specs/2026-06-03-sterling-only-removal-design.md`
**Branch:** `feat/sterling-only` (already created; spec already committed).

---

## File map

**Frontend — modify**
- `frontend/src/pages/SimpleTerminal.tsx` — drop 4 tabs (imports, union, tab list, render branches)
- `frontend/src/pages/Dashboard.tsx` — remove dead refs to deleted signal components
- `frontend/src/utils/colors.ts` — fix stale doc comment

**Frontend — delete**
- `frontend/src/components/statarb/` (StatArbTab)
- `frontend/src/components/strategy/` (StrategyTab)
- `frontend/src/components/SignalsTable.tsx`, `SignalsBar.tsx`, `SignalsList.tsx`
- `frontend/src/hooks/useStatArb.ts`, `useStrategy.ts`, `useAllSignalsStream.ts`

**Backend — modify**
- `backend/app/api/v1/endpoints/derivatives.py` — remove `triple_st` candidate block
- `backend/app/engines/derivatives/profiles.py` — remove `triple_st` + `statarb` entries + docstring bullets
- `backend/main.py` — remove stat-arb config restore, task create/cancel, `_background_statarb_trader`, strategy + statarb router includes
- `backend/tests/test_phase3_derivatives_api.py`, `test_candidates_from_cache.py`, `test_edge_wiring.py` — repoint sample strategy to `directional`
- `backend/tests/test_phase2_selector.py`, `test_phase7_dual_tables.py` — relocate sample profiles to local fixtures

**Backend — delete**
- `backend/app/engines/statarb/`, `backend/app/engines/triple_st/`
- `backend/app/api/v1/endpoints/statarb.py`, `backend/app/api/v1/endpoints/strategy.py`
- `backend/tests/test_phase5_strategy_wiring.py`

---

## Phase 1 — Frontend

### Task 1: Prune the four tabs from `SimpleTerminal`

**Files:**
- Modify: `frontend/src/pages/SimpleTerminal.tsx`

- [ ] **Step 1: Remove imports of the deleted components**

Delete these four import lines (currently lines 4, 9, 19, 21):

```tsx
import { SignalsTable } from '../components/SignalsTable';
```
```tsx
import { CalibrationPanel } from '../components/CalibrationPanel';
```
```tsx
import { StrategyTab } from '../components/strategy/StrategyTab';
```
```tsx
import { StatArbTab } from '../components/statarb/StatArbTab';
```

- [ ] **Step 2: Trim the ThreeColumnLayout import to what stays in use**

Replace (line 23):

```tsx
import { ThreeColumnLayout, LeftSection, RightSection, StatCard } from '../components/ThreeColumnLayout';
```

with:

```tsx
import { ThreeColumnLayout, RightSection } from '../components/ThreeColumnLayout';
```

- [ ] **Step 3: Narrow the `activeSection` union (state declaration)**

Replace (line ~145):

```tsx
  const [activeSection, setActiveSection] = useState<'scalping' | 'statarb' | 'strategy' | 'signals' | 'positions' | 'backtest' | 'calibration'>('scalping');
```

with:

```tsx
  const [activeSection, setActiveSection] = useState<'scalping' | 'positions' | 'backtest'>('scalping');
```

- [ ] **Step 4: Shrink the tab list and its cast**

Replace:

```tsx
          {([
            ['scalping',   'STERLING ENGINE'],
            ['statarb',    'STAT ARB'],
            ['strategy',    'RSI MEAN-REV'],
            ['signals',     'SIGNALS'],
            ['positions',   'POSITIONS'],
            ['backtest',    'BACKTEST'],
            ['calibration', 'CALIBRATION'],
          ] as ['scalping' | 'statarb' | 'strategy' | 'signals' | 'positions' | 'backtest' | 'calibration', string][]).map(([id, label]) => (
```

with:

```tsx
          {([
            ['scalping',   'STERLING ENGINE'],
            ['positions',   'POSITIONS'],
            ['backtest',    'BACKTEST'],
          ] as ['scalping' | 'positions' | 'backtest', string][]).map(([id, label]) => (
```

- [ ] **Step 5: Remove the four dead render branches**

Replace the whole block (from the comment above the `scalping` branch through the end of the `calibration` branch):

```tsx
        {/* V4 Analytics shown on signals, backtest, and calibration tabs — in the right sidebar of those tabs */}
        {activeSection === 'scalping' && (
          <ScalpingTab />
        )}
        {activeSection === 'statarb' && (
          <StatArbTab />
        )}
        {activeSection === 'strategy' && (
          <StrategyTab />
        )}
        {activeSection === 'signals' && (
          <ThreeColumnLayout
            leftNav={[{ id: 'all', label: 'All Signals', color: 'var(--t-bright)'}]}
            activeNav="all"
            onNavClick={() => {}}
            centerHeader={<>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Signals</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Live signal feed</div>
            </>}
            centerContent={<div className="term-signals-wrap" style={{ flex: 1, minHeight: 0 }}><SignalsTable /></div>}
            centerFullBleed
            rightSidebar={<>
              <RightSection label="Analytics">
                <V4AnalyticsDashboard activeSymbol={underlying} />
              </RightSection>
            </>}
          />
        )}
        {activeSection === 'positions' && <PositionsStrip asPage />}
        {activeSection === 'backtest' && (
          <ThreeColumnLayout
            leftNav={[{ id: 'backtest', label: 'Backtest', color: 'var(--t-blue)' }]}
            activeNav="backtest"
            onNavClick={() => {}}
            centerHeader={<>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Backtest</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Historical candle data & signal simulation</div>
            </>}
            centerContent={<BacktestView />}
            rightSidebar={<>
              <RightSection label="Analytics">
                <V4AnalyticsDashboard activeSymbol={underlying} />
              </RightSection>
            </>}
          />
        )}
        {activeSection === 'calibration' && (
          <ThreeColumnLayout
            leftNav={[{ id: 'calibration', label: 'Calibration', color: 'var(--t-amber)' }]}
            activeNav="calibration"
            onNavClick={() => {}}
            centerHeader={<>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Calibration</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Adaptive calibration metrics</div>
            </>}
            centerContent={<CalibrationPanel />}
            rightSidebar={<>
              <RightSection label="Analytics">
                <V4AnalyticsDashboard activeSymbol={underlying} />
              </RightSection>
            </>}
          />
        )}
```

with:

```tsx
        {activeSection === 'scalping' && (
          <ScalpingTab />
        )}
        {activeSection === 'positions' && <PositionsStrip asPage />}
        {activeSection === 'backtest' && (
          <ThreeColumnLayout
            leftNav={[{ id: 'backtest', label: 'Backtest', color: 'var(--t-blue)' }]}
            activeNav="backtest"
            onNavClick={() => {}}
            centerHeader={<>
              <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--t-bright)' }}>Backtest</div>
              <div style={{ fontSize: 10, color: 'var(--t-dim)', marginTop: 1 }}>Historical candle data & signal simulation</div>
            </>}
            centerContent={<BacktestView />}
            rightSidebar={<>
              <RightSection label="Analytics">
                <V4AnalyticsDashboard activeSymbol={underlying} />
              </RightSection>
            </>}
          />
        )}
```

- [ ] **Step 6: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS for `SimpleTerminal.tsx` (it still references `StatArbTab`/`StrategyTab`/`SignalsTable`/`CalibrationPanel`? No — all removed). The only errors that may remain are from `Dashboard.tsx` (fixed in Task 2) — there should be none yet because the component files still exist. Expected: clean (0 errors).

---

### Task 2: Remove dead references to deleted signal components in `Dashboard`

`Dashboard.tsx`'s tab body is unreachable (it returns `SimpleTerminal`/`Terminal` first), but it must still compile once the component files are deleted in Task 3.

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Remove the three imports**

Delete these lines (currently 54, 55, 58):

```tsx
import { SignalsBar } from '../components/SignalsBar';
```
```tsx
import { SignalsList } from '../components/SignalsList';
```
```tsx
import { SignalsTable } from '../components/SignalsTable';
```

- [ ] **Step 2: Remove the two JSX usages**

Delete this line (currently ~292):

```tsx
          <PanelBoundary title="LIVE SIGNALS"><SignalsTable /></PanelBoundary>
```

Delete this line (currently ~310):

```tsx
          <SignalsBar />
```

(`SignalsList` has no JSX usage — the import removal in Step 1 is enough.)

- [ ] **Step 3: Typecheck still clean**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (0 errors). Component files still exist; we removed only references.

---

### Task 3: Delete orphaned frontend components and hooks

**Files:**
- Delete: 5 components + 2 dirs + 3 hooks (below)
- Modify: `frontend/src/utils/colors.ts` (stale comment)

- [ ] **Step 1: Delete the files**

Run:

```bash
cd /home/nageshmadaram/Sterling
rm -rf frontend/src/components/statarb frontend/src/components/strategy
rm frontend/src/components/SignalsTable.tsx frontend/src/components/SignalsBar.tsx frontend/src/components/SignalsList.tsx
rm frontend/src/hooks/useStatArb.ts frontend/src/hooks/useStrategy.ts frontend/src/hooks/useAllSignalsStream.ts
```

- [ ] **Step 2: Fix the stale doc comment in `colors.ts`**

Replace (line 3):

```ts
/** Single source of truth for signal state colors — used by SignalsTable, AlertsPanel, and InstrumentDetailCard */
```

with:

```ts
/** Single source of truth for signal state colors — used by AlertsPanel and InstrumentDetailCard */
```

- [ ] **Step 3: Grep-confirm no live references remain**

Run:

```bash
cd /home/nageshmadaram/Sterling
grep -rn "SignalsTable\|SignalsBar\|SignalsList\|useStatArb\|useStrategy\|useAllSignalsStream\|StatArbTab\|StrategyTab" frontend/src --include=*.tsx --include=*.ts
```

Expected: NO output. (If `useSignalFeed.ts` shows a `// same logic as SignalsTable.resolveMode` historical comment, that is acceptable — it is an internal note, not a dependency. Leave it.)

- [ ] **Step 4: Full frontend typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (0 errors).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add frontend/src/pages/SimpleTerminal.tsx frontend/src/pages/Dashboard.tsx frontend/src/utils/colors.ts
git add -A frontend/src/components frontend/src/hooks
git commit -m "refactor(ui): remove stat-arb, rsi-mean-rev, signals, calibration tabs from SimpleTerminal

Keep CalibrationPanel/SignalPane and the signal feed/hooks — still used by the
pro Terminal and the Sterling engine. Delete only the dedicated tab UI + orphaned
components/hooks (StatArbTab, StrategyTab, SignalsTable/Bar/List, useStatArb,
useStrategy, useAllSignalsStream).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — Backend code

### Task 4: Remove the `triple_st` candidate block and the two strategy profiles

**Files:**
- Modify: `backend/app/api/v1/endpoints/derivatives.py`
- Modify: `backend/app/engines/derivatives/profiles.py`

- [ ] **Step 1: Remove the `triple_st` candidate block in `derivatives.py`**

Delete this block (currently lines ~1165–1193), preserving the surrounding edge-collection and `return out`:

```python
    # Triple-ST (RSI(2))
    if strategy_filter is None or strategy_filter == "triple_st":
        try:
            from app.api.v1.endpoints import strategy as _strat
            cfg = getattr(request.app.state, "triple_st_config", None)
            if cfg is not None:
                syms = _strat._store_symbols(cfg.warmup_bars * 24)
                for sym in syms[:10]:
                    if underlying_filter and sym.upper() != underlying_filter.upper():
                        continue
                    candles = _strat._store_candles(sym, "1h", cfg.warmup_bars)
                    if not candles or len(candles) < cfg.warmup_bars:
                        continue
                    from app.engines.triple_st import backtest as _bt
                    ev = _bt.evaluate_live(sym, candles, cfg)
                    if ev.trade_plan is None:
                        continue
                    signal_id = f"trist:{sym}:{ev.timestamp_ms}"
                    out.append((signal_id, SignalContext(
                        strategy="triple_st", underlying=sym, direction=ev.direction,
                        entry=ev.trade_plan.entry, stop_loss=ev.trade_plan.stop_loss,
                        take_profit=None,
                        atr=0.0, rr_target=2.0,
                        signal_score=50.0 + max(0, ev.rsi_oversold - ev.rsi),
                        signal_strength="STRONG", expected_hold_minutes=5 * 24 * 60,
                        mode_name="swing",
                    )))
        except Exception:
            pass

    return out
```

with:

```python
    return out
```

- [ ] **Step 2: Remove the `triple_st` + `statarb` profile entries in `profiles.py`**

Delete these two entries from the `DEFAULT_PROFILES` dict (currently lines ~108–138):

```python
    # Triple-ST RSI(2)
    "triple_st": StrategyDerivativesProfile(
        strategy="triple_st",
        instrument_bias=InstrumentBias.AUTO,
        target_delta=0.575,                # 0.55-0.60 band ITM
        target_delta_tolerance=0.075,
        dte_min=10,
        dte_preferred=14,
        dte_max=21,
        expected_hold_minutes=5 * 24 * 60, # 5 days
        expiry_close_minutes_before=120,
        leverage_cap=10.0,
        max_premium_pct_of_account=0.015,
        funding_cost_max_pct_of_R=0.25,
        min_oi=1.0,                        # Delta India options are thin — venue-realistic floor
        min_volume_24h_x_contract=1.0,
        max_spread_pct=0.04,
        ivr_pct_naked_max=40,              # tighter — swing options need cheap IV
    ),

    # StatArb — futures-only, per-leg leverage capped, basis-aware
    "statarb": StrategyDerivativesProfile(
        strategy="statarb",
        instrument_bias=InstrumentBias.FUTURES,
        dte_min=0, dte_preferred=0, dte_max=0,
        expected_hold_minutes=60 * 24,     # 1 day median spread hold
        leverage_cap=5.0,                  # per leg; basis exposure capped 2× elsewhere
        max_premium_pct_of_account=0.02,
        funding_cost_max_pct_of_R=0.25,
        ivr_pct_naked_max=100,             # n/a for futures-only
    ),

```

(That is: remove from the `# Triple-ST RSI(2)` comment through the blank line after the `statarb` entry's closing `),`. The `# Directional / Hybrid VCP` entry that follows stays.)

- [ ] **Step 3: Remove the two stale docstring bullets in `profiles.py`**

Replace (lines 13–14):

```python
  • "triple_st" — Triple-ST RSI(2) daily mean-reversion. Swing hold.
  • "statarb" — futures-only, per-leg leverage cap, basis-aware.
```

with: (delete both lines entirely — the `• "directional"` bullet below stays.)

- [ ] **Step 4: Tidy the two cosmetic `schemas.py` comments**

Edit `backend/app/engines/derivatives/schemas.py` (cosmetic only — no functional change).

Replace (line ~29):

```python
    FUTURES    = "futures"     # always futures (e.g. StatArb)
```

with:

```python
    FUTURES    = "futures"     # always futures
```

Replace (line ~103):

```python
    strategy: str                                   # "scalping/price_action", "triple_st", "statarb", ...
```

with:

```python
    strategy: str                                   # e.g. "scalping/price_action", "edge/smc", "directional"
```

- [ ] **Step 5: Sanity-import the edited modules**

Run:

```bash
cd /home/nageshmadaram/Sterling/backend
python -c "import app.engines.derivatives.profiles as p; assert 'triple_st' not in p.DEFAULT_PROFILES and 'statarb' not in p.DEFAULT_PROFILES; print('profiles OK', sorted(p.DEFAULT_PROFILES))"
```

Expected: prints `profiles OK [...]` with neither `triple_st` nor `statarb` in the list. (No commit yet — `import app.main` still references the engines via `main.py`; that is fixed in Task 5.)

---

### Task 5: Unwire stat-arb + strategy from `main.py`

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Remove the stat-arb config restore block**

Delete this block (currently lines ~1363–1374):

```python
    # Restore persisted StatArb config (survives server restarts)
    from app.engines.statarb.config import StatArbConfig as _SAC, default_statarb_config as _default_sac
    _saved_sac = get_config("statarb_config")
    if _saved_sac:
        try:
            cfg = _SAC.model_validate_json(_saved_sac)
            app.state.statarb_config = cfg
            log.info("Restored StatArb config from DB")
        except Exception:
            app.state.statarb_config = _default_sac()
    else:
        app.state.statarb_config = _default_sac()
```

(The `# Restore persisted scalping config` comment above and the `from app.engines.scalping.config import ...` line below both stay.)

- [ ] **Step 2: Remove the stat-arb task creation**

Delete these two lines (currently ~1494–1495):

```python
    statarb_task = asyncio.create_task(_background_statarb_trader(app, interval=15))
    log.info("StatArb background trader started")
```

- [ ] **Step 3: Remove the stat-arb task cancellation in shutdown**

Delete this block (currently ~1535–1539):

```python
    statarb_task.cancel()
    try:
        await statarb_task
    except (Exception, BaseException):
        pass
```

- [ ] **Step 4: Remove the entire `_background_statarb_trader` function**

The function is ~148 lines and earlier edits shift its line numbers, so delete it by text anchor (everything from its `async def` up to, but not including, `def create_app()`). Run:

```bash
cd /home/nageshmadaram/Sterling
python3 - <<'PY'
p = "backend/main.py"
s = open(p).read()
start = s.index("async def _background_statarb_trader")
end = s.index("def create_app() -> FastAPI:")
s = s[:start].rstrip() + "\n\n\n" + s[end:]
open(p, "w").write(s)
print("removed _background_statarb_trader")
PY
```

Expected: prints `removed _background_statarb_trader`.

- [ ] **Step 5: Remove the strategy router include**

Delete this block (currently ~1794–1796, plus its trailing blank line):

```python
    # Triple SuperTrend strategy (self-contained module)
    from app.api.v1.endpoints.strategy import router as strategy_router
    app.include_router(strategy_router, prefix="/api/v1")
```

- [ ] **Step 6: Remove the statarb router include**

Delete this block (currently ~1802–1803):

```python
    from app.api.v1.endpoints.statarb import router as statarb_router
    app.include_router(statarb_router, prefix="/api/v1/statarb", tags=["statarb"])
```

- [ ] **Step 7: Confirm no statarb/strategy references remain in `main.py`**

Run:

```bash
cd /home/nageshmadaram/Sterling
grep -nE "statarb|_background_statarb|strategy_router|app\.engines\.triple_st|endpoints\.strategy\b" backend/main.py
```

Expected: NO output. (Note: lines containing the word "strategy" in unrelated contexts such as `scoring_strategy` are fine and are not matched by the patterns above.)

---

### Task 6: Delete the engines, endpoints, and the strategy-wiring test; verify backend imports

**Files:**
- Delete: `backend/app/engines/statarb/`, `backend/app/engines/triple_st/`, `backend/app/api/v1/endpoints/statarb.py`, `backend/app/api/v1/endpoints/strategy.py`, `backend/tests/test_phase5_strategy_wiring.py`

- [ ] **Step 1: Delete the backend files**

Run:

```bash
cd /home/nageshmadaram/Sterling
rm -rf backend/app/engines/statarb backend/app/engines/triple_st
rm backend/app/api/v1/endpoints/statarb.py backend/app/api/v1/endpoints/strategy.py
rm backend/tests/test_phase5_strategy_wiring.py
```

- [ ] **Step 2: Grep-confirm no remaining importers of the deleted engines/endpoints**

Run:

```bash
cd /home/nageshmadaram/Sterling
grep -rn "app\.engines\.statarb\|app\.engines\.triple_st\|endpoints\.statarb\|endpoints import statarb\|endpoints\.strategy\|endpoints import strategy\b" backend/app backend/main.py
```

Expected: NO output. (If anything appears outside `backend/tests/`, fix it before continuing.)

- [ ] **Step 3: Verify the app imports cleanly**

Run:

```bash
cd /home/nageshmadaram/Sterling/backend
python -c "import main; main.create_app(); print('app imports + builds OK')"
```

Expected: prints `app imports + builds OK` with no ImportError/AttributeError. (If `create_app()` needs env/DB and errors for an unrelated reason, fall back to `python -c "import main; print('import OK')"` and confirm no reference to deleted modules.)

- [ ] **Step 4: Commit the backend code removal**

```bash
cd /home/nageshmadaram/Sterling
git add -A backend/app backend/main.py backend/tests/test_phase5_strategy_wiring.py
git commit -m "refactor(backend): remove statarb + triple_st engines, endpoints, and wiring

Delete engines/statarb + engines/triple_st, their /statarb and /strategy routers,
the stat-arb background trader, the triple_st candidate block in derivatives.py,
and the triple_st/statarb derivatives-profile entries. CalibrationService and the
signal feed are untouched (Sterling invariants).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — Tests & verification

### Task 7: Fix derivatives tests that used the removed strategies as sample data

The kept derivatives tests use `triple_st`/`statarb` as generic vehicles for selector/table machinery (Sterling infra). Repoint the endpoint/config tests to the surviving `directional` profile; relocate the two profiles into local fixtures for the unit tests that assert their specific numbers.

**Files:**
- Modify: `backend/tests/test_phase3_derivatives_api.py`, `test_candidates_from_cache.py`, `test_edge_wiring.py`
- Modify: `backend/tests/test_phase2_selector.py`, `test_phase7_dual_tables.py`

- [ ] **Step 1: Remove the obsolete triple_st_config stub in `test_phase3_derivatives_api.py`**

Delete these two lines (currently ~81–82 — the `/candidates` triple_st branch no longer exists):

```python
    # Triple-ST config stub so /candidates' triple_st branch doesn't NPE
    app.state.triple_st_config = MagicMock(warmup_bars=210)
```

- [ ] **Step 2: Repoint the endpoint/config/edge tests from `triple_st` → `directional`**

These three files use `triple_st` only as a profile-key / filter string (no dependence on its numeric profile values). Repoint them:

```bash
cd /home/nageshmadaram/Sterling
sed -i 's/triple_st/directional/g' \
  backend/tests/test_phase3_derivatives_api.py \
  backend/tests/test_candidates_from_cache.py \
  backend/tests/test_edge_wiring.py
```

Then read each file and sanity-check the comments still read sensibly (e.g. `# (e.g. directional)`); they are non-functional. No value assertions in these three files depend on the old triple_st numbers (`directional` is also `enabled=False` by default, so the `enabled is False` assertions still hold).

- [ ] **Step 3: Add local profile fixtures to `test_phase2_selector.py`**

The selector unit tests assert specific profile numbers, so preserve behavior by owning the sample profiles locally. Add these module-level constants near the top of the file (after the existing imports — they reference `StrategyDerivativesProfile` and `InstrumentBias`, which the file already imports; if `InstrumentBias` is not imported, add `from app.engines.derivatives.schemas import InstrumentBias`):

```python
# Local sample profiles (formerly DEFAULT_PROFILES["triple_st"] / ["statarb"],
# kept here as test vehicles after those strategies were removed from production).
_SWING_PROFILE = StrategyDerivativesProfile(
    strategy="swing_demo",
    instrument_bias=InstrumentBias.AUTO,
    target_delta=0.575,
    target_delta_tolerance=0.075,
    dte_min=10,
    dte_preferred=14,
    dte_max=21,
    expected_hold_minutes=5 * 24 * 60,
    expiry_close_minutes_before=120,
    leverage_cap=10.0,
    max_premium_pct_of_account=0.015,
    funding_cost_max_pct_of_R=0.25,
    min_oi=1.0,
    min_volume_24h_x_contract=1.0,
    max_spread_pct=0.04,
    ivr_pct_naked_max=40,
)
_FUTURES_PROFILE = StrategyDerivativesProfile(
    strategy="futures_demo",
    instrument_bias=InstrumentBias.FUTURES,
    dte_min=0, dte_preferred=0, dte_max=0,
    expected_hold_minutes=60 * 24,
    leverage_cap=5.0,
    max_premium_pct_of_account=0.02,
    funding_cost_max_pct_of_R=0.25,
    ivr_pct_naked_max=100,
)
```

- [ ] **Step 4: Repoint `test_phase2_selector.py` usages to the local fixtures**

Apply these substitutions in `test_phase2_selector.py`:

- `DEFAULT_PROFILES["triple_st"]` → `_SWING_PROFILE`
- `DEFAULT_PROFILES["statarb"]` → `_FUTURES_PROFILE`
- `profiles_mod.get_profile("triple_st")` → `profiles_mod.get_profile("directional")` (this test targets the registry lookup, which must use a surviving key)
- the `assert p.strategy == "triple_st"` immediately after that `get_profile` → `assert p.strategy == "directional"`
- `get_profile("triple_st", overrides={"triple_st": override})` → `get_profile("directional", overrides={"directional": override})`, and in the `override = StrategyDerivativesProfile(strategy="triple_st", ...)` on the line above it, set `strategy="directional"`
- remaining bare `strategy="triple_st"` (in `SignalContext(...)`) and `list_recent(strategy="triple_st")` and `profile_overrides={"triple_st": ...}` keys → `"swing_demo"`

Command to find every remaining occurrence to convert by hand:

```bash
cd /home/nageshmadaram/Sterling
grep -nE "triple_st|statarb" backend/tests/test_phase2_selector.py
```

Expected after edits: only `_SWING_PROFILE` / `_FUTURES_PROFILE` / `"swing_demo"` / `"futures_demo"` / `"directional"` references remain (no bare `triple_st` or `statarb`).

- [ ] **Step 5: Add the `_SWING_PROFILE` fixture to `test_phase7_dual_tables.py` and repoint**

Add the same `_SWING_PROFILE` constant (copy the block from Step 3; ensure `StrategyDerivativesProfile` and `InstrumentBias` are imported in this file — add the import if missing) near the top, then substitute:

- `DEFAULT_PROFILES["triple_st"]` → `_SWING_PROFILE`
- `_good_signal(strategy: str = "triple_st")` → `_good_signal(strategy: str = "swing_demo")`
- every `profile_overrides={"triple_st": ...}` key and bare `strategy="triple_st"` / `row_strategy="triple_st"` → `"swing_demo"`

Find them with:

```bash
cd /home/nageshmadaram/Sterling
grep -nE "triple_st|statarb" backend/tests/test_phase7_dual_tables.py
```

Expected after edits: no bare `triple_st`/`statarb` remain.

- [ ] **Step 6: Run the affected test files**

Run:

```bash
cd /home/nageshmadaram/Sterling/backend
python -m pytest tests/test_phase2_selector.py tests/test_phase3_derivatives_api.py tests/test_phase7_dual_tables.py tests/test_candidates_from_cache.py tests/test_edge_wiring.py -q
```

Expected: all PASS. If a value assertion fails in `test_phase2_selector`/`test_phase7` it means a `DEFAULT_PROFILES["triple_st"]` lookup was missed (should be `_SWING_PROFILE`) — re-run the Step 4/5 grep and convert it. If a `KeyError: 'triple_st'`/`'statarb'` appears, the same applies.

- [ ] **Step 7: Confirm no test still references the removed strategies as production profiles**

Run:

```bash
cd /home/nageshmadaram/Sterling
grep -rnE "DEFAULT_PROFILES\[.(triple_st|statarb)" backend/tests
grep -rn "app.engines.statarb\|app.engines.triple_st\|endpoints.strategy\|endpoints.statarb" backend/tests
```

Expected: NO output from either grep.

- [ ] **Step 8: Commit the test fixes**

```bash
cd /home/nageshmadaram/Sterling
git add -A backend/tests
git commit -m "test: drop strategy-wiring test; relocate sample profiles to fixtures

Delete test_phase5_strategy_wiring.py. Repoint endpoint/config tests to the
surviving 'directional' profile; relocate the triple_st/statarb profiles used by
the selector/dual-table unit tests into local fixtures (_SWING_PROFILE /
_FUTURES_PROFILE) so behavior is preserved without depending on removed strategies.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Full verification gates

**Files:** none (verification only)

- [ ] **Step 1: Backend — full import + targeted suites**

Run:

```bash
cd /home/nageshmadaram/Sterling/backend
python -c "import main; main.create_app(); print('app OK')"
python -m pytest tests/ -q -k "deriv or selector or dual_tables or candidates or edge or scalping"
```

Expected: `app OK` and all selected tests PASS.

- [ ] **Step 2: Backend — repo-wide grep clean**

Run:

```bash
cd /home/nageshmadaram/Sterling
grep -rn "app\.engines\.statarb\|app\.engines\.triple_st" backend/app backend/main.py
grep -rn "statarb\|triple_st" backend/main.py
```

Expected: NO output. (References inside test fixtures are already namespaced as `swing_demo`/`futures_demo`/`directional`; `backend/` helper scripts outside `app/` are out of scope.)

- [ ] **Step 3: Frontend — typecheck + production build**

Run:

```bash
cd /home/nageshmadaram/Sterling/frontend
npx tsc --noEmit && npx vite build
```

Expected: typecheck clean (0 errors) and `vite build` completes successfully.

- [ ] **Step 4: Frontend — grep clean**

Run:

```bash
cd /home/nageshmadaram/Sterling
grep -rn "SignalsTable\|SignalsBar\|SignalsList\|useStatArb\|useStrategy\|useAllSignalsStream\|StatArbTab\|StrategyTab\|'statarb'\|'strategy'\|'signals'\|'calibration'" frontend/src --include=*.tsx --include=*.ts
```

Expected: NO output for the deleted identifiers. (The `'statarb'/'strategy'/'signals'/'calibration'` string literals should be gone from `SimpleTerminal`. A historical comment mentioning `SignalsTable.resolveMode` in `useSignalFeed.ts` is acceptable.)

- [ ] **Step 5: Manual smoke check (record results, do not auto-pass)**

Start the app and confirm, in basic mode (`SimpleTerminal`):
- Tab bar shows exactly **STERLING ENGINE / POSITIONS / BACKTEST** — no STAT ARB / RSI MEAN-REV / SIGNALS / CALIBRATION.
- STERLING ENGINE tab renders `ScalpingTab` with its futures/options candidate tables (unchanged).
- POSITIONS and BACKTEST tabs render unchanged.

Then switch to pro mode (TERMINAL button) and confirm Sterling shared infra is intact:
- Left `SignalPane` renders.
- Bottom panel still shows the Calibration panel; `StatusBar` calibration chip still updates.

- [ ] **Step 6: (If smoke surfaced fixes) commit; otherwise the branch is ready**

If Step 5 required code fixes, commit them. Otherwise the work is complete on `feat/sterling-only`. Use the superpowers:finishing-a-development-branch skill to decide merge/PR.

---

## Notes for the engineer

- **Do not delete** `CalibrationService` (`backend/app/services/calibration.py`), the `/api/v1/risk/calibration/{underlying}` endpoint, `CalibrationPanel`, `useCalibration`, `SignalPane`, or any signal hook other than `useAllSignalsStream`. These are consumed by the Sterling engine and/or the pro `Terminal`. CALIBRATION removal is **tab-only**.
- `backend/app/engines/scalping/mean_reversion.py` is a **Sterling sub-strategy** and is unrelated to the removed RSI MEAN-REV (`triple_st`) tab. Leave it.
- `Dashboard.tsx`'s tab body is dead/unreachable; only touch the lines required to compile after deletions — do not refactor it.
