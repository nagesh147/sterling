# Derivatives Structuring Revamp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make each engine's armed signal reliably become a correctly-structured futures position (Slice 1) and a delta-targeted options structure (Slice 2), per its `StrategyDerivativesProfile`, deferring only on REAL quality gates — not spuriously. Alpha/signals untouched.

**Architecture:** In-place revamp of the derivatives translation layer. Slice 1 sanitizes the futures stop in `selector._futures_candidate` (ATR fallback in the signal direction) so `solve_futures` stops spuriously rejecting valid signals. Slice 2 adds a delta-targeted debit-vertical builder + real liquidity/spread/premium gates, wired into the native engine's options leg. Per-engine differentiation comes entirely from the profile.

**Tech Stack:** Python, pytest. Touches `app/engines/derivatives/selector.py`, `app/engines/derivatives_native/structures.py`, `app/engines/derivatives_native/engine.py`. Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest <files> -q`.

**Honesty invariants:** real gates (funding/spread/OI/volume/premium) retained; no forced rows; no alpha changes; auto-exec default-OFF.

## File structure

- `app/engines/derivatives/selector.py` — add `_sane_futures_stop()`; modify `_futures_candidate()`. (Slice 1)
- `app/engines/derivatives_native/structures.py` — add `_nearest_by_delta()` + `build_delta_debit_vertical()`. (Slice 2)
- `app/engines/derivatives_native/engine.py` — modify `_defined_risk_candidate()` directional branch to use the delta builder. (Slice 2)
- `backend/tests/test_derivatives_structuring.py` — new test file for both slices.

---

## SLICE 1 — Futures structuring (the empty-futures fix)

### Task 1: `_sane_futures_stop` helper

**Files:**
- Modify: `backend/app/engines/derivatives/selector.py`
- Test: `backend/tests/test_derivatives_structuring.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_derivatives_structuring.py`:

```python
"""Derivatives structuring revamp — futures stop sanitization + delta options."""
from __future__ import annotations

import pytest

from app.engines.derivatives.selector import _sane_futures_stop


def test_sane_stop_keeps_valid_stop():
    # long, stop below entry → unchanged
    assert _sane_futures_stop("long", entry=100.0, stop=95.0, atr=2.0) == 95.0
    # short, stop above entry → unchanged
    assert _sane_futures_stop("short", entry=100.0, stop=105.0, atr=2.0) == 105.0


def test_sane_stop_atr_fallback_when_stop_equals_entry():
    # long, stop==entry (zero distance, the collector's fallback) → ATR stop below
    s = _sane_futures_stop("long", entry=100.0, stop=100.0, atr=2.0, k=1.5)
    assert s == pytest.approx(97.0)        # 100 - 1.5*2
    # short → ATR stop above
    s = _sane_futures_stop("short", entry=100.0, stop=100.0, atr=2.0, k=1.5)
    assert s == pytest.approx(103.0)


def test_sane_stop_atr_fallback_when_wrong_side_or_missing():
    # long with stop ABOVE entry (wrong side) → ATR fallback
    assert _sane_futures_stop("long", entry=100.0, stop=110.0, atr=2.0, k=1.5) == pytest.approx(97.0)
    # missing stop → ATR fallback
    assert _sane_futures_stop("short", entry=100.0, stop=None, atr=2.0, k=1.5) == pytest.approx(103.0)


def test_sane_stop_none_when_no_atr_and_bad_stop():
    # bad stop AND no usable atr → cannot derive → None
    assert _sane_futures_stop("long", entry=100.0, stop=100.0, atr=0.0) is None
    assert _sane_futures_stop("long", entry=100.0, stop=None, atr=0.0) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -q`
Expected: FAIL — `ImportError: cannot import name '_sane_futures_stop'`.

- [ ] **Step 3: Implement the helper**

In `backend/app/engines/derivatives/selector.py`, add near the top (after imports, before `_futures_candidate`):

```python
def _sane_futures_stop(direction: str, *, entry: float, stop, atr: float,
                       k: float = 1.5):
    """Return a geometrically-valid stop for a futures entry, or None.

    A valid stop is on the protective side of entry (below for long, above for
    short) with non-zero distance. When the supplied stop is missing / equal to
    entry / on the wrong side, fall back to an ATR-based stop in the signal's
    direction (entry ∓ k·atr). Returns None only when no stop can be derived
    (bad stop AND atr ≤ 0). This eliminates the spurious sl_tp rejects that left
    the futures table empty, while never inventing a stop with no risk basis."""
    is_long = direction == "long"
    valid = (
        stop is not None and stop > 0 and
        ((is_long and stop < entry) or (not is_long and stop > entry))
    )
    if valid:
        return float(stop)
    if atr and atr > 0 and entry > 0:
        return entry - k * atr if is_long else entry + k * atr
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/app/engines/derivatives/selector.py backend/tests/test_derivatives_structuring.py
git commit -m "feat(derivatives): _sane_futures_stop — ATR fallback for missing/bad stops

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wire the sane stop into `_futures_candidate`

