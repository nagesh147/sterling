# Strategy Improvement Plan — Post-Backtest Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix two root causes identified in the 6-month backtest: (1) RANGING/NEUTRAL regime blocks all confirmed entries despite strong signals, producing too few trades; (2) BULL_TREND long entries lose because signals lag — the move is already extended by the time all conditions align.

**Architecture:** Two focused changes — `setup_engine.py` gets a high-score RANGING promotion path, and `scoring.py` / `backtest_engine.py` get a score-minimum gate so only high-confidence entries are taken. Then re-run the backtest to quantify improvement.

**Tech Stack:** Python (existing engines), pytest

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/app/engines/directional/setup_engine.py` — promote RANGING/VOLATILE to CONFIRMED when score ≥ threshold |
| Modify | `backend/app/engines/backtest/backtest_engine.py` — add `score_min` param to `simulate_capital_curve` |
| Test | `backend/tests/test_strategy_fixes.py` — new test file |

---

## Task 1: Promote high-score RANGING/VOLATILE setups to CONFIRMED

**Files:**
- Modify: `backend/app/engines/directional/setup_engine.py`
- Create: `backend/tests/test_strategy_fixes.py`

### Why

`evaluate_setup()` hard-caps RANGING and VOLATILE regimes at `EARLY_SETUP_ACTIVE`. But when all 3 SuperTrends agree AND the signal score is ≥ 16/20, we have strong confluence — the regime label is just lagging. Over 6 months, BTC spent 65% of bars in NEUTRAL/RANGING, which is why it generated only 4 confirmed trades.

The fix: in the RANGING and VOLATILE branches, if `signal.all_green`/`all_red` is True (all 3 STs agree, not just 2/3) AND `signal_score ≥ 16.0`, promote to `CONFIRMED_SETUP_ACTIVE`. Keep the existing EARLY_SETUP path for weaker signals.

### Step 1: Write failing tests

```python
# backend/tests/test_strategy_fixes.py
import pytest
from unittest.mock import MagicMock
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import (
    RegimeResult, SignalResult, MacroRegime, TradeState, Direction,
)

def _regime(macro):
    r = MagicMock(spec=RegimeResult)
    r.macro_regime = macro
    r.score = 0.0
    return r

def _signal(trend, all_green=False, all_red=False, green_count=3, red_count=0, score=0.0, arrow=False):
    s = MagicMock(spec=SignalResult)
    s.trend = trend
    s.all_green = all_green
    s.all_red = all_red
    s.st_trends = ([1]*green_count + [-1]*red_count + [0]*(3-green_count-red_count))[:3]
    s.signal_score = score
    s.green_arrow = arrow and trend == 1
    s.red_arrow   = arrow and trend == -1
    return s


def test_ranging_high_score_all_green_confirms_long():
    """RANGING + all 3 STs green + score ≥ 16 → CONFIRMED_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=True, green_count=3, score=16.5)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.LONG


def test_ranging_high_score_all_red_confirms_short():
    """RANGING + all 3 STs red + score ≥ 16 → CONFIRMED_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=-1, all_red=True, red_count=3, score=17.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.SHORT


def test_ranging_low_score_stays_early():
    """RANGING + all STs green but score < 16 → still EARLY_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=True, green_count=3, score=12.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_ranging_partial_st_stays_early():
    """RANGING + only 2/3 STs green → EARLY regardless of score."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=False, green_count=2, score=18.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_volatile_high_score_all_green_confirms():
    """VOLATILE + all STs green + score ≥ 16 → CONFIRMED_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.VOLATILE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=16.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE


def test_volatile_low_score_stays_early():
    """VOLATILE + low score → EARLY_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.VOLATILE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=14.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_idle_still_filtered():
    """IDLE regime is always filtered regardless of score."""
    regime = _regime(MacroRegime.IDLE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=20.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.FILTERED


def test_trending_regime_unchanged():
    """Existing BULL_TREND confirmed path still works (no regression)."""
    regime = _regime(MacroRegime.BULL_TREND)
    signal = _signal(trend=1, all_green=True, green_count=3, score=15.0, arrow=True)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.LONG
```

- [ ] **Step 1:** Create `backend/tests/test_strategy_fixes.py` with the 8 tests above

- [ ] **Step 2: Verify tests 1, 2, 5 fail** (RANGING/VOLATILE promotion doesn't exist yet)

```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_strategy_fixes.py -v 2>&1 | tail -20
```
Expected: tests 1, 2, 5 FAIL with AssertionError (state is EARLY not CONFIRMED); tests 3, 4, 6, 7, 8 PASS

- [ ] **Step 3: Modify `backend/app/engines/directional/setup_engine.py`**

The promotion threshold:
```python
_HIGH_SCORE_CONFIRM = 16.0   # signal_score threshold to confirm in ranging/volatile
```

Add it near the top of the file (after the existing constants).

In the `evaluate_setup` function, find the RANGING branch:
```python
    elif macro in _RANGING_REGIMES and green_count >= _PARTIAL_ST_MIN and trend == 1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=f"Ranging regime, {green_count}/3 ST bullish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _RANGING_REGIMES and red_count >= _PARTIAL_ST_MIN and trend == -1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason=f"Ranging regime, {red_count}/3 ST bearish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )
