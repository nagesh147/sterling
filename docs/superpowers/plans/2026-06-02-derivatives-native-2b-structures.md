# Derivatives Native Engine — Phase 2b (Defined-Risk Structures) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Give the native engine `defined_risk` capability — build multi-leg debit/credit verticals and iron condors with correct, capped-risk economics, surfaced on candidate rows. No naked exposure; no order execution (deferred to a guarded follow-up).

**Architecture:** A generic expiry-payoff evaluator derives `max_loss`/`max_profit`/breakevens from any set of option legs (one function serves all structure types — DRY). Pure builders pick strikes from the live chain and assemble structures; the native engine routes `risk_posture=defined_risk` to a builder and attaches the result to `DerivativesCandidate.structure`. Rows expose a flat summary so the FE change is minimal.

**Tech Stack:** Python 3.14, Pydantic v2, pytest. Frontend: React + TypeScript (type-sync only this phase).

**Scope boundary (explicit):** This phase does NOT wire multi-leg ORDER execution (Delta India multi-leg/atomicity needs venue verification; sequenced fills carry leg-risk). Structures are built, priced, displayed, and audited only. Auto-execute remains OFF. Visual table rendering of legs rides with the 2c UI phase; 2b keeps the TS row type in sync.

---

## File Structure

- **Modify** `backend/app/engines/derivatives/schemas.py` — add `StructureLeg`, `DerivativesStructure`; add `structure: Optional[DerivativesStructure] = None` to `DerivativesCandidate`.
- **Create** `backend/app/engines/derivatives_native/structures.py` — `compute_economics(...)` + `build_debit_vertical/build_credit_vertical/build_iron_condor`.
- **Modify** `backend/app/engines/derivatives_native/engine.py` — `defined_risk` builds a structure candidate.
- **Modify** `backend/app/api/v1/endpoints/derivatives.py` — `_CandidateRow` gains `structure_summary`/`structure_max_loss_usd`/`structure_max_profit_usd`; `_row_from_decision` populates them.
- **Modify** `backend/tests/test_derivatives_native.py` — structure + builder + engine + row tests.
- **Modify** `frontend/src/hooks/useDerivatives.ts` — add the 3 optional structure fields to `DerivativesCandidateRow`.

---

## Task 1: Structure schemas + candidate field

**Files:**
- Modify: `backend/app/engines/derivatives/schemas.py`
- Test: `backend/tests/test_derivatives_native.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
from app.engines.derivatives.schemas import (
    DerivativesCandidate, DerivativesStructure, StructureLeg,
)


class TestStructureSchema:
    def test_structure_holds_legs_and_economics(self):
        legs = [
            StructureLeg(option_type="call", side="buy", strike=50000, premium=1200, ratio=1),
            StructureLeg(option_type="call", side="sell", strike=52000, premium=600, ratio=1),
        ]
        s = DerivativesStructure(
            structure_type="debit_vertical", underlying="BTC", direction="long",
            legs=legs, contracts=2.0, net_premium_usd=1200.0,
            max_loss_usd=1200.0, max_profit_usd=2800.0, breakevens=[50600.0])
        assert len(s.legs) == 2
        assert s.max_loss_usd == 1200.0
        assert "debit_vertical" in s.summary()
        assert "BC" not in s.summary()  # sanity: summary is human text

    def test_candidate_accepts_structure(self):
        s = DerivativesStructure(
            structure_type="iron_condor", underlying="BTC", direction="neutral", legs=[])
        cand = DerivativesCandidate(
            instrument_type="options", underlying="BTC", entry_price=50000,
            direction="neutral", contracts=1.0, structure=s)
        assert cand.structure is not None
        assert cand.structure.structure_type == "iron_condor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestStructureSchema -v`
Expected: FAIL — `ImportError: cannot import name 'DerivativesStructure'`

- [ ] **Step 3: Add the schemas**

In `backend/app/engines/derivatives/schemas.py`, after the `LiquidityScore` class (before the `# ── Output ──` section), add:

```python
class StructureLeg(BaseModel):
    """One leg of a multi-leg options structure."""
    option_symbol: Optional[str] = None
    option_type: str                         # "call" | "put"
    side: str                                # "buy" | "sell"
    strike: float
    expiry: Optional[str] = None
    dte: Optional[int] = None
    ratio: int = 1                           # contracts for this leg (relative)
    premium: float = 0.0                     # per-contract entry premium (mark/mid)
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0


class DerivativesStructure(BaseModel):
    """A multi-leg defined-risk structure (vertical / iron condor).

    Economics are computed by `derivatives_native.structures.compute_economics`
    and stored here; `net_premium_usd` > 0 = net debit paid, < 0 = net credit
    received. `max_loss_usd` / `max_profit_usd` are positive magnitudes."""
    structure_type: str                      # "debit_vertical"|"credit_vertical"|"iron_condor"
    underlying: str
    direction: str                           # "long"|"short"|"neutral"
    legs: list[StructureLeg] = Field(default_factory=list)
    contracts: float = 1.0
    net_premium_usd: float = 0.0
    max_loss_usd: float = 0.0
    max_profit_usd: float = 0.0
    breakevens: list[float] = Field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"{l.side} {l.ratio}x {l.option_type} {l.strike:g}" for l in self.legs
        ]
        return (f"{self.structure_type} [{' / '.join(parts)}] "
                f"maxLoss=${self.max_loss_usd:,.0f} maxProfit=${self.max_profit_usd:,.0f}")
```

Then add the field to `DerivativesCandidate` — after its `option_type` line (near the top of the class):

```python
    structure: Optional["DerivativesStructure"] = None   # set for multi-leg defined-risk
```

