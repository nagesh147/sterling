# Sterling Trading Strategy — Comprehensive Improvement Plan

**Goal:** Improve all metrics of the Sterling trading strategy across 5 areas: signal quality, position sizing, entry/exit rules, backtesting & metrics, and risk management.

**Architecture:** Multi-stage improvement across the directional engine stack. Each task is self-contained and produces working, testable code. Tasks are ordered to respect dependencies (signals → sizing → entries/exits → backtesting → risk).

**Tech Stack:** Python 3.11+, numpy, scipy, pydantic, pytest

---

## File Map

| Area | Key Files |
|------|-----------|
| Signal quality | `engines/directional/signal_weights.py`, `engines/directional/signal_features.py` |
| Position sizing | `engines/directional/sizing_engine.py`, `engines/risk/regime_adaptive_sizer.py` |
| Entry/exit | `engines/directional/execution_engine.py`, `engines/directional/trailing_stop.py`, `engines/risk/cooldown.py` |
| Backtesting | `engines/backtest/backtest_mtf.py`, `engines/analytics/performance.py` |
| Risk management | `engines/risk/greeks_budget.py`, `engines/directional/scoring.py`, `engines/directional/structure_selector.py` |

---

## Area 1: Signal Quality

### Task 1: Normalize Signal Weights to Sum to 20

**Files:**
- Modify: `backend/app/engines/directional/signal_weights.py:43-54`
- Modify: `backend/app/engines/directional/signal_engine.py` (imports V4_BASE_WEIGHTS)
- Modify: `backend/app/engines/backtest/backtest_mtf.py` (imports V4_BASE_WEIGHTS)

**Problem:** V4_BASE_WEIGHTS sum to 22, not 20. The `pct × 20` scaling assumes total=20. This creates confusion in `assemble_signal_score` where `earned / 22` is scaled to 0-20.

**Fix:** Reduce `ha_real_aligned` from 3 → 2. Total = 4+2+2+3+3+3+2+2 = 20 ✓

```python
# signal_weights.py:43-54 — replace V4_BASE_WEIGHTS
V4_BASE_WEIGHTS: Dict[str, int] = {
    "st_flip":         4,  # clean reversal — primary signal
    "rsi":             2,  # in band
    "rsi_momentum":    2,  # in momentum zone
    "squeeze":         3,  # BB/KC squeeze breakout
    "volume":          3,  # volume spike
    "ha_aligned":      3,  # HA body matches trend
    "ha_real_aligned": 2,  # HA/real divergence (reduced from 3 to normalize total to 20)
    "mtf_boost":       2,  # aligns with macro
}
V4_TOTAL_WEIGHT: int = sum(V4_BASE_WEIGHTS.values())  # now 20
```

**Test:** `pytest tests/unit/test_signal_weights.py::test_base_weights_sum_to_20 -v` → FAIL → fix → PASS → commit

---

### Task 2: Add Volatility-Adaptive Staleness

**Files:**
- Modify: `backend/app/engines/directional/signal_weights.py:114-117`
- Modify: `backend/app/engines/directional/signal_features.py`
- Modify: `backend/app/engines/directional/signal_engine.py`

**Problem:** Staleness lookback is fixed at 16 bars regardless of volatility regime. In low-vol (slow moves), 16 bars = longer real time = more staleness → should penalize harder. In high-vol, same 16 bars = faster moves = less staleness.

**Fix:** Make staleness lookback adaptive: `effective_lookback = 16 × (50 / atr_percentile)` clamped to [8, 32]. Then compute `staleness = bars_active / effective_lookback`.

```python
# signal_features.py — update staleness_penalty signature
def staleness_penalty(
    closes: np.ndarray,
    bars_active: int,
    atr_percentile: Optional[float] = None,  # NEW param
) -> float:
    lookback = V4_STALENESS_LOOKBACK
    if atr_percentile is not None and atr_percentile > 0:
        factor = max(0.5, min(2.0, 50.0 / atr_percentile))
        lookback = int(round(lookback * factor))
        lookback = max(8, min(32, lookback))
    raw = bars_active / lookback
    return float(min(V4_STALENESS_MAX, raw / V4_STALENESS_DIVISOR))
```