```

Replace with:
```python
    elif macro in _RANGING_REGIMES and green_count >= _PARTIAL_ST_MIN and trend == 1:
        sig_score = float(getattr(signal, 'signal_score', 0.0) or 0.0)
        if signal.all_green and sig_score >= _HIGH_SCORE_CONFIRM:
            return SetupResult(
                state=TradeState.CONFIRMED_SETUP_ACTIVE,
                direction=Direction.LONG,
                reason=f"Ranging regime — all STs bullish + high score ({sig_score:.0f}/20)",
                macro_regime=macro,
                signal_trend=trend,
            )
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason=f"Ranging regime, {green_count}/3 ST bullish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _RANGING_REGIMES and red_count >= _PARTIAL_ST_MIN and trend == -1:
        sig_score = float(getattr(signal, 'signal_score', 0.0) or 0.0)
        if signal.all_red and sig_score >= _HIGH_SCORE_CONFIRM:
            return SetupResult(
                state=TradeState.CONFIRMED_SETUP_ACTIVE,
                direction=Direction.SHORT,
                reason=f"Ranging regime — all STs bearish + high score ({sig_score:.0f}/20)",
                macro_regime=macro,
                signal_trend=trend,
            )
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason=f"Ranging regime, {red_count}/3 ST bearish — lower confidence.",
            macro_regime=macro,
            signal_trend=trend,
        )
```

Then find the VOLATILE branch:
```python
    elif macro in _VOLATILE_REGIMES and trend == 1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.LONG,
            reason="Volatile regime, all STs bullish — momentum long.",
            macro_regime=macro,
            signal_trend=trend,
        )
    elif macro in _VOLATILE_REGIMES and trend == -1:
        return SetupResult(
            state=TradeState.EARLY_SETUP_ACTIVE,
            direction=Direction.SHORT,
            reason="Volatile regime, all STs bearish — momentum short.",
            macro_regime=macro,
            signal_trend=trend,
        )
```

Replace with:
```python
    elif macro in _VOLATILE_REGIMES and trend == 1:
        sig_score = float(getattr(signal, 'signal_score', 0.0) or 0.0)
        state = (TradeState.CONFIRMED_SETUP_ACTIVE
                 if signal.all_green and sig_score >= _HIGH_SCORE_CONFIRM
                 else TradeState.EARLY_SETUP_ACTIVE)
        reason = (f"Volatile regime — all STs bullish + high score ({sig_score:.0f}/20)"
                  if state == TradeState.CONFIRMED_SETUP_ACTIVE
                  else "Volatile regime, all STs bullish — momentum long.")
        return SetupResult(state=state, direction=Direction.LONG,
                           reason=reason, macro_regime=macro, signal_trend=trend)
    elif macro in _VOLATILE_REGIMES and trend == -1:
        sig_score = float(getattr(signal, 'signal_score', 0.0) or 0.0)
        state = (TradeState.CONFIRMED_SETUP_ACTIVE
                 if signal.all_red and sig_score >= _HIGH_SCORE_CONFIRM
                 else TradeState.EARLY_SETUP_ACTIVE)
        reason = (f"Volatile regime — all STs bearish + high score ({sig_score:.0f}/20)"
                  if state == TradeState.CONFIRMED_SETUP_ACTIVE
                  else "Volatile regime, all STs bearish — momentum short.")
        return SetupResult(state=state, direction=Direction.SHORT,
                           reason=reason, macro_regime=macro, signal_trend=trend)
```

- [ ] **Step 4: Run all 8 tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_strategy_fixes.py -v 2>&1 | tail -15
```
Expected: 8/8 passed