(Place the assignment among the existing optional fields; the forward-ref string is fine since `DerivativesStructure` is defined above in the same module.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestStructureSchema -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/app/engines/derivatives/schemas.py backend/tests/test_derivatives_native.py && git commit -q -m "feat(deriv-native): DerivativesStructure + StructureLeg schemas

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Economics evaluator + structure builders

**Files:**
- Create: `backend/app/engines/derivatives_native/structures.py`
- Test: `backend/tests/test_derivatives_native.py`

**Context:** Expiry P/L of one leg at spot S: long call `max(S−K,0)`, short call `−max(S−K,0)`, long put `max(K−S,0)`, short put `−max(K−S,0)` (× ratio). Entry net debit = Σ(buy:+premium, sell:−premium)×ratio. Total P/L(S) = Σ leg-payoff(S) − net_debit. The payoff is piecewise-linear with extrema at {0, strikes, far}, so evaluating on that grid yields exact max/min and breakevens (linear interpolation of zero-crossings). This one function serves every structure type.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
from app.engines.derivatives_native import structures as st


class TestStructureEconomics:
    def test_debit_call_spread_math(self):
        legs = [
            StructureLeg(option_type="call", side="buy", strike=50000, premium=1200),
            StructureLeg(option_type="call", side="sell", strike=52000, premium=600),
        ]
        net, max_loss, max_profit, bes = st.compute_economics(legs, contracts=1.0)
        assert round(net, 2) == 600.0          # debit paid = 1200 - 600
        assert round(max_loss, 2) == 600.0     # = net debit
        assert round(max_profit, 2) == 1400.0  # width 2000 - debit 600
        assert bes == [50600.0]                 # K1 + debit

    def test_credit_put_spread_math(self):
        legs = [
            StructureLeg(option_type="put", side="sell", strike=49000, premium=800),
            StructureLeg(option_type="put", side="buy", strike=47000, premium=300),
        ]
        net, max_loss, max_profit, bes = st.compute_economics(legs, contracts=1.0)
        assert round(net, 2) == -500.0         # net credit received
        assert round(max_profit, 2) == 500.0   # = credit
        assert round(max_loss, 2) == 1500.0    # width 2000 - credit 500
        assert bes == [48500.0]                 # K_short - credit

    def test_contracts_scale_linearly(self):
        legs = [
            StructureLeg(option_type="call", side="buy", strike=50000, premium=1200),
            StructureLeg(option_type="call", side="sell", strike=52000, premium=600),
        ]
        _, ml1, _, _ = st.compute_economics(legs, contracts=1.0)
        _, ml3, _, _ = st.compute_economics(legs, contracts=3.0)
        assert round(ml3, 2) == round(ml1 * 3, 2)


class TestStructureBuilders:
    def test_build_debit_vertical_long(self):
        s = st.build_debit_vertical(
            chain=_chain_btc(), spot=50000.0, direction="long",
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is not None
        assert s.structure_type == "debit_vertical"
        assert len(s.legs) == 2
        assert s.legs[0].side == "buy" and s.legs[1].side == "sell"
        assert s.legs[1].strike > s.legs[0].strike    # long lower, short higher (call spread)
        assert s.max_loss_usd <= 0.02 * 100_000.0 + 1e-6   # sized to budget
        assert s.max_loss_usd > 0

    def test_build_returns_none_when_strikes_missing(self):
        thin = [o for o in _chain_btc() if o.strike == 50000]   # only 1 strike
        s = st.build_debit_vertical(
            chain=thin, spot=50000.0, direction="long",
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestStructureEconomics tests/test_derivatives_native.py::TestStructureBuilders -v`
Expected: FAIL — `ModuleNotFoundError: ...structures`

- [ ] **Step 3: Implement structures.py**

Create `backend/app/engines/derivatives_native/structures.py`:

```python
"""Defined-risk options structure construction + payoff economics.

`compute_economics` derives net premium, max loss, max profit, and breakevens
from any set of legs by evaluating the piecewise-linear expiry payoff on the
grid {0, strikes, far}. The builders pick strikes from a live chain and size
contracts to a max-loss budget. Pure functions — no I/O, fully unit-testable.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from app.engines.derivatives.schemas import DerivativesStructure, StructureLeg
from app.schemas.market import OptionSummary


def _leg_intrinsic(leg: StructureLeg, s: float) -> float:
    if leg.option_type == "call":
        intr = max(s - leg.strike, 0.0)
    else:
        intr = max(leg.strike - s, 0.0)
    sign = 1.0 if leg.side == "buy" else -1.0
    return sign * intr * leg.ratio


def _net_debit(legs: Sequence[StructureLeg]) -> float:
    """+ = debit paid at entry, - = credit received."""
    return sum((leg.premium if leg.side == "buy" else -leg.premium) * leg.ratio
               for leg in legs)


def compute_economics(legs: Sequence[StructureLeg], contracts: float):
    """Return (net_premium_usd, max_loss_usd, max_profit_usd, breakevens).

    net_premium_usd: + debit / - credit (× contracts).
    max_loss_usd / max_profit_usd: positive magnitudes (× contracts).
    """
    if not legs:
        return 0.0, 0.0, 0.0, []
    net = _net_debit(legs)
    strikes = sorted({leg.strike for leg in legs})
    grid = [0.0] + strikes + [strikes[-1] * 2.0 + 1.0]

    def pnl(s: float) -> float:
        return sum(_leg_intrinsic(leg, s) for leg in legs) - net

    vals = [(s, pnl(s)) for s in grid]
    max_profit = max(v for _, v in vals)
    max_loss = min(v for _, v in vals)            # <= 0 for defined-risk

    breakevens: list[float] = []
    for (s0, p0), (s1, p1) in zip(vals, vals[1:]):
        if p0 == 0.0:
            breakevens.append(round(s0, 2))
        if (p0 < 0.0 < p1) or (p1 < 0.0 < p0):
            be = s0 + (0.0 - p0) * (s1 - s0) / (p1 - p0)
            breakevens.append(round(be, 2))

    return (
        round(net * contracts, 2),
        round(max(0.0, -max_loss) * contracts, 2),
        round(max(0.0, max_profit) * contracts, 2),
        sorted(set(breakevens)),
    )


def _nearest(chain: Sequence[OptionSummary], opt_type: str, target: float) -> Optional[OptionSummary]:
    cands = [o for o in chain if o.option_type == opt_type and o.strike > 0]
    if not cands:
        return None
    return min(cands, key=lambda o: abs(o.strike - target))


def _prem(o: OptionSummary) -> float:
    return o.mark_price if o.mark_price > 0 else o.mid_price


def _size_to_budget(per_contract_max_loss: float, nav_usd: float, max_loss_pct: float) -> float:
    if per_contract_max_loss <= 0:
        return 0.0
    budget = nav_usd * max_loss_pct
    return max(0.01, math.floor((budget / per_contract_max_loss) * 100) / 100)


def _leg_from_option(o: OptionSummary, side: str) -> StructureLeg:
    return StructureLeg(
        option_symbol=o.instrument_name, option_type=o.option_type, side=side,
        strike=o.strike, expiry=o.expiry_date, dte=o.dte, ratio=1, premium=_prem(o),
        delta=o.delta, gamma=o.gamma, vega=o.vega, theta=o.theta)


def build_debit_vertical(
    *, chain: Sequence[OptionSummary], spot: float, direction: str,
    width_pct: float, nav_usd: float, max_loss_pct: float,
) -> Optional[DerivativesStructure]:
    """Bullish → call debit spread (buy ATM, sell OTM higher).
    Bearish → put debit spread (buy ATM, sell OTM lower)."""
    if direction == "long":
        opt_type, long_target, short_target = "call", spot, spot * (1.0 + width_pct)
    else:
        opt_type, long_target, short_target = "put", spot, spot * (1.0 - width_pct)
    long_o = _nearest(chain, opt_type, long_target)
    short_o = _nearest(chain, opt_type, short_target)
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


def build_credit_vertical(
    *, chain: Sequence[OptionSummary], spot: float, direction: str,
    width_pct: float, nav_usd: float, max_loss_pct: float,
) -> Optional[DerivativesStructure]:
    """Bullish → put credit spread (sell OTM put, buy further-OTM put)."""
    if direction == "long":
        opt_type, short_target, long_target = "put", spot * (1.0 - width_pct), spot * (1.0 - 2 * width_pct)
    else:
        opt_type, short_target, long_target = "call", spot * (1.0 + width_pct), spot * (1.0 + 2 * width_pct)
    short_o = _nearest(chain, opt_type, short_target)
    long_o = _nearest(chain, opt_type, long_target)
    if not short_o or not long_o or short_o.strike == long_o.strike:
        return None
    legs = [_leg_from_option(short_o, "sell"), _leg_from_option(long_o, "buy")]
    _, ml1, _, _ = compute_economics(legs, contracts=1.0)
    contracts = _size_to_budget(ml1, nav_usd, max_loss_pct)
    if contracts <= 0:
        return None
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="credit_vertical", underlying=short_o.underlying,
        direction=direction, legs=legs, contracts=contracts,
        net_premium_usd=net, max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)


def build_iron_condor(
    *, chain: Sequence[OptionSummary], spot: float,
    width_pct: float, nav_usd: float, max_loss_pct: float,
) -> Optional[DerivativesStructure]:
    """Neutral: sell OTM put + call, buy further-OTM wings."""
    sp = _nearest(chain, "put", spot * (1.0 - width_pct))
    lp = _nearest(chain, "put", spot * (1.0 - 2 * width_pct))
    sc = _nearest(chain, "call", spot * (1.0 + width_pct))
    lc = _nearest(chain, "call", spot * (1.0 + 2 * width_pct))
    legs_o = [sp, lp, sc, lc]
    if any(o is None for o in legs_o):
        return None
    if len({o.strike for o in legs_o}) < 4:
        return None
    legs = [_leg_from_option(sp, "sell"), _leg_from_option(lp, "buy"),
            _leg_from_option(sc, "sell"), _leg_from_option(lc, "buy")]
    _, ml1, _, _ = compute_economics(legs, contracts=1.0)
    contracts = _size_to_budget(ml1, nav_usd, max_loss_pct)
    if contracts <= 0:
        return None
    net, ml, mp, bes = compute_economics(legs, contracts)
    return DerivativesStructure(
        structure_type="iron_condor", underlying=sp.underlying, direction="neutral",
        legs=legs, contracts=contracts, net_premium_usd=net,
        max_loss_usd=ml, max_profit_usd=mp, breakevens=bes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestStructureEconomics tests/test_derivatives_native.py::TestStructureBuilders -v`
Expected: PASS (5 passed). If `_chain_btc` only has calls (it does), `build_debit_vertical` long works; the credit/condor builders need puts — see Task 2b note below.

- [ ] **Step 5: Extend the test chain with puts (builders need both types)**

The existing `_chain_btc()` is calls-only. Update it so credit/condor tests have puts. Replace the `_chain_btc` body's loop to also emit puts:

```python
def _chain_btc(spot=50000.0) -> list[OptionSummary]:
    """A small tradeable call+put chain around spot (14 DTE, tight spread)."""
    out = []
    for strike in (46000, 47000, 48000, 49000, 50000, 51000, 52000, 53000, 54000):
        for opt_type in ("call", "put"):
            if opt_type == "call":
                intrinsic = max(0.0, spot - strike)
            else:
                intrinsic = max(0.0, strike - spot)
            mark = intrinsic + 1200.0
            out.append(OptionSummary(
                instrument_name=f"{'C' if opt_type=='call' else 'P'}-BTC-{strike}-140625",
                underlying="BTC", strike=float(strike), expiry_date="140625", dte=14,
                option_type=opt_type, bid=mark * 0.985, ask=mark * 1.015,
                mark_price=mark, mid_price=mark, mark_iv=55.0,
                delta=(0.55 if strike <= spot else 0.40) * (1 if opt_type == "call" else -1),
                gamma=0.0006, vega=20.0, theta=-15.0, rho=5.0,
                open_interest=400.0, volume_24h=200.0,
                last_updated_ms=int(time.time() * 1000), spread_pct=0.03))
    return out
```

Add the credit + condor builder assertions:

```python
class TestStructureBuildersFull:
    def test_build_credit_vertical_long(self):
        s = st.build_credit_vertical(
            chain=_chain_btc(), spot=50000.0, direction="long",
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is not None and s.structure_type == "credit_vertical"
        assert s.legs[0].side == "sell" and s.legs[0].option_type == "put"
        assert s.net_premium_usd < 0      # credit received
        assert 0 < s.max_loss_usd <= 0.02 * 100_000.0 + 1e-6

    def test_build_iron_condor(self):
        s = st.build_iron_condor(
            chain=_chain_btc(), spot=50000.0,
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is not None and s.structure_type == "iron_condor"
        assert len(s.legs) == 4
        assert s.net_premium_usd < 0      # net credit
        assert s.max_loss_usd > 0
```

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py -q`
Expected: PASS (all). Note: changing `_chain_btc` must not break Task-4-era `TestNativeOptionsLeg` — those only need ≥1 tradeable call near spot, which the richer chain still provides; re-run confirms.

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/app/engines/derivatives_native/structures.py backend/tests/test_derivatives_native.py && git commit -q -m "feat(deriv-native): structure economics + debit/credit vertical + iron condor builders

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Native engine `defined_risk` wiring

**Files:**
- Modify: `backend/app/engines/derivatives_native/engine.py`
- Test: `backend/tests/test_derivatives_native.py`

**Context:** In 2a, `defined_risk` fell back to long_only with a warning. Now, when `risk_posture == DEFINED_RISK` and an options source is active, build a structure: directional sources (`skew_put` → credit vertical; `vrp_voltiming` with directional signal → debit vertical) — for 2b use a simple rule: `vrp_voltiming` → iron condor (sell vol, neutral); `skew_put` → credit vertical (put-side); default/directional → debit vertical matching `signal.direction`. Attach the structure to a `DerivativesCandidate(instrument_type="options", structure=...)`. The naked tier still falls back with a warning (Phase 2d).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
class TestNativeDefinedRisk:
    def test_vrp_defined_risk_builds_condor(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options is not None and dual.options.status == DecisionStatus.OK
        cand = dual.options.chosen
        assert cand.structure is not None
        assert cand.structure.structure_type == "iron_condor"
        assert cand.structure.max_loss_usd > 0
        # no fallback warning anymore
        assert not any("long_only" in w for w in dual.warnings)

    def test_skew_defined_risk_builds_credit_vertical(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["skew_put"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options.chosen.structure.structure_type == "credit_vertical"

    def test_naked_still_falls_back_with_warning(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.NAKED)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert any("naked" in w.lower() for w in dual.warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestNativeDefinedRisk -v`
Expected: FAIL — condor assertion fails (structure is None; 2a builds a single long option).

- [ ] **Step 3: Wire defined_risk in engine.py**

In `backend/app/engines/derivatives_native/engine.py`, add imports near the top:

```python
from app.engines.derivatives.schemas import DerivativesCandidate
from app.engines.derivatives_native import structures as _structures
```

Add a helper before `decide_both`:

```python
def _defined_risk_candidate(
    *, signal: SignalContext, market: MarketContext,
    profile: StrategyDerivativesProfile, chain: list[OptionSummary], sources: set[str],
) -> Optional[DerivativesCandidate]:
    """Build a defined-risk structure candidate based on the active source.
    Provisional rule (until Phase 1 calibrates): vrp→iron condor (sell vol),
    skew→put credit vertical, else debit vertical matching direction."""
    nav = market.portfolio_value
    max_loss_pct = profile.max_premium_pct_of_account
    width = 0.04
    if "vrp_voltiming" in sources:
        s = _structures.build_iron_condor(
            chain=chain, spot=market.spot, width_pct=width,
            nav_usd=nav, max_loss_pct=max_loss_pct)
    elif "skew_put" in sources:
        s = _structures.build_credit_vertical(
            chain=chain, spot=market.spot, direction=signal.direction,
            width_pct=width, nav_usd=nav, max_loss_pct=max_loss_pct)
    else:
        s = _structures.build_debit_vertical(
            chain=chain, spot=market.spot, direction=signal.direction,
            width_pct=width, nav_usd=nav, max_loss_pct=max_loss_pct)
    if s is None:
        return None
    return DerivativesCandidate(
        rank=0, instrument_type="options", underlying=signal.underlying,
        entry_price=signal.entry, direction=signal.direction,
        contracts=s.contracts, leverage=1.0,
        notional_usd=round(s.contracts * signal.entry, 2),
        premium_usd=round(s.net_premium_usd, 2),
        expected_r=(round(s.max_profit_usd / s.max_loss_usd, 3) if s.max_loss_usd > 0 else 0.0),
        score=1.0, structure=s,
    )
```

Then replace the options-leg block in `decide_both`. The current 2a block is:

```python
    if (sources & {"vrp_voltiming", "skew_put"}) and chain:
        if cfg.risk_posture != RiskPosture.LONG_ONLY:
            warnings.append(
                f"risk_posture={cfg.risk_posture.value} not implemented in 2a; using long_only")
        # Native ignores per-strategy instrument_bias so options aren't suppressed.
        opt_profile = profile.model_copy(update={"instrument_bias": InstrumentBias.AUTO})
        opts = _sel._build_options_candidates(
            signal=signal, market=market, profile=opt_profile, chain=chain)
        if opts:
            options_leg = _frozen_ok(opts[0], reason="native:long_premium", now_ms=now_ms)
            options_leg.alternatives = opts[1:4]
        else:
            options_leg = DerivativesDecision(
                status=DecisionStatus.DEFER,
                reason="no long-premium strike survived tradeability gates",
                code="no_options_candidate", timestamp_ms=now_ms,
            )
```

Replace it with:

```python
    if (sources & {"vrp_voltiming", "skew_put"}) and chain:
        if cfg.risk_posture == RiskPosture.NAKED:
            warnings.append("risk_posture=naked not implemented (Phase 2d); using defined_risk")
        if cfg.risk_posture in (RiskPosture.DEFINED_RISK, RiskPosture.NAKED):
            cand = _defined_risk_candidate(
                signal=signal, market=market, profile=profile, chain=chain, sources=sources)
            if cand is not None:
                options_leg = _frozen_ok(cand, reason="native:defined_risk", now_ms=now_ms)
            else:
                options_leg = DerivativesDecision(
                    status=DecisionStatus.DEFER,
                    reason="no defined-risk structure buildable from chain",
                    code="no_structure", timestamp_ms=now_ms)
        else:
            # long_only: single long premium via the existing builder
            opt_profile = profile.model_copy(update={"instrument_bias": InstrumentBias.AUTO})
            opts = _sel._build_options_candidates(
                signal=signal, market=market, profile=opt_profile, chain=chain)
            if opts:
                options_leg = _frozen_ok(opts[0], reason="native:long_premium", now_ms=now_ms)
                options_leg.alternatives = opts[1:4]
            else:
                options_leg = DerivativesDecision(
                    status=DecisionStatus.DEFER,
                    reason="no long-premium strike survived tradeability gates",
                    code="no_options_candidate", timestamp_ms=now_ms)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py -q`
Expected: PASS (all). The 2a `test_defined_risk_falls_back_to_long_only_with_warning` test will now FAIL (behavior changed). **Update it**: rename to `test_defined_risk_builds_structure` and assert `dual.options.chosen.structure is not None` instead of the warning. Make that edit, then re-run.

- [ ] **Step 5: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/app/engines/derivatives_native/engine.py backend/tests/test_derivatives_native.py && git commit -q -m "feat(deriv-native): defined_risk wiring (condor/credit/debit per source)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Surface structure on rows + TS type sync

**Files:**
- Modify: `backend/app/api/v1/endpoints/derivatives.py`
- Modify: `frontend/src/hooks/useDerivatives.ts`
- Test: `backend/tests/test_derivatives_native.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
class TestStructureRow:
    def test_row_carries_structure_summary(self):
        from app.api.v1.endpoints.derivatives import _row_from_decision
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        row = _row_from_decision(
            signal_id="sig1", signal=_signal(), decision=dual.options)
        assert row.structure_summary is not None
        assert "iron_condor" in row.structure_summary
        assert row.structure_max_loss_usd is not None and row.structure_max_loss_usd > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestStructureRow -v`
Expected: FAIL — `_CandidateRow` has no `structure_summary`.

- [ ] **Step 3: Add row fields + populate**

In `backend/app/api/v1/endpoints/derivatives.py`, add to `_CandidateRow` (after `chain_age_ms`):

```python
    structure_summary: Optional[str] = None
    structure_max_loss_usd: Optional[float] = None
    structure_max_profit_usd: Optional[float] = None
```

In `_row_from_decision`, before the `return _CandidateRow(`, add:

```python
    struct = getattr(c, "structure", None) if c else None
```

and add these kwargs to the `_CandidateRow(...)` construction:

```python
        structure_summary=(struct.summary() if struct else None),
        structure_max_loss_usd=(struct.max_loss_usd if struct else None),
        structure_max_profit_usd=(struct.max_profit_usd if struct else None),
```

- [ ] **Step 4: Sync the TS row type**

In `frontend/src/hooks/useDerivatives.ts`, add to the `DerivativesCandidateRow` interface (after `chain_age_ms`):

```typescript
  structure_summary: string | null;
  structure_max_loss_usd: number | null;
  structure_max_profit_usd: number | null;
```

- [ ] **Step 5: Run tests + tsc**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/test_derivatives_native.py -q`
Expected: PASS (all)
Run: `cd /home/nageshmadaram/Sterling/frontend && npx tsc --noEmit`
Expected: exit 0

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/app/api/v1/endpoints/derivatives.py frontend/src/hooks/useDerivatives.ts backend/tests/test_derivatives_native.py && git commit -q -m "feat(deriv-native): surface structure summary/max-loss on candidate rows + TS sync

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Regression

- [ ] **Step 1: Run the derivatives/native suite**

Run: `cd /home/nageshmadaram/Sterling/backend && .venv/bin/python -m pytest tests/ -k "deriv or selector or native" -q`
Expected: native tests all green; the 4 pre-existing `TestPinningGate`/`TestInstrumentChooser`/`TestSLTPSolver` failures remain (not in scope). No NEW failures.

---

## Self-Review notes

- **Spec coverage (2b):** `DerivativesStructure`/`StructureLeg` (Task 1), defined-risk verticals + condor builders with capped loss (Task 2), engine `defined_risk` wiring (Task 3), row surfacing + FE type sync (Task 4). **Deferred (flagged):** multi-leg ORDER execution and visual table rendering of legs (→ 2c/guarded follow-up).
- **Provisional logic:** the source→structure mapping (vrp→condor, skew→credit, else debit) is a hypothesis until Phase 1 calibrates — documented in `_defined_risk_candidate`.
- **Safety:** every structure has computed `max_loss_usd` (capped, sized to `max_premium_pct_of_account`); naked stays unreachable (falls back with warning); auto-execute OFF; no order plumbing added.
- **Type consistency:** `compute_economics` returns `(net_premium_usd, max_loss_usd, max_profit_usd, breakevens)` consumed identically in builders and engine; `DerivativesStructure` field names match across schema/builders/engine/row.