Thread `atr_percentile` through `signal_engine.py` → `assemble_signal_score`.

**Test:** `pytest tests/unit/test_signal_features.py::test_staleness_penalty_adapts_to_volatility -v`

---

### Task 3: Add Signal Coherence Score (ST Channel Agreement)

**Files:**
- Create: `backend/app/engines/directional/signal_coherence.py`
- Modify: `backend/app/engines/directional/signal_engine.py`
- Test: `tests/unit/test_signal_coherence.py`

**Problem:** Signal direction = 0 (mixed) still produces scores. No measurement of how much the 3 ST channels agree.

**Fix:** Add coherence = 1 - (variance_of_trends / max_variance) where max_variance = 2 for 3 values in {-1, 0, 1}. Coherence penalty = max(2.0, (0.8 - coherence) / 0.3 × 2) for coherence < 0.8.

```python
# signal_coherence.py
def compute_coherence(st_trends: list[int]) -> float:
    arr = np.array(st_trends, dtype=np.float64)
    mean_t = float(np.mean(arr))
    variance = float(np.mean((arr - mean_t) ** 2))
    return round(max(0.0, min(1.0, 1.0 - variance / 2.0)), 3)

def coherence_penalty(coherence: float, max_penalty: float = 2.0) -> float:
    if coherence >= 0.8: return 0.0
    if coherence >= 0.5: return round((0.8 - coherence) / 0.3 * max_penalty, 2)
    return max_penalty
```

Apply `coherence_penalty` in `assemble_signal_score` alongside staleness and CVD penalties.

---

## Area 2: Position Sizing

### Task 4: Recalibrate Regime Size Multipliers with Sharpe, Not Win Rate

**Files:**
- Modify: `backend/app/engines/directional/sizing_engine.py:43-59`
- Add: `regime_breakdown_sharpe()` to `analytics/performance.py`
- Test: `tests/unit/test_regime_sizing.py`

**Problem:** Current multipliers assign BULL_TREND ×0.50, BEAR_TREND ×1.0 based on win rate. Win rate = 44% for BULL_TREND but that's misleading — it's the MOST negative Sharpe. Sharpe is the correct metric.

**Fix:** Reorder based on Sharpe proxy (mean / std of pnl per regime):

| Regime | Multiplier | Basis |
|--------|-----------|-------|
| BULL_TREND | 0.25 | negative Sharpe |
| BULLISH | 0.40 | slight edge |
| BULL_TRENDING | 0.40 | slight edge |
| BULL_WEAK | 0.50 | marginally positive |
| BULL_RANGING | 0.75 | mixed |
| VOLATILE | 0.75 | high noise |
| NEUTRAL | 1.0 | anchor |
| RANGING | 1.0 | best Sharpe |
| BEAR_WEAK | 0.75 | close to breakeven |
| BEAR_RANGING | 1.0 | mixed |
| BEARISH | 1.0 | good edge |
| BEAR_TREND | 1.25 | best — compound it |
| BEAR_TRENDING | 1.25 | best — compound it |

```python
_REGIME_SIZE_MULT: Dict[MacroRegime, float] = {
    MacroRegime.IDLE:           0.25,
    MacroRegime.CHOPPY:         0.25,
    MacroRegime.BULL_TREND:     0.25,   # worst edge
    MacroRegime.BULLISH:        0.40,
    MacroRegime.BULL_TRENDING:  0.40,
    MacroRegime.BULL_WEAK:      0.50,
    MacroRegime.BULL_RANGING:   0.75,
    MacroRegime.VOLATILE:       0.75,
    MacroRegime.NEUTRAL:        1.0,
    MacroRegime.RANGING:        1.0,    # anchor — best Sharpe
    MacroRegime.BEAR_WEAK:      0.75,
    MacroRegime.BEAR_RANGING:   1.0,
    MacroRegime.BEARISH:        1.0,
    MacroRegime.BEAR_TREND:     1.25,   # best — compound it
    MacroRegime.BEAR_TRENDING:  1.25,
}
```

Add `regime_breakdown_sharpe()` to `performance.py` that computes Sharpe proxy per regime.

---

### Task 5: Theta-Aware Sizing for Options