- [ ] **Step 5: Run existing phase tests (regression check)**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_phase_b.py tests/test_phase_e_f.py tests/test_backtest_robustness.py -v 2>&1 | tail -15
```
Expected: all pass

- [ ] **Step 6: Commit**
```bash
git add backend/app/engines/directional/setup_engine.py backend/tests/test_strategy_fixes.py
git commit -m "feat: promote RANGING/VOLATILE to CONFIRMED when score ≥ 16 and all STs agree"
```

---

## Task 2: Add score_min filter to simulate_capital_curve + re-run backtest stats

**Files:**
- Modify: `backend/app/engines/backtest/backtest_engine.py` — add `score_min` param to `simulate_capital_curve`
- Test: `backend/tests/test_strategy_fixes.py` (append)

### Why

Even with more CONFIRMED signals, we need a quality gate to avoid the lowest-conviction entries. `signal_score ≥ 10/20` (50%) filters out bars where only volume OR only squeeze fires without RSI/HA confirmation.

### Step 1: Append tests

```python
# append to backend/tests/test_strategy_fixes.py
from app.engines.backtest.backtest_engine import simulate_capital_curve
from app.schemas.backtest import BacktestBarResult
from app.schemas.directional import TradeState

def _bar(state='CONFIRMED_SETUP_ACTIVE', direction='long', fwd12=1.5, score=15.0):
    return BacktestBarResult(
        timestamp_ms=1_700_000_000_000,
        close_1h=30000.0, close_4h=30000.0,
        macro_regime='BULL_TREND', ema50=29000.0,
        signal_trend=1, all_green=True, all_red=False,
        green_arrow=True, red_arrow=False,
        st_trends=[1,1,1], st_values=[29900.0,29800.0,29700.0],
        state=state, direction=direction,
        fwd_return_12h=fwd12,
        signal_score=score,
    )

def test_simulate_score_min_filters_low_score_entries():
    """score_min=12 must skip bars with signal_score < 12."""
    bars = [
        _bar(score=8.0,  fwd12=5.0),   # should be skipped (score too low)
        _bar(score=14.0, fwd12=3.0),   # should be taken
    ]
    sim_no_filter = simulate_capital_curve(bars, capital=10_000, score_min=0.0)
    sim_filtered  = simulate_capital_curve(bars, capital=10_000, score_min=12.0)
    # With filter: only 1 trade (the 14.0 score bar)
    assert sim_filtered['trade_count'] == 1 if 'trade_count' in sim_filtered else len(sim_filtered['trades']) == 1
    # Without filter: 2 trades
    assert sim_no_filter['trade_count'] == 2 if 'trade_count' in sim_no_filter else len(sim_no_filter['trades']) == 2

def test_simulate_score_min_zero_unchanged():
    """score_min=0 (default) must behave identically to old no-filter behaviour."""
    bars = [_bar(score=5.0, fwd12=2.0), _bar(score=18.0, fwd12=-1.0)]
    sim = simulate_capital_curve(bars, capital=10_000, score_min=0.0)
    assert len(sim['trades']) == 2
```

- [ ] **Step 1:** Append the 2 tests above to `backend/tests/test_strategy_fixes.py`

- [ ] **Step 2: Verify new tests fail** (score_min param doesn't exist yet)

```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_strategy_fixes.py -k "score_min" -v 2>&1 | tail -10
```
Expected: TypeError or AttributeError

- [ ] **Step 3: Modify `simulate_capital_curve` in `backend/app/engines/backtest/backtest_engine.py`**

Current signature:
```python
def simulate_capital_curve(
    bars: List[BacktestBarResult],
    capital: float = 10_000.0,
    fee_rt_pct: float = FEE_RT_PCT,
    risk_pct: float = 0.02,
    hold_bars: int = 3,
) -> dict:
```

New signature (add `score_min` at end with default 0.0):
```python
def simulate_capital_curve(
    bars: List[BacktestBarResult],
    capital: float = 10_000.0,
    fee_rt_pct: float = FEE_RT_PCT,
    risk_pct: float = 0.02,
    hold_bars: int = 3,
    score_min: float = 0.0,
) -> dict:
```

Inside the function, find the entry condition:
```python
        if not in_trade and bar.state == conf:
            d = 1 if bar.direction == "long" else (-1 if bar.direction == "short" else 0)
```

Replace with:
```python
        if not in_trade and bar.state == conf:
            bar_score = float(getattr(bar, 'signal_score', 0.0) or 0.0)
            if bar_score < score_min:
                continue
            d = 1 if bar.direction == "long" else (-1 if bar.direction == "short" else 0)
```

Also need to add `signal_score` field to `BacktestBarResult` schema (it currently doesn't have it). In `backend/app/schemas/backtest.py`, add to `BacktestBarResult`:
```python
    signal_score: Optional[float] = None   # 0-20 confluence score
```

- [ ] **Step 4: Run score_min tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_strategy_fixes.py -k "score_min" -v 2>&1 | tail -10
```
Expected: 2 passed

Note: if the `_bar()` helper uses `signal_score=` but `BacktestBarResult` doesn't have that field yet, the test will error — fix by adding the field to the schema first.

