# Scalping Fix Plan — 5M and 15M Strategy Repair

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Make the strategy actually work at 5M and 15M by: (1) adding fast ST configs tuned for each TF, (2) lowering the ST agreement threshold to 2/3, (3) exposing `st_configs` and `st_threshold` on `run_backtest` so the backtest engine can test these configs.

**Architecture:** Single change to `backtest_engine.py` — thread `st_configs` and `st_threshold` through `run_backtest` into `compute_signal`. No new files needed. Then run a diagnostic script to measure signal count and win rates at both TFs.

**Root causes identified:**
- 5M with 1H configs (7,3)/(14,2)/(21,2): period-7 ST looks back 7×5M=35min — barely faster than the noise
- Requiring 3/3 STs to agree on 5M: almost never happens because the configs are too slow
- Fix: 5M → ST (3,1.5)/(5,1.0)/(8,0.8) + threshold=2; 15M → ST (5,2.0)/(10,1.5)/(14,1.0) + threshold=2

**Tech Stack:** Python (existing backtest engine), pytest

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/app/engines/backtest/backtest_engine.py` — add st_configs/st_threshold to run_backtest |
| Test | `backend/tests/test_scalping_fix.py` — new, TDD |

---

## Task 1: Add st_configs + st_threshold to run_backtest

**Files:**
- Modify: `backend/app/engines/backtest/backtest_engine.py`
- Create: `backend/tests/test_scalping_fix.py`

### Step 1: Write failing tests

```python
# backend/tests/test_scalping_fix.py
import pytest
from tests.conftest import make_candles
from app.engines.backtest.backtest_engine import run_backtest


def test_run_backtest_accepts_st_configs():
    """run_backtest must accept custom st_configs without error."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    scalping_configs = [(3, 1.5), (5, 1.0), (8, 0.8)]
    res = run_backtest("BTC", c4h, c1h, lookback_days=30,
                       sample_every_n_bars=4, st_configs=scalping_configs)
    assert len(res.bars) >= 0   # runs without error


def test_run_backtest_accepts_st_threshold_2():
    """run_backtest with st_threshold=2 should produce >= as many confirmed bars
    as st_threshold=3 (lower threshold = more or equal signals)."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    res3 = run_backtest("BTC", c4h, c1h, lookback_days=30,
                        sample_every_n_bars=4, st_threshold=3)
    res2 = run_backtest("BTC", c4h, c1h, lookback_days=30,
                        sample_every_n_bars=4, st_threshold=2)
    conf3 = res3.stats.confirmed_long_setups + res3.stats.confirmed_short_setups
    conf2 = res2.stats.confirmed_long_setups + res2.stats.confirmed_short_setups
    assert conf2 >= conf3


def test_run_backtest_default_unchanged():
    """Calling without new params returns identical results to before."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    r1 = run_backtest("BTC", c4h, c1h, lookback_days=30, sample_every_n_bars=4)
    r2 = run_backtest("BTC", c4h, c1h, lookback_days=30, sample_every_n_bars=4,
                      st_configs=None, st_threshold=3)
    assert r1.stats.total_bars_evaluated == r2.stats.total_bars_evaluated
    assert r1.stats.green_arrows == r2.stats.green_arrows
```

- [ ] **Step 1:** Create `backend/tests/test_scalping_fix.py` with the 3 tests above

- [ ] **Step 2: Verify tests 1 and 2 fail** (st_configs/st_threshold params don't exist yet):
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_scalping_fix.py -v 2>&1 | tail -15
```
Expected: TypeError on tests 1 and 2; test 3 passes (backward compat trivially passes)

- [ ] **Step 3: Modify `run_backtest` in `backend/app/engines/backtest/backtest_engine.py`**

Read the file. Find `def run_backtest(`:

Current signature:
```python
def run_backtest(
    underlying: str,
    candles_4h: List[Candle],
    candles_1h: List[Candle],
    lookback_days: int,
    sample_every_n_bars: int = 4,
    atm_iv: Optional[float] = None,
    option_dte: int = 30,
) -> BacktestResult:
```

New signature (add at end, before `) -> BacktestResult:`):
```python
def run_backtest(
    underlying: str,
    candles_4h: List[Candle],
    candles_1h: List[Candle],
    lookback_days: int,
    sample_every_n_bars: int = 4,
    atm_iv: Optional[float] = None,
    option_dte: int = 30,
    st_configs: Optional[List[tuple]] = None,
    st_threshold: int = 3,
) -> BacktestResult:
```

Add `Optional` and `List` to the typing import if not already there (they are).

Inside `run_backtest`, find the line that calls `compute_signal`:
```python
        signal = compute_signal(c1h_slice)
```
Replace with:
```python
        signal = compute_signal(c1h_slice,
                                st_configs=st_configs,
                                st_threshold=st_threshold)
```

That's the only change needed inside the function.

- [ ] **Step 4: Run all 3 tests**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_scalping_fix.py -v 2>&1 | tail -15
```
Expected: 3/3 passed

- [ ] **Step 5: Regression**
```bash
cd /home/nageshmadaram/Sterling/backend && python -m pytest tests/test_backtest_robustness.py tests/test_strategy_fixes.py tests/test_backtest_mtf.py -v 2>&1 | tail -15
```
Expected: all pass

- [ ] **Step 6: Commit**
```bash
git add backend/app/engines/backtest/backtest_engine.py backend/tests/test_scalping_fix.py
git commit -m "feat: add st_configs and st_threshold params to run_backtest for TF-specific signal tuning"
```

---

## Self-Review

- `st_configs=None` and `st_threshold=3` are the defaults, making this fully backward-compatible
- The change is 2 lines inside the function body + 2 params in the signature
- All existing callers (backtest endpoint, tests, sweep.py) pass no new args → unaffected