**Files:**
- Modify: `backend/app/engines/directional/sizing_engine.py`
- Test: `tests/unit/test_sizing_theta.py`

**Problem:** Sizing is static from entry — options lose value every hour due to theta but sizing ignores DTE.

**Fix:** Add `_theta_haircut(dte)` function:

```python
def _theta_haircut(dte: int) -> float:
    if dte >= 30: return 1.0
    if dte >= 21: return 0.90
    if dte >= 14: return 0.80
    return 0.60
```

Apply in `size_trade()` after computing `target_risk_pct`:

```python
if structure.structure_type != "futures" and structure.legs:
    dte = structure.legs[0].dte if structure.legs else 30
    theta_mult = _theta_haircut(dte)
    if theta_mult < 1.0:
        target_risk_pct *= theta_mult
        notes.append(f"theta_haircut_dte{dte}")
```

---

### Task 6: Smooth Correlation Penalty

**Files:**
- Modify: `backend/app/engines/directional/sizing_engine.py:69-72`
- Test: `tests/unit/test_correlation_penalty.py`

**Problem:** Binary cutoff at |corr| > 0.8 → 0.5×. No smooth transition.

**Fix:** Replace with `penalty = (1 - |corr|)²`:

```python
def _correlation_penalty(max_abs_corr: float) -> float:
    if max_abs_corr <= 0.0: return 1.0
    return (1.0 - min(1.0, max_abs_corr)) ** 2

# At |corr|=0.5 → 0.25 (moderate), |corr|=0.8 → 0.04 (strong), |corr|=1.0 → 0.0
```

---

### Task 7: Kelly Ruin Probability Guard

**Files:**
- Create: `backend/app/engines/directional/kelly_ruin.py`
- Modify: `backend/app/engines/directional/sizing_engine.py`
- Test: `tests/unit/test_kelly_ruin.py`

**Fix:** Add `ruin_probability()` and `size_with_ruin_limit()`:

```python
# kelly_ruin.py
RUIN_PROB_MAX = 0.05  # 5% max acceptable

def ruin_probability(win_rate, avg_win, avg_loss, bankroll_fraction=0.01, n_trades=None):
    edge = win_rate * avg_win - (1 - win_rate) * avg_loss
    if edge <= 0: return 1.0
    variance = win_rate * avg_win**2 + (1 - win_rate) * avg_loss**2
    if variance <= 0: return 0.0
    p_ruin = math.exp(-2 * bankroll_fraction * edge / variance)
    if n_trades: p_ruin = 1.0 - (1.0 - p_ruin) ** n_trades
    return round(p_ruin, 6)

def size_with_ruin_limit(target_risk_pct, capital, win_rate, avg_win, avg_loss, n_trades_estimate=100):
    current_risk = target_risk_pct
    for _ in range(10):
        if ruin_probability(win_rate, avg_win, avg_loss, current_risk, n_trades_estimate) <= RUIN_PROB_MAX:
            return current_risk
        current_risk *= 0.8
    return current_risk
```

In `size_trade()`, after Kelly cap, apply ruin adjustment. If `adjusted < target_risk_pct`, apply it and add `"ruin_adj(5%_max)"` to notes.

---

## Area 3: Entry / Exit Rules

### Task 8: Persist Cooldown State to Redis

**Files:**
- Create: `backend/app/engines/risk/cooldown_redis.py`
- Modify: `backend/app/engines/risk/cooldown.py`
- Test: `tests/unit/test_cooldown_persistence.py`

**Problem:** In-memory `_LAST_EXITS` dict is lost on restart and not shared across workers.

**Fix:** Write-through to Redis. `record_exit()` writes to both `_LAST_EXITS` (primary, in-process) and Redis (cross-worker). `is_blocked()` checks Redis as fallback.

```python
# cooldown_redis.py
_KEY = "sterling:cooldown"
def redis_record(underlying, mode, direction, exit_ts_ms, ttl_seconds=43200):
    r = _get_redis()
    if r: r.setex(f"{_KEY}:{underlying}:{mode}:{direction}", ttl_seconds, str(exit_ts_ms))

def redis_is_blocked(underlying, mode, direction, now_ms, window_ms):
    r = _get_redis()
    if not r: return False
    val = r.get(f"{_KEY}:{underlying}:{mode}:{direction}")
    return val and (now_ms - int(val)) < window_ms
```