- [ ] **Step 5: Run all 10 tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_strategy_fixes.py -v 2>&1 | tail -15
```
Expected: 10/10 passed

- [ ] **Step 6: Run regression suite**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_robustness.py tests/test_phase_b.py tests/test_phase_e_f.py tests/test_signal_squeeze.py -v 2>&1 | tail -15
```
Expected: all pass

- [ ] **Step 7: Commit**
```bash
git add backend/app/engines/backtest/backtest_engine.py backend/app/schemas/backtest.py backend/tests/test_strategy_fixes.py
git commit -m "feat: add score_min filter to simulate_capital_curve; add signal_score to BacktestBarResult"
```

---

## Task 3: Wire signal_score into backtest_engine bar results

**Files:**
- Modify: `backend/app/engines/backtest/backtest_engine.py` — populate `signal_score` in `BacktestBarResult`

### Why

`signal_score` was added to `BacktestBarResult` in Task 2 but `run_backtest()` never populates it. The bar-level replay must capture the score so `simulate_capital_curve(score_min=10)` can actually filter.

### Step 1: Modify `run_backtest` in `backtest_engine.py`

Find the `bars.append(BacktestBarResult(...))` call inside `run_backtest`. It currently creates the bar result without `signal_score`. Add it:

```python
        bars.append(
            BacktestBarResult(
                timestamp_ms=current_ts,
                close_1h=signal.close_1h,
                close_4h=regime.close_4h,
                macro_regime=regime.macro_regime.value,
                ema50=regime.ema50,
                signal_trend=signal.trend,
                all_green=signal.all_green,
                all_red=signal.all_red,
                green_arrow=signal.green_arrow,
                red_arrow=signal.red_arrow,
                st_trends=signal.st_trends,
                st_values=signal.st_values,
                state=setup.state.value,
                direction=setup.direction.value,
                signal_score=float(getattr(signal, 'signal_score', 0.0) or 0.0),  # ← add this
                fwd_return_4h=_fwd_return(candles_1h, i, 4),
                ...
            )
        )
```

- [ ] **Step 1:** Add `signal_score=float(getattr(signal, 'signal_score', 0.0) or 0.0)` to the `BacktestBarResult(...)` constructor call in `run_backtest`

- [ ] **Step 2: Write a quick integration test**

```python
# append to backend/tests/test_strategy_fixes.py
from tests.conftest import make_candles
from app.engines.backtest.backtest_engine import run_backtest

def test_run_backtest_populates_signal_score():
    """run_backtest bars must have signal_score populated (not None/0 always)."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    res = run_backtest("BTC", c4h, c1h, lookback_days=30, sample_every_n_bars=4)
    assert len(res.bars) > 0
    scores = [b.signal_score for b in res.bars if b.signal_score is not None]
    assert len(scores) > 0
    assert any(s > 0 for s in scores)
```

- [ ] **Step 3: Run new test**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_strategy_fixes.py::test_run_backtest_populates_signal_score -v 2>&1 | tail -10
```
Expected: 1 passed

- [ ] **Step 4: Full regression**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/ -v --ignore=tests/test_okx_adapter.py --ignore=tests/test_order_router.py 2>&1 | tail -20
```
Expected: all pass (ignore pre-existing failures in okx/order_router which were already failing)

- [ ] **Step 5: Commit**
```bash
git add backend/app/engines/backtest/backtest_engine.py backend/tests/test_strategy_fixes.py
git commit -m "feat: populate signal_score in BacktestBarResult from run_backtest"
```

---

## Self-Review Checklist

### Spec coverage
- [x] RANGING regime → CONFIRMED when all_green/all_red + score ≥ 16
- [x] VOLATILE regime → CONFIRMED when all_green/all_red + score ≥ 16  
- [x] RANGING partial (2/3 STs) → still EARLY (no regression)
- [x] IDLE → still FILTERED (no regression)
- [x] Trending BULL/BEAR regimes → unchanged (no regression)
- [x] `simulate_capital_curve` accepts `score_min` with default 0.0 (backward compat)
- [x] `BacktestBarResult` carries `signal_score`
- [x] `run_backtest` populates `signal_score` from signal engine

### Threshold choice: why 16/20?
- 16/20 = 80% of max score. Requires at least 3 of the 4 weighted factors to fire:
  - ST flip (3pts) + RSI (2pts) + HA aligned (4pts) + HA real aligned (2pts) = 11 of 20 needed minimum
  - volume spike (4pts) + squeeze (4pts) push it over 16
- Below 16 in RANGING = signal is present but not exceptional → keep as EARLY

### No regression risks
- All existing tests pass (trending regime logic untouched)
- `score_min=0.0` default means zero behaviour change for existing callers