**Files:**
- Modify: `backend/app/engines/derivatives/selector.py` (`_futures_candidate`)
- Test: `backend/tests/test_derivatives_structuring.py`

- [ ] **Step 1: Write the failing test (append)**

```python
from app.engines.derivatives.selector import _futures_candidate
from app.engines.derivatives.profiles import get_profile
from app.engines.derivatives.schemas import SignalContext
from app.schemas.market import MarketContext


def _mkt(spot=62000.0):
    return MarketContext(spot=spot, underlying="BTC", funding_8h_pct=0.0001,
                         portfolio_value=500.0)


def _sig(direction="short", entry=62000.0, stop=62000.0, atr=600.0, tp=None):
    # stop==entry reproduces the collector's zero-distance fallback that DEFERed.
    return SignalContext(strategy="directional", underlying="BTC",
                         direction=direction, entry=entry, stop_loss=stop,
                         take_profit=tp, atr=atr, rr_target=2.0, signal_score=70.0,
                         signal_strength="SIGNAL", presized=False)


def test_futures_candidate_built_despite_zero_distance_stop():
    # Was: stop==entry → solve_futures rejects → DEFER → empty table.
    # Now: ATR fallback gives a real stop → a futures candidate is produced.
    cand = _futures_candidate(signal=_sig(), market=_mkt(), profile=get_profile("directional"))
    assert cand is not None
    assert cand.instrument_type == "futures"
    assert cand.direction == "short"
    assert cand.stop_loss is not None and cand.stop_loss > cand.entry_price  # short stop above
    assert cand.contracts > 0


def test_futures_candidate_none_when_no_atr_and_bad_stop():
    cand = _futures_candidate(signal=_sig(atr=0.0), market=_mkt(),
                              profile=get_profile("directional"))
    assert cand is None      # honest: no risk basis derivable
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -k futures_candidate -q`
Expected: FAIL — `test_futures_candidate_built_despite_zero_distance_stop` fails (returns None today).

- [ ] **Step 3: Modify `_futures_candidate`**

In `selector.py`, replace the opening of `_futures_candidate` (the `sl_plan = sl_tp_solver.solve_futures(...)` block) with a version that sanitizes the stop for non-validated signals and derives a TP if missing:

```python
    # Non-validated (directional/scalping) signals may carry a missing / zero-
    # distance / wrong-side stop (e.g. the directional collector sets stop=entry
    # when the snapshot lacks one). Sanitize via ATR so a real armed signal isn't
    # spuriously rejected. Validated (edge) signals keep their proven geometry.
    if signal.presized:
        stop = signal.stop_loss
    else:
        stop = _sane_futures_stop(signal.direction, entry=signal.entry,
                                  stop=signal.stop_loss, atr=signal.atr)
        if stop is None:
            log.info("futures: no derivable stop for %s (atr=%.4f)",
                     signal.underlying, signal.atr or 0.0)
            return None

    take_profit = signal.take_profit
    if not signal.presized and (not take_profit or take_profit <= 0):
        sd = abs(signal.entry - stop)
        take_profit = (signal.entry + signal.rr_target * sd
                       if signal.direction == "long"
                       else signal.entry - signal.rr_target * sd)

    sl_plan = sl_tp_solver.solve_futures(
        direction=signal.direction, entry=signal.entry,
        structure_stop=stop, atr_val=signal.atr,
        take_profit=take_profit, rr=signal.rr_target,
        validated=signal.presized,
    )
    if not sl_plan.ok:
        log.info("futures sl_tp rejected for %s: %s", signal.underlying, sl_plan.reason)
        return None
```