Update `cooldown.py` to call Redis on `record_exit()` and fall back to Redis in `is_blocked()` when in-memory misses.

---

### Task 9: Theta-Aware Trailing Stop

**Files:**
- Modify: `backend/app/engines/directional/trailing_stop.py`
- Test: `tests/unit/test_trailing_stop_theta.py`

**Fix:** Add `_theta_aware_breakeven()` to `TrailingStopEngine`:

```python
def _theta_aware_breakeven(self, entry_price, current_price, dte, direction, partial_done):
    if dte >= 30 or not partial_done: return None
    premium = abs(current_price - entry_price)
    if premium <= 0: return None
    daily_theta = premium / max(1, dte)
    safe_lock = 2.0 * daily_theta
    new_be = entry_price + safe_lock if direction == "bullish" else entry_price - safe_lock
    if direction == "bullish" and new_be > entry_price: return new_be
    if direction == "bearish" and new_be < entry_price: return new_be
    return None
```

Call after partial check in `update()`: if `breakeven_set`, check theta adjustment and lift stop.

---

### Task 10: Adaptive Partial Exit Schedule (Volatility-Based)

**Files:**
- Modify: `backend/app/engines/directional/trailing_stop.py`
- Test: `tests/unit/test_adaptive_partial_exits.py`

**Fix:** Replace hard-coded 10%/20% with ATR-adaptive thresholds:

```python
def _adaptive_partial_thresholds(atr_percentile: float) -> tuple[float, float]:
    if atr_percentile <= 25:  return (0.07, 0.14)  # compression — lock in faster
    if atr_percentile <= 60:  return (0.10, 0.20)  # normal
    if atr_percentile <= 85:  return (0.12, 0.24)  # expansion — let winners run
    return (0.15, 0.30)  # hyper — widest targets
```

Use `atr_percentile` from `_atr_percentile()` to select thresholds per tick.

---

## Area 4: Backtesting & Metrics

### Task 11: Audit backtest_mtf.py for Look-Ahead Bias

**Files:**
- Read: `backend/app/engines/backtest/mtf_vectorizer.py`
- Test: `tests/unit/test_mtf_no_lookahead.py`

**Fix:** The reference fix in `backtest_engine.py:70`:
```python
idx_4h = bisect.bisect_right(c4h_ts, current_ts - _4H_MS)
```
Use this as the pattern to check in `mtf_vectorizer.py`. Verify that all regime/signal computations at bar `i` use only bars ≤ `i`. Audit the vectorized path specifically.

---

### Task 12: Add Walk-Forward Integration to Main Backtest

**Files:**
- Create: `backend/app/engines/backtest/walk_forward_runner.py`
- Modify: `backend/app/engines/backtest/backtest_engine.py` (add `--walk-forward` flag)
- Test: `tests/unit/test_walk_forward.py`

**Fix:** Create `run_walk_forward(closes, timestamps, train_bars, test_bars, stride)` that:
1. Rolls forward with train/test windows
2. Computes IS Sharpe and OOS Sharpe per window
3. Returns OOS/IS ratio (overfit indicator: <0.5 = overfit, >0.7 = healthy)

```python
# walk_forward_runner.py
@dataclass
class WalkForwardResult:
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    oos_is_ratio: float  # cap at 5.0
    n_windows: int
    train_sharpes: List[float]
    test_sharpes: List[float]
```

---

### Task 13: Add Options Fee Model to Backtest

**Files:**
- Modify: `backend/app/engines/backtest/costs.py`
- Modify: `backend/app/engines/backtest/backtest_engine.py`
- Test: `tests/unit/test_options_fee_model.py`

**Fix:** Add options-specific fee model:

```python
OPTIONS_MAKER_FEE_PCT = 0.0002   # 0.02% per side
OPTIONS_TAKER_FEE_PCT = 0.0004   # 0.04% per side
OPTIONS_CONTRACT_FEE = 0.65       # $0.65 per contract (round-trip)

def compute_options_round_trip_cost(notional, n_contracts=1):
    return 2 * OPTIONS_TAKER_FEE_PCT * notional + 2 * OPTIONS_CONTRACT_FEE * n_contracts

def estimate_round_trip_cost(notional, structure_type, leverage=1, n_contracts=1):
    if structure_type in SPREAD_TYPES | {"naked_call", "naked_put"}:
        return compute_options_round_trip_cost(notional, n_contracts)
    return notional * (2 * slip_bps / 10_000 + FEE_RT_PCT)  # crypto fallback
```

---

## Area 5: Risk Management

### Task 14: Add Greeks Veto in Scoring

**Files:**
- Create: `backend/app/engines/risk/greeks_checker.py`
- Modify: `backend/app/engines/directional/scoring.py`
- Test: `tests/unit/test_greeks_veto.py`

**Fix:** Create `greeks_veto_reason(structure, open_positions, budget, portfolio_value)` that returns `None` or a veto string like `"delta_breach:0.35>0.30"`.

Add `score_structure_with_greeks()` that wraps `score_structure()` and checks Greeks budget before scoring. If vetoed, return score=0 with veto reason.

```python
# greeks_checker.py
def greeks_veto_reason(structure, open_positions, budget, portfolio_value):
    if structure.structure_type == "futures" or not structure.legs: return None
    leg = structure.legs[0]
    pos_greeks = PositionGreeks(delta=float(getattr(leg,'delta',0)), ...)
    checker = GreeksBudgetChecker(budget, portfolio_value)
    allowed, reason = checker.check(open_positions, pos_greeks, structure.net_premium)
    return None if allowed else reason
```

---

### Task 15: Add Strike Density Check in Structure Selector

**Files:**
- Create: `backend/app/engines/directional/strike_density.py`
- Modify: `backend/app/engines/directional/structure_selector.py`
- Test: `tests/unit/test_strike_density.py`

**Fix:** Create `check_strike_density(strikes, target_strike, max_strike_pct=0.25)` returning `(bool, str)`:

```python
# strike_density.py
MIN_STRIKES_EACH_SIDE = 3

def check_strike_density(strikes, target_strike, max_strike_pct=0.25):
    max_width = target_strike * max_strike_pct
    lower = [s for s in strikes if s < target_strike and (target_strike - s) <= max_width]
    upper = [s for s in strikes if s > target_strike and (s - target_strike) <= max_width]
    if len(lower) < MIN_STRIKES_EACH_SIDE:
        return False, f"strike_density: only {len(lower)} below (need ≥{MIN_STRIKES_EACH_SIDE})"
    if len(upper) < MIN_STRIKES_EACH_SIDE:
        return False, f"strike_density: only {len(upper)} above (need ≥{MIN_STRIKES_EACH_SIDE})"
    return True, "ok"
```

In `structure_selector.py`, call before building each spread type.

---

### Task 16: HMM Integration Decision

**Files:**
- Read: `backend/app/engines/directional/regime_hmm.py`
- Read: `regime_engine.py` (HMM integration path)
- Test: `tests/unit/test_hmm_regime.py`

**Decision:** Run an accuracy comparison: HMM-predicted regime vs heuristic regime across 500+ trades. If HMM improves regime classification accuracy by >10%, integrate it as the primary path (not an override). If not, remove `regime_hmm.py` and clean up references.

---

## Task Dependencies

| Order | Task | Dependencies |
|-------|------|-------------|
| 1 | Normalize signal weights | None |
| 2 | Vol-adaptive staleness | 1 |
| 3 | Signal coherence | 1 |
| 4 | Sharpe-calibrated sizing | None |
| 5 | Theta-aware sizing | 4 |
| 6 | Smooth correlation penalty | 4 |
| 7 | Kelly ruin probability | 4 |
| 8 | Redis cooldown | None |
| 9 | Theta-aware trailing stop | None |
| 10 | Adaptive partial exits | None |
| 11 | Audit look-ahead bias | None |
| 12 | Walk-forward runner | 11 |
| 13 | Options fee model | None |
| 14 | Greeks veto | None |
| 15 | Strike density check | None |
| 16 | HMM decision | None |

---

## Verification Command

```bash
cd backend && pytest tests/unit/ -v --tb=short
```

All tasks produce commit-able changes. Each task has test + implementation + commit.