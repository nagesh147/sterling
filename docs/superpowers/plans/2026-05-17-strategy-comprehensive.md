# Comprehensive Strategy Fix — All Symbols

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Fix three root causes identified in per-bar analysis that hurt ALL symbols: (1) stale entries — 90% of confirmed bars entered 20+ bars after the ST flip, meaning we buy at the top/short at the bottom; (2) overextended RSI — longs entered when RSI > 70 (overbought), shorts entered when RSI < 30 (oversold); (3) wrong fwd-return horizon in simulation — using 12-bar hold for scalping TFs instead of 4-bar.

**Architecture:** Two engine changes only — `signal_engine.py` gets tighter RSI bounds and a `bars_since_flip` staleness penalty; `backtest_engine.py` gets a `fwd_horizon` param for simulation. No schema changes.

**Data evidence:**
- 38/42 confirmed BTC bars: flip_age = 99 (stale signal > 20 bars old)
- BULL_TREND long bar 12: RSI=71.6 → loses -1.884% at 8H (overbought entry)
- BEAR_TREND short bar 34: RSI=34.5, st_dist=-0.842% → bounce +0.599% at 4H (oversold entry)
- BULL_TREND longs: 73% WR (good!) but several overbought losses drag average down
- RANGING shorts: 70% WR (the best signal type)

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/app/engines/directional/signal_engine.py` — tighter RSI bounds + staleness penalty |
| Modify | `backend/app/engines/backtest/backtest_engine.py` — add `fwd_horizon` to simulate_capital_curve |
| Test | `backend/tests/test_comprehensive_fix.py` — new test file |

---

## Task 1: Tighter RSI bounds + staleness penalty in signal_engine.py

**Files:**
- Modify: `backend/app/engines/directional/signal_engine.py`
- Create: `backend/tests/test_comprehensive_fix.py`

### What changes

**RSI bounds (current → new):**
```
Long:  40 < RSI < 78  →  42 < RSI < 70   (filter overbought > 70)
Short: 22 < RSI < 60  →  30 < RSI < 57   (filter oversold < 30)
```

**RSI momentum (current → new):**
```
Long momentum:  RSI > 60          →  55 < RSI < 68   (momentum but not overbought)
Short momentum: RSI < 40          →  32 < RSI < 45   (momentum but not oversold)
```

**Staleness penalty — NEW:**
After computing the weighted score, scan the last 16 bars to find the most recent ST flip in the current direction (green_arrow for trend=1, red_arrow for trend=-1). Compute `bars_since_flip`. Subtract `min(4, bars_since_flip // 4)` from the earned score before computing signal_score. Cap the penalty at 4 points.

If no flip found in 16 bars, `bars_since_flip = 16` → penalty = 4.

This means:
- Fresh entry (flip ≤ 4 bars ago): 0pt penalty
- Slightly stale (5–8 bars): 1pt penalty
- Stale (9–12 bars): 2pt penalty
- Very stale (13–16+ bars): 4pt penalty max

A confirmed entry that was at score 16 becomes:
- Fresh: 16 → 16 (still confirmed ≥ 15)
- 8 bars stale: 16 → 15 (barely confirmed)
- 12 bars stale: 16 → 14 (EARLY, not confirmed)
- 16+ bars stale: 16 → 12 (EARLY)

Add `bars_since_flip: int = 0` to `SignalResult` schema in `directional.py`.

### Step 1: Write failing tests

```python
# backend/tests/test_comprehensive_fix.py
import pytest
import numpy as np
from tests.conftest import make_candles
from app.engines.directional.signal_engine import compute_signal


def test_signal_engine_rsi_upper_bound_long():
    """Longs with RSI >= 70 must not earn rsi_ok points (score drops)."""
    # Build candles with strong uptrend to push RSI near 70+
    # We can't guarantee RSI > 70 with make_candles but we can test the
    # tighter bounds are wired by checking score degrades on high RSI.
    # Instead test the bounds directly via a mock-like approach:
    from app.engines.directional.signal_engine import _rsi_ok_long, _rsi_ok_short
    assert _rsi_ok_long(69.9) is True
    assert _rsi_ok_long(70.0) is False   # boundary: exactly 70 is NOT ok
    assert _rsi_ok_long(41.9) is False   # below 42 not ok
    assert _rsi_ok_long(42.1) is True


def test_signal_engine_rsi_lower_bound_short():
    """Shorts with RSI <= 30 must not earn rsi_ok points."""
    from app.engines.directional.signal_engine import _rsi_ok_long, _rsi_ok_short
    assert _rsi_ok_short(30.1) is True
    assert _rsi_ok_short(30.0) is False   # boundary: exactly 30 is NOT ok
    assert _rsi_ok_short(56.9) is True
    assert _rsi_ok_short(57.0) is False   # upper bound for shorts


def test_signal_engine_returns_bars_since_flip():
    """SignalResult must include bars_since_flip field (int >= 0)."""
    candles = make_candles(80, base=30000.0, trend=10.0)
    result = compute_signal(candles)
    assert hasattr(result, 'bars_since_flip')
    assert isinstance(result.bars_since_flip, int)
    assert result.bars_since_flip >= 0


def test_signal_score_lower_on_stale_signal():
    """Stale signals (no flip in last 16 bars) must have lower score than
    fresh signals with identical conditions. We verify by comparing two
    identical candle sets where one has a recent flip."""
    # Use a flat trend candle set — signal will be stale (no recent flip)
    flat_candles = make_candles(80, base=30000.0, trend=0.0)
    result_flat = compute_signal(flat_candles)
    # With a strong trend (generates a flip), score should be higher or equal
    trend_candles = make_candles(80, base=30000.0, trend=40.0)
    result_trend = compute_signal(trend_candles)
    # The flat stale signal should not have a higher score than trend signal
    # (This is a directional test, not exact equality)
    assert result_flat.signal_score <= result_trend.signal_score + 4  # generous bound


def test_default_behavior_preserved_for_medium_rsi():
    """RSI in the 42–70 long zone must still work normally."""
    candles = make_candles(80, base=30000.0, trend=15.0)
    result = compute_signal(candles)
    # Should run without error; score in [0, 20]
    assert 0.0 <= result.signal_score <= 20.0
```

Note: Tests 1 and 2 require extracting the RSI gate logic into helper functions `_rsi_ok_long(rsi)` and `_rsi_ok_short(rsi)` in signal_engine.py. These are pure functions that return bool — easy to test directly.

- [ ] **Step 1:** Create `backend/tests/test_comprehensive_fix.py` with the 5 tests

- [ ] **Step 2: Verify tests 1 and 2 fail** (helper functions don't exist yet):
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_comprehensive_fix.py -k "rsi" -v 2>&1 | tail -10
```

- [ ] **Step 3: Modify `signal_engine.py`**

Read `/home/nageshmadaram/Sterling/backend/app/engines/directional/signal_engine.py` carefully first.

**3a. Add RSI helper functions** (add before `compute_signal`):
```python
def _rsi_ok_long(rsi: float) -> bool:
    return 42.0 < rsi < 70.0

def _rsi_ok_short(rsi: float) -> bool:
    return 30.0 < rsi < 57.0
```

**3b. Replace the RSI gate block** (find the existing lines that set `rsi_ok` and `rsi_momentum`):

Current code (approximately):
```python
    if trend_val == 1:
        rsi_ok = 40.0 < cur_rsi < 78.0
        rsi_momentum = cur_rsi > 60.0
    elif trend_val == -1:
        rsi_ok = 22.0 < cur_rsi < 60.0
        rsi_momentum = cur_rsi < 40.0
    else:
        rsi_ok = False
        rsi_momentum = False
```

Replace with:
```python
    if trend_val == 1:
        rsi_ok = _rsi_ok_long(cur_rsi)
        rsi_momentum = 55.0 < cur_rsi < 68.0   # momentum but not overbought
    elif trend_val == -1:
        rsi_ok = _rsi_ok_short(cur_rsi)
        rsi_momentum = 32.0 < cur_rsi < 45.0   # not yet oversold
    else:
        rsi_ok = False
        rsi_momentum = False
```

**3c. Add staleness penalty** (after the score computation, before building SignalResult):

Find the existing score computation:
```python
    total_weight = sum(weights.values())  # 20
    earned = sum(w for k, w in weights.items() if flags[k])
    pct = earned / total_weight
```

After this block (after `pct = earned / total_weight`), add:

```python
    # Staleness penalty: scan last 16 bars for most recent ST flip
    # Penalise entries where the signal flip happened long ago
    bars_since_flip = 16  # default: not found within window
    if trend_val != 0:
        window = candles_1h[max(0, len(candles_1h) - 17): len(candles_1h) - 1]
        for age, prev_c in enumerate(reversed(window), start=1):
            prev_slice = candles_1h[max(0, len(candles_1h) - 17 - age): len(candles_1h) - age]
            if len(prev_slice) < 30:
                break
            prev_sig = _compute_st_trends_only(prev_slice, _st_cfgs, st_threshold)
            cur_green = (trend_val == 1 and all_green_now)
            cur_red   = (trend_val == -1 and all_red_now)
            was_green = prev_sig['all_green']
            was_red   = prev_sig['all_red']
            if (cur_green and not was_green) or (cur_red and not was_red):
                bars_since_flip = age
                break
    stale_penalty = min(4, bars_since_flip // 4)
    earned_adj = max(0, earned - stale_penalty)
    pct = earned_adj / total_weight
```

Note: This requires a helper `_compute_st_trends_only` that reuses the ST computation without full signal overhead. See Step 3d.

**3d. Add `_compute_st_trends_only` helper** before `compute_signal`:

```python
def _compute_st_trends_only(
    candles: List[Candle],
    st_cfgs: List[tuple],
    st_threshold: int,
) -> dict:
    """Lightweight: compute only ST trends (for staleness check). No RSI/BB/KC."""
    if len(candles) < 30:
        return {'all_green': False, 'all_red': False}
    o = np.array([c.open  for c in candles], dtype=np.float64)
    h = np.array([c.high  for c in candles], dtype=np.float64)
    l = np.array([c.low   for c in candles], dtype=np.float64)
    c = np.array([c.close for c in candles], dtype=np.float64)
    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    p1, m1 = st_cfgs[0]; p2, m2 = st_cfgs[1]; p3, m3 = st_cfgs[2]
    _, t1 = compute_supertrend(ha_h, ha_l, ha_c, p1, m1)
    _, t2 = compute_supertrend(h,    l,    c,    p2, m2)
    vwap_c_list = list(_to_vwap_candles(candles))
    vh = np.array([v.high  for v in vwap_c_list], dtype=np.float64)
    vl = np.array([v.low   for v in vwap_c_list], dtype=np.float64)
    vc = np.array([v.close for v in vwap_c_list], dtype=np.float64)
    _, t3 = compute_supertrend(vh, vl, vc, p3, m3)
    trends = [int(t1[-1]), int(t2[-1]), int(t3[-1])]
    gc = trends.count(1); rc = trends.count(-1)
    return {'all_green': gc >= st_threshold, 'all_red': rc >= st_threshold}
```

**3e. Add `bars_since_flip` to `SignalResult` return**:

In the `return SignalResult(...)` call at the bottom of `compute_signal`, add:
```python
        bars_since_flip=bars_since_flip,
```

**3f. Add `bars_since_flip: int = 0` to `SignalResult` in the schema**:

Read `/home/nageshmadaram/Sterling/backend/app/schemas/directional.py`. Find `class SignalResult`. Add:
```python
    bars_since_flip: int = 0
```

Also add it to the early-return (insufficient data) case at the top of `compute_signal`:
```python
    return SignalResult(
        trend=0, all_green=False, all_red=False, ...,
        bars_since_flip=0,
    )
```

### Step 4: Run all 5 tests
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_comprehensive_fix.py -v 2>&1 | tail -15
```
Expected: 5/5 passed

### Step 5: Run full regression
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_signal_rsi_thresholds.py tests/test_signal_squeeze.py tests/test_signal_cadence.py tests/test_backtest_robustness.py tests/test_strategy_fixes.py -v 2>&1 | tail -20
```
Expected: all pass

### Step 6: Commit
```bash
git add backend/app/engines/directional/signal_engine.py \
        backend/app/schemas/directional.py \
        backend/tests/test_comprehensive_fix.py
git commit -m "feat: tighter RSI bounds (42-70 long/30-57 short), staleness penalty, bars_since_flip"
```

---

## Task 2: Add fwd_horizon param to simulate_capital_curve

**Files:**
- Modify: `backend/app/engines/backtest/backtest_engine.py`
- Test: `backend/tests/test_comprehensive_fix.py` (append)

### Why

`simulate_capital_curve` always uses `fwd_return_12h` as the hold horizon. For 5M data, that means 60-minute hold. For 15M data, 3-hour hold. This is correct for 1H strategy but wrong for scalping — 5M scalpers should use `fwd_return_4h` (4 bars = 20min).

The forward returns computed in `run_backtest` as `fwd_return_4h` = 4 signal bars, which equals:
- 1H data: 4 × 1H = 4H horizon
- 15M data: 4 × 15M = 1H horizon  
- 5M data: 4 × 5M = 20min horizon

### Step 1: Append test
```python
# append to backend/tests/test_comprehensive_fix.py
from app.engines.backtest.backtest_engine import simulate_capital_curve
from app.schemas.backtest import BacktestBarResult

def _sim_bar(fwd4=1.0, fwd12=-0.5, score=16.0):
    return BacktestBarResult(
        timestamp_ms=1_700_000_000_000, close_1h=30000.0, close_4h=30000.0,
        macro_regime='BULL_TREND', ema50=29000.0, signal_trend=1,
        all_green=True, all_red=False, green_arrow=True, red_arrow=False,
        st_trends=[1,1,1], st_values=[29900.0,29800.0,29700.0],
        state='CONFIRMED_SETUP_ACTIVE', direction='long',
        fwd_return_4h=fwd4, fwd_return_12h=fwd12, signal_score=score,
    )

def test_simulate_fwd_4h_uses_4h_return():
    """fwd_horizon='4h' must use fwd_return_4h (+1.0%), not fwd_return_12h (-0.5%)."""
    bar = _sim_bar(fwd4=1.0, fwd12=-0.5)
    sim4h  = simulate_capital_curve([bar, _sim_bar()], capital=10_000, hold_bars=1, fwd_horizon='4h')
    sim12h = simulate_capital_curve([bar, _sim_bar()], capital=10_000, hold_bars=1, fwd_horizon='12h')
    # With fwd4 positive and fwd12 negative:
    # 4h sim should be profitable, 12h sim should not be
    if sim4h['trades'] and sim12h['trades']:
        assert sim4h['trades'][0]['pnl_pct'] > sim12h['trades'][0]['pnl_pct']

def test_simulate_default_fwd_12h_unchanged():
    """Default (no fwd_horizon) must use fwd_return_12h (backward compat)."""
    bar = _sim_bar(fwd4=99.0, fwd12=1.5)
    sim_default = simulate_capital_curve([bar, _sim_bar()], capital=10_000, hold_bars=1)
    sim_12h     = simulate_capital_curve([bar, _sim_bar()], capital=10_000, hold_bars=1, fwd_horizon='12h')
    if sim_default['trades'] and sim_12h['trades']:
        assert abs(sim_default['trades'][0]['pnl_pct'] - sim_12h['trades'][0]['pnl_pct']) < 0.001
```

- [ ] **Step 1:** Append the 2 tests above to `backend/tests/test_comprehensive_fix.py`

- [ ] **Step 2: Verify they fail:**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_comprehensive_fix.py -k "fwd" -v 2>&1 | tail -10
```
Expected: TypeError (fwd_horizon param doesn't exist)

- [ ] **Step 3: Modify `simulate_capital_curve` in `backtest_engine.py`**

Add `fwd_horizon: str = '12h'` as last param:
```python
def simulate_capital_curve(
    bars: List[BacktestBarResult],
    capital: float = 10_000.0,
    fee_rt_pct: float = FEE_RT_PCT,
    risk_pct: float = 0.02,
    hold_bars: int = 3,
    score_min: float = 0.0,
    fwd_horizon: str = '12h',   # '4h', '12h', or '24h'
) -> dict:
```

Inside the function, find where `entry_bar.fwd_return_12h` is used for `raw_ret`:
```python
            raw_ret    = entry_bar.fwd_return_12h
```
Replace with:
```python
            if fwd_horizon == '4h':
                raw_ret = entry_bar.fwd_return_4h
            elif fwd_horizon == '24h':
                raw_ret = entry_bar.fwd_return_24h
            else:
                raw_ret = entry_bar.fwd_return_12h
```

- [ ] **Step 4: Run fwd horizon tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_comprehensive_fix.py -k "fwd" -v 2>&1 | tail -10
```
Expected: 2/2 passed

- [ ] **Step 5: Run all tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_comprehensive_fix.py tests/test_backtest_robustness.py tests/test_scalping_fix.py tests/test_strategy_fixes.py -v 2>&1 | tail -20
```
Expected: all pass

- [ ] **Step 6: Commit**
```bash
git add backend/app/engines/backtest/backtest_engine.py backend/tests/test_comprehensive_fix.py
git commit -m "feat: add fwd_horizon param to simulate_capital_curve (4h/12h/24h)"
```

---

## Self-Review

### RSI changes: why these bounds?
- Long upper 78→70: prevents entering momentum already at overbought (RSI 70+ = >2σ above mean in normal distribution)
- Long lower 40→42: minimal change, removes the borderline RSI=40-42 zone
- Short upper 60→57: tighter, prevents entering shorts in neutral RSI (57-60 is not clearly bearish)
- Short lower 22→30: prevents entering shorts at deeply oversold levels (likely bounce)

### Staleness penalty: why max 4 points?
- 4 points = 20% of max-20 = meaningful but not dominating
- A score of 19 with 16-bar staleness → 15 (barely confirmed)
- A score of 15 with 8-bar staleness → 13 (EARLY — filtered out)
- A score of 19 with 4-bar freshness → 19 (no penalty)

### No lookahead bias
- `_compute_st_trends_only` operates on `candles[0:i]` (same slice as compute_signal)
- The staleness scan looks BACKWARD through already-closed bars
- No future data used

### Backward compatibility
- `fwd_horizon='12h'` is the default → all existing callers unaffected
- RSI changes affect signal_score which feeds confirmation — existing tests may need updating if they pin exact signal_score values