(This replaces the original `sl_plan = sl_tp_solver.solve_futures(... structure_stop=signal.stop_loss ... take_profit=signal.take_profit ...)` + `if not sl_plan.ok` block. The rest of `_futures_candidate` — funding gate, leverage, sizing, the `DerivativesCandidate(...)` return — is unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -k futures -q`
Expected: PASS.

- [ ] **Step 5: Regression — existing derivatives suites green**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_native.py tests/test_phase7_dual_tables.py tests/test_phase0_derivatives_fixes.py tests/test_candidates_from_cache.py -q`
Expected: all pass (the validated/edge path is unchanged; only non-validated stop handling changed).

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/app/engines/derivatives/selector.py backend/tests/test_derivatives_structuring.py
git commit -m "fix(derivatives): futures leg uses ATR-fallback stop for non-validated signals

Eliminates the spurious sl_tp_reject (stop==entry) that left the futures table
empty for armed directional signals. Validated (edge) geometry untouched. DEFER
only when no stop is derivable (atr<=0) or the real funding gate trips.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## SLICE 2 — Options structuring (delta-targeted)

### Task 3: `_nearest_by_delta` + `build_delta_debit_vertical`

**Files:**
- Modify: `backend/app/engines/derivatives_native/structures.py`
- Test: `backend/tests/test_derivatives_structuring.py`

- [ ] **Step 1: Write the failing test (append)**

```python
from app.schemas.market import OptionSummary
from app.engines.derivatives_native.structures import build_delta_debit_vertical


def _opt(strike, otype, delta, dte=21, bid=100.0, ask=104.0, oi=50.0, vol=20.0):
    mid = (bid + ask) / 2
    return OptionSummary(
        instrument_name=f"BTC-{otype}-{int(strike)}", underlying="BTC",
        strike=strike, expiry_date="2026-07-01", dte=dte, option_type=otype,
        bid=bid, ask=ask, mark_price=mid, mid_price=mid, mark_iv=0.5,
        delta=delta, open_interest=oi, volume_24h=vol, last_updated_ms=0,
        gamma=0.0001, vega=10.0, theta=-5.0)


def _put_chain():
    # puts with deltas spanning the target; dte in window
    return [_opt(60000, "put", -0.30), _opt(58000, "put", -0.55),
            _opt(56000, "put", -0.70), _opt(54000, "put", -0.20)]


def test_delta_debit_vertical_short_picks_target_delta_long_leg():
    s = build_delta_debit_vertical(
        chain=_put_chain(), spot=58000.0, direction="short",
        target_delta=0.55, width_delta=0.25, dte_min=7, dte_max=45,
        nav_usd=500.0, max_loss_pct=0.02,
        max_spread_pct=0.10, min_oi=1.0, min_volume=1.0)
    assert s is not None
    assert s.structure_type == "debit_vertical"
    # long leg ≈ |delta| 0.55 (strike 58000), short leg further OTM (lower |delta|)
    long_leg = next(l for l in s.legs if l.side == "buy")
    short_leg = next(l for l in s.legs if l.side == "sell")
    assert long_leg.strike == 58000
    assert abs(short_leg.delta) < abs(long_leg.delta)   # short leg further OTM
    assert s.contracts > 0


def test_delta_debit_vertical_defers_on_wide_spread():
    wide = [_opt(58000, "put", -0.55, bid=50.0, ask=150.0),   # 100% spread
            _opt(56000, "put", -0.30, bid=50.0, ask=150.0)]
    s = build_delta_debit_vertical(
        chain=wide, spot=58000.0, direction="short", target_delta=0.55,
        width_delta=0.25, dte_min=7, dte_max=45, nav_usd=500.0, max_loss_pct=0.02,
        max_spread_pct=0.10, min_oi=1.0, min_volume=1.0)
    assert s is None      # spread gate


def test_delta_debit_vertical_defers_on_low_oi():
    thin = [_opt(58000, "put", -0.55, oi=0.0), _opt(56000, "put", -0.30, oi=0.0)]
    s = build_delta_debit_vertical(
        chain=thin, spot=58000.0, direction="short", target_delta=0.55,
        width_delta=0.25, dte_min=7, dte_max=45, nav_usd=500.0, max_loss_pct=0.02,
        max_spread_pct=0.10, min_oi=1.0, min_volume=1.0)
    assert s is None      # OI gate
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -k delta_debit -q`
Expected: FAIL — `ImportError: cannot import name 'build_delta_debit_vertical'`.

- [ ] **Step 3: Implement in `structures.py`**

Add after `_nearest`:

```python
def _spread_pct(o: OptionSummary) -> float:
    mid = o.mid_price if o.mid_price > 0 else (o.bid + o.ask) / 2
    return ((o.ask - o.bid) / mid) if mid > 0 else 1.0


def _tradeable(o: OptionSummary, *, max_spread_pct: float, min_oi: float,
               min_volume: float, dte_min: int, dte_max: int) -> bool:
    return (dte_min <= o.dte <= dte_max
            and o.open_interest >= min_oi
            and o.volume_24h >= min_volume
            and _spread_pct(o) <= max_spread_pct
            and o.strike > 0 and (o.mark_price > 0 or o.mid_price > 0))


def _nearest_by_delta(chain, opt_type, target_abs_delta, *, max_spread_pct,
                      min_oi, min_volume, dte_min, dte_max):
    cands = [o for o in chain if o.option_type == opt_type
             and _tradeable(o, max_spread_pct=max_spread_pct, min_oi=min_oi,
                            min_volume=min_volume, dte_min=dte_min, dte_max=dte_max)]
    if not cands:
        return None
    return min(cands, key=lambda o: abs(abs(o.delta) - target_abs_delta))


def build_delta_debit_vertical(
    *, chain, spot: float, direction: str, target_delta: float,
    width_delta: float, dte_min: int, dte_max: int, nav_usd: float,
    max_loss_pct: float, max_spread_pct: float, min_oi: float, min_volume: float,
):
    """Delta-targeted directional debit spread. Long leg ≈ `target_delta`; short
    leg `width_delta` further OTM (lower |delta|). Call spread for long, put
    spread for short. Returns None (→ DEFER) only on real gates: no tradeable
    strike near the target delta within the DTE window / liquidity / spread, or
    a zero-contract size after the premium-budget cap."""
    opt_type = "call" if direction == "long" else "put"
    gate = dict(max_spread_pct=max_spread_pct, min_oi=min_oi,
                min_volume=min_volume, dte_min=dte_min, dte_max=dte_max)
    long_o = _nearest_by_delta(chain, opt_type, target_delta, **gate)
    short_o = _nearest_by_delta(chain, opt_type, max(0.05, target_delta - width_delta), **gate)
    if not long_o or not short_o or long_o.strike == short_o.strike:
        return None
    legs = [_leg_from_option(long_o, "buy"), _leg_from_option(short_o, "sell")]
    _, ml1, _, _ = compute_economics(legs, contracts=1.0)
    contracts = _size_to_budget(ml1, nav_usd, max_loss_pct)
    if contracts <= 0:
        return None
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="debit_vertical", underlying=long_o.underlying,
        direction=direction, legs=legs, contracts=contracts,
        net_premium_usd=net, max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -k delta_debit -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/app/engines/derivatives_native/structures.py backend/tests/test_derivatives_structuring.py
git commit -m "feat(derivatives): delta-targeted debit vertical + liquidity/spread/DTE gates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Wire the delta builder into the native engine's directional options leg

**Files:**
- Modify: `backend/app/engines/derivatives_native/engine.py` (`_defined_risk_candidate`)
- Test: `backend/tests/test_derivatives_structuring.py`

- [ ] **Step 1: Write the failing test (append)**

```python
from app.engines.derivatives_native.engine import _defined_risk_candidate


def test_defined_risk_uses_delta_targeting_for_directional():
    prof = get_profile("directional")   # target_delta 0.60, dte 14-45
    cand = _defined_risk_candidate(
        signal=_sig(direction="short"), market=_mkt(spot=58000.0),
        profile=prof,
        chain=[_opt(58000, "put", -0.60), _opt(55000, "put", -0.35)],
        sources={"directional_options"})
    assert cand is not None
    assert cand.instrument_type == "options"
    assert cand.structure is not None and cand.structure.structure_type == "debit_vertical"
    assert cand.direction == "short"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -k defined_risk -q`
Expected: FAIL — current `_defined_risk_candidate` uses the strike-based `build_debit_vertical` (ATM, no delta targeting); with this chain (no ATM-at-spot call/put pair matching the old width logic) it returns None or a non-delta structure. (If it happens to pass, the test still pins the delta-targeted path once Step 3 lands.)

- [ ] **Step 3: Modify the directional branch of `_defined_risk_candidate`**

In `engine.py`, replace the `else:` branch (the directional `build_debit_vertical` call) with the delta-targeted builder driven by the profile:

```python
    else:
        s = _structures.build_delta_debit_vertical(
            chain=chain, spot=market.spot, direction=signal.direction,
            target_delta=profile.target_delta,
            width_delta=max(0.15, profile.target_delta - 0.30),
            dte_min=profile.dte_min, dte_max=profile.dte_max,
            nav_usd=nav, max_loss_pct=max_loss_pct,
            max_spread_pct=profile.max_spread_pct,
            min_oi=profile.min_oi, min_volume=profile.min_volume_24h_x_contract,
        )
```

(The `vrp_voltiming`→iron_condor and `skew_put`→credit_vertical branches are unchanged. `width` local var is now unused by this branch — leave it for the other branches.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py -k defined_risk -q`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_native.py tests/test_phase7_dual_tables.py tests/test_phase1_options_lifecycle.py tests/test_candidates_from_cache.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling
git add backend/app/engines/derivatives_native/engine.py backend/tests/test_derivatives_structuring.py
git commit -m "feat(derivatives): native options leg uses profile-driven delta-targeted spread

Directional options now build a delta-targeted debit vertical from each engine's
profile (target_delta/dte/spread/OI), instead of the strike-based ATM heuristic.
Per-engine character (Sterling near-ATM short-DTE vs Grok slightly-ITM long-DTE)
flows from the profile. vrp/skew/GEX postures unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: End-to-end verification (live, both legs)

- [ ] **Step 1: Full suite for the touched area**

Run: `cd backend && PYTHONWARNINGS=ignore .venv/bin/python -m pytest tests/test_derivatives_structuring.py tests/test_derivatives_native.py tests/test_phase7_dual_tables.py tests/test_phase0_derivatives_fixes.py tests/test_phase1_options_lifecycle.py tests/test_candidates_from_cache.py -q`
Expected: all green.

- [ ] **Step 2: In-process end-to-end** (mirrors `/tmp/probe7.py`): an armed BTC short → `decide_both` → assert `dual.futures.status == OK and dual.futures.chosen` (Slice 1) AND, with a live/fixture chain, `dual.options.status == OK and dual.options.chosen` is a `debit_vertical` (Slice 2). Capture the futures + options candidate.

- [ ] **Step 3: Restart the `:8000` server** and confirm `/api/v1/derivatives/candidates/futures` and `/candidates/options` now return rows for armed signals (futures no longer all-DEFER). Report the counts.

---

## Self-review

- **Spec coverage:** Slice 1 futures sanitization (Tasks 1–2) ✓; Slice 2 delta-targeted options + gates (Tasks 3–4) ✓; per-engine via profile (Task 4 reads `profile.target_delta/dte/spread/oi`) ✓; honesty gates retained (`_tradeable` keeps spread/OI/volume/DTE; funding gate untouched in `_futures_candidate`) ✓; e2e verify (Task 5) ✓.
- **Placeholder scan:** every step has complete code; the one "if it happens to pass" note in Task 4 Step 1 is a real TDD caveat, not a placeholder — the test pins the post-Step-3 behavior either way.
- **Type consistency:** `_sane_futures_stop(direction, *, entry, stop, atr, k)` used identically in Task 2; `build_delta_debit_vertical(...)` signature in Task 3 matches the call in Task 4; `OptionSummary`/`DerivativesStructure`/`DerivativesCandidate` fields match the schemas read from source.
