# Derivatives Native Engine — Phase 2a (Core MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `native` derivatives engine mode that emits both a futures leg and long-premium option legs per active alpha-source — bypassing the routing-gate's instrument veto — selectable via a global engine config, with `routing_gate` remaining the default (zero behavior change until flipped).

**Architecture:** New `app/engines/derivatives_native/` package returns the *existing* output contract (`DualDerivativesDecision`/`DerivativesCandidate`), so FE tables, freeze-tokens, and `/execute` are unchanged. The producer swap happens at one site — `_both_rows` in `derivatives.py` — chosen by `app.state.derivatives_engine_config.engine_mode`. The native engine reuses the existing futures/options candidate builders but skips `instrument_chooser` (the routing veto), emitting legs gated only by tradeability + risk posture.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, pytest. Frontend: React + TypeScript.

---

## File Structure

- **Create** `backend/app/engines/derivatives_native/__init__.py` — package exports.
- **Create** `backend/app/engines/derivatives_native/config.py` — `EngineMode`/`RiskPosture` enums, `DerivativesEngineConfig` model, `get_engine_config(app)` / `set_engine_config(app, cfg)`.
- **Create** `backend/app/engines/derivatives_native/engine.py` — `decide_both(...)` / `decide(...)` producing the existing decision schemas.
- **Modify** `backend/app/api/v1/endpoints/derivatives.py` — `_both_rows` producer swap; add `GET/POST /config/engine`.
- **Create** `backend/tests/test_derivatives_native.py` — config + engine + producer-swap tests.
- **Modify** `frontend/src/hooks/useDerivatives.ts` — fetch/patch engine config.
- **Modify** `frontend/src/components/derivatives/DerivativesPanel.tsx` — mode toggle + source checkboxes + risk-tier selector.

Reused (not modified): `app/engines/derivatives/selector.py` (`_futures_candidate`, `_build_options_candidates`), `schemas.py`, `profiles.py`, `freeze_token.py`, `services/db.py` (`get_config`/`set_config`).

---

## Task 1: Engine config model + enums

**Files:**
- Create: `backend/app/engines/derivatives_native/__init__.py`
- Create: `backend/app/engines/derivatives_native/config.py`
- Test: `backend/tests/test_derivatives_native.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_derivatives_native.py`:

```python
"""Phase 2a — native derivatives engine: config, engine, producer swap."""
from __future__ import annotations

import time
import pytest

from app.engines.derivatives_native.config import (
    ALPHA_SOURCES, DerivativesEngineConfig, EngineMode, RiskPosture,
)


class TestEngineConfig:
    def test_defaults(self):
        c = DerivativesEngineConfig()
        assert c.engine_mode == EngineMode.ROUTING_GATE
        assert c.active_alpha_sources == ["directional_futures"]
        assert c.risk_posture == RiskPosture.LONG_ONLY
        assert c.validation_method == 1

    def test_rejects_unknown_alpha_source(self):
        with pytest.raises(ValueError):
            DerivativesEngineConfig(active_alpha_sources=["directional_futures", "bogus"])

    def test_rejects_bad_validation_method(self):
        with pytest.raises(ValueError):
            DerivativesEngineConfig(validation_method=4)

    def test_alpha_sources_constant(self):
        assert ALPHA_SOURCES == {
            "directional_futures", "vrp_voltiming", "skew_put", "gex_pinning"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestEngineConfig -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.engines.derivatives_native'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/engines/derivatives_native/__init__.py`:

```python
"""Native derivatives engine — generates its own futures + option legs,
bypassing the routing-gate instrument veto. Returns the existing
DualDerivativesDecision contract so downstream (FE, /execute) is unchanged."""
```

Create `backend/app/engines/derivatives_native/config.py`:

```python
"""Global (engine-level) derivatives config. Distinct from the per-strategy
`profile_overrides`: this picks WHICH engine produces candidates and how it
behaves (active alpha sources, risk posture, validation method)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EngineMode(str, Enum):
    ROUTING_GATE = "routing_gate"   # existing selector.decide_both (default)
    NATIVE = "native"               # new native_engine.decide_both


class RiskPosture(str, Enum):
    LONG_ONLY = "long_only"         # buy premium only (max loss = premium)
    DEFINED_RISK = "defined_risk"   # + spreads/condors (Phase 2b)
    NAKED = "naked"                 # + short options (Phase 2d, opt-in)


ALPHA_SOURCES = {"directional_futures", "vrp_voltiming", "skew_put", "gex_pinning"}


class DerivativesEngineConfig(BaseModel):
    engine_mode: EngineMode = EngineMode.ROUTING_GATE
    active_alpha_sources: list[str] = Field(
        default_factory=lambda: ["directional_futures"])
    risk_posture: RiskPosture = RiskPosture.LONG_ONLY
    validation_method: int = 1      # 1=calibrate-live, 2=real-only, 3=snapshot

    @field_validator("active_alpha_sources")
    @classmethod
    def _known_sources(cls, v: list[str]) -> list[str]:
        bad = set(v) - ALPHA_SOURCES
        if bad:
            raise ValueError(f"unknown alpha sources: {sorted(bad)}")
        return v

    @field_validator("validation_method")
    @classmethod
    def _valid_method(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("validation_method must be 1, 2 or 3")
        return v
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestEngineConfig -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/derivatives_native/__init__.py backend/app/engines/derivatives_native/config.py backend/tests/test_derivatives_native.py
git commit -m "feat(deriv-native): add DerivativesEngineConfig model + enums"
```

---

## Task 2: Config accessors (lazy-seed from DB + persist)

**Files:**
- Modify: `backend/app/engines/derivatives_native/config.py`
- Test: `backend/tests/test_derivatives_native.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
from app.engines.derivatives_native.config import get_engine_config, set_engine_config


class _FakeState:
    pass


class _FakeApp:
    def __init__(self):
        self.state = _FakeState()


class TestEngineConfigAccessors:
    def test_get_seeds_default_when_absent(self, monkeypatch):
        import app.engines.derivatives_native.config as cfgmod
        monkeypatch.setattr(cfgmod, "get_config", lambda key, default="": "")
        app = _FakeApp()
        c = get_engine_config(app)
        assert c.engine_mode == EngineMode.ROUTING_GATE
        # cached on app.state
        assert app.state.derivatives_engine_config is c

    def test_set_persists_and_caches(self, monkeypatch):
        import app.engines.derivatives_native.config as cfgmod
        saved = {}
        monkeypatch.setattr(cfgmod, "set_config",
                            lambda key, value: saved.__setitem__(key, value))
        app = _FakeApp()
        cfg = DerivativesEngineConfig(engine_mode=EngineMode.NATIVE)
        out = set_engine_config(app, cfg)
        assert out.engine_mode == EngineMode.NATIVE
        assert app.state.derivatives_engine_config.engine_mode == EngineMode.NATIVE
        assert "derivatives_engine_config" in saved
        assert "native" in saved["derivatives_engine_config"]

    def test_get_loads_persisted(self, monkeypatch):
        import app.engines.derivatives_native.config as cfgmod
        raw = DerivativesEngineConfig(engine_mode=EngineMode.NATIVE).model_dump_json()
        monkeypatch.setattr(cfgmod, "get_config", lambda key, default="": raw)
        app = _FakeApp()
        c = get_engine_config(app)
        assert c.engine_mode == EngineMode.NATIVE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestEngineConfigAccessors -v`
Expected: FAIL — `ImportError: cannot import name 'get_engine_config'`

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/engines/derivatives_native/config.py`:

```python
# Imported at module scope so tests can monkeypatch these symbols.
from app.services.db import get_config, set_config

_CONFIG_KEY = "derivatives_engine_config"


def get_engine_config(app: Any) -> DerivativesEngineConfig:
    """Return the engine config, lazy-seeding app.state from the DB (or
    defaults). Mirrors the lazy-seed pattern used for profile_overrides."""
    cur = getattr(app.state, "derivatives_engine_config", None)
    if cur is None:
        raw = ""
        try:
            raw = get_config(_CONFIG_KEY, "")
        except Exception:
            raw = ""
        if raw:
            try:
                cur = DerivativesEngineConfig.model_validate_json(raw)
            except Exception:
                cur = DerivativesEngineConfig()
        else:
            cur = DerivativesEngineConfig()
        app.state.derivatives_engine_config = cur
    return cur


def set_engine_config(app: Any, cfg: DerivativesEngineConfig) -> DerivativesEngineConfig:
    """Cache on app.state and persist as JSON in system_config."""
    app.state.derivatives_engine_config = cfg
    try:
        set_config(_CONFIG_KEY, cfg.model_dump_json())
    except Exception:
        pass
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestEngineConfigAccessors -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/derivatives_native/config.py backend/tests/test_derivatives_native.py
git commit -m "feat(deriv-native): engine config accessors (lazy-seed + persist)"
```

---

## Task 3: Native engine — futures leg (bypasses routing veto)

**Files:**
- Create: `backend/app/engines/derivatives_native/engine.py`
- Test: `backend/tests/test_derivatives_native.py`

**Context:** `selector._futures_candidate(*, signal, market, profile)` returns a
`DerivativesCandidate` or `None` (verified in `selector.py:47`). `get_profile(strategy, overrides)`
resolves the per-strategy profile (sizing/leverage params). The native engine emits the futures leg
whenever `directional_futures` is active and the SL/TP solver succeeds — there is **no**
`instrument_chooser` call, so a high-IVR signal that the routing gate would force to futures-only (or
the routing score would send to options) is emitted as futures unconditionally here.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
from app.engines.derivatives.freeze_token import get_store
from app.engines.derivatives.schemas import (
    DecisionStatus, MarketContext, SignalContext,
)
from app.engines.derivatives_native import engine as native_engine


@pytest.fixture(autouse=True)
def _reset_freeze():
    get_store().clear()
    yield
    get_store().clear()


def _signal(direction="long", entry=50000.0, atr=500.0) -> SignalContext:
    return SignalContext(
        strategy="edge/ma_crossover", underlying="BTC", direction=direction,
        entry=entry, stop_loss=entry - 2 * atr, take_profit=entry + 4 * atr,
        atr=atr, rr_target=2.0, signal_score=85.0, presized=True,
    )


def _market(spot=50000.0, ivr=90.0) -> MarketContext:
    # ivr=90 would trip the routing gate's ivr_pct_naked_max veto; native ignores it.
    return MarketContext(spot=spot, underlying="BTC", ivr_pct=ivr,
                         funding_8h_pct=0.0, portfolio_value=100_000.0)


class TestNativeFuturesLeg:
    def test_emits_futures_when_directional_active(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["directional_futures"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(), chain=None, config=cfg)
        assert dual.futures is not None
        assert dual.futures.status == DecisionStatus.OK
        assert dual.futures.chosen.instrument_type == "futures"
        assert dual.futures.freeze_token  # frozen so /execute works
        assert dual.status == DecisionStatus.OK

    def test_no_futures_when_source_inactive(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["skew_put"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(), chain=None, config=cfg)
        assert dual.futures is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestNativeFuturesLeg -v`
Expected: FAIL — `ModuleNotFoundError`/`AttributeError: module ... has no attribute 'decide_both'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/engines/derivatives_native/engine.py`:

```python
"""Native derivatives engine producer.

Emits a futures leg and/or long-premium option legs per the active alpha
sources in `DerivativesEngineConfig`, gated only by tradeability + risk
posture — NOT by `instrument_chooser` (the routing veto). Returns the
existing `DualDerivativesDecision` contract so downstream is unchanged.

Phase 2a: directional_futures + long_only options (long call/put). Spreads
(defined_risk) and short vol (naked) are Phase 2b/2d; selecting them here
falls back to long_only with a warning.
"""
from __future__ import annotations

import time
from typing import Optional

from app.engines.derivatives import selector as _sel
from app.engines.derivatives.freeze_token import get_store as _get_freeze_store
from app.engines.derivatives.profiles import get_profile
from app.engines.derivatives.schemas import (
    DecisionStatus, DerivativesDecision, DualDerivativesDecision,
    InstrumentBias, MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives_native.config import DerivativesEngineConfig, RiskPosture
from app.schemas.market import OptionSummary


def _frozen_ok(candidate, *, reason: str, now_ms: int) -> DerivativesDecision:
    dec = DerivativesDecision(
        status=DecisionStatus.OK, chosen=candidate, alternatives=[],
        reason=reason, timestamp_ms=now_ms, warnings=list(candidate.warnings),
    )
    token, ttl = _get_freeze_store().freeze(dec)
    dec.freeze_token = token
    dec.freeze_token_ttl_ms = ttl
    return dec


def decide_both(
    *,
    signal: SignalContext,
    market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
    config: Optional[DerivativesEngineConfig] = None,
) -> DualDerivativesDecision:
    cfg = config or DerivativesEngineConfig()
    profile = get_profile(signal.strategy, profile_overrides)
    now_ms = int(time.time() * 1000)
    sources = set(cfg.active_alpha_sources)
    warnings: list[str] = []

    futures_leg: Optional[DerivativesDecision] = None
    options_leg: Optional[DerivativesDecision] = None

    # ── Futures leg (directional, default) — no routing veto ──────────────
    if "directional_futures" in sources:
        fut = _sel._futures_candidate(signal=signal, market=market, profile=profile)
        if fut is not None:
            futures_leg = _frozen_ok(fut, reason="native:directional_futures", now_ms=now_ms)
        else:
            futures_leg = DerivativesDecision(
                status=DecisionStatus.DEFER,
                reason=f"native futures sl_tp rejected for {signal.underlying}",
                code="sl_tp_reject", timestamp_ms=now_ms,
            )

    # ── Options leg (long premium only in 2a) ─────────────────────────────
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

    status = DecisionStatus.OK if (
        (futures_leg and futures_leg.status == DecisionStatus.OK)
        or (options_leg and options_leg.status == DecisionStatus.OK)
    ) else DecisionStatus.DEFER

    return DualDerivativesDecision(
        status=status, futures=futures_leg, options=options_leg,
        reason=f"native mode · sources={sorted(sources)}",
        timestamp_ms=now_ms, warnings=warnings,
    )


def decide(
    *,
    signal: SignalContext,
    market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
    config: Optional[DerivativesEngineConfig] = None,
) -> DerivativesDecision:
    """Single-decision shape for /preview parity: prefer options leg if OK,
    else futures leg, else a DEFER."""
    dual = decide_both(signal=signal, market=market, chain=chain,
                       profile_overrides=profile_overrides, config=config)
    if dual.options and dual.options.status == DecisionStatus.OK:
        return dual.options
    if dual.futures and dual.futures.status == DecisionStatus.OK:
        return dual.futures
    return DerivativesDecision(
        status=DecisionStatus.DEFER, reason=dual.reason,
        code="native_no_candidate", timestamp_ms=dual.timestamp_ms)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestNativeFuturesLeg -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/derivatives_native/engine.py backend/tests/test_derivatives_native.py
git commit -m "feat(deriv-native): native engine futures leg (bypasses routing veto)"
```

---

## Task 4: Native engine — long-premium options leg + over-filter contrast

**Files:**
- Test: `backend/tests/test_derivatives_native.py` (engine.py already supports this from Task 3)

**Context:** This task adds tests proving (a) the native engine emits a long-premium option leg when
an options source is active and a tradeable chain is present, and (b) the **behavioral difference vs
the routing gate**: with `ivr_pct=90` (above `edge` profile `ivr_pct_naked_max=50`) the routing
gate's `instrument_chooser` would veto options to futures, whereas the native engine still emits the
futures leg directly. This is the "over-filter bypass" the whole phase is about.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_derivatives_native.py`:

```python
from app.schemas.market import OptionSummary


def _chain_btc(spot=50000.0) -> list[OptionSummary]:
    """A small tradeable call chain around spot (14 DTE, tight spread, real OI)."""
    out = []
    for strike in (48000, 49000, 50000, 51000, 52000):
        intrinsic = max(0.0, spot - strike)
        mark = intrinsic + 1200.0
        out.append(OptionSummary(
            instrument_name=f"C-BTC-{strike}-140625", underlying="BTC",
            strike=float(strike), expiry_date="140625", dte=14,
            option_type="call", bid=mark * 0.985, ask=mark * 1.015,
            mark_price=mark, mid_price=mark, mark_iv=55.0,
            delta=0.55 if strike <= spot else 0.40,
            gamma=0.0006, vega=20.0, theta=-15.0, rho=5.0,
            open_interest=400.0, volume_24h=200.0,
            last_updated_ms=int(time.time() * 1000), spread_pct=0.03))
    return out


class TestNativeOptionsLeg:
    def test_emits_long_premium_when_options_source_active(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["directional_futures", "vrp_voltiming"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options is not None
        assert dual.options.status == DecisionStatus.OK
        assert dual.options.chosen.instrument_type == "options"
        assert dual.options.freeze_token

    def test_overfilter_bypass_high_ivr_still_emits_futures(self):
        # ivr=90 > edge profile ivr_pct_naked_max(50): routing gate would veto
        # options→futures via instrument_chooser. Native emits futures directly.
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["directional_futures"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=90.0), chain=_chain_btc(), config=cfg)
        assert dual.futures.status == DecisionStatus.OK

    def test_defined_risk_falls_back_to_long_only_with_warning(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert any("long_only" in w for w in dual.warnings)
```

- [ ] **Step 2: Run test to verify it fails (then passes — engine already supports it)**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestNativeOptionsLeg -v`
Expected: PASS (3 passed). If `test_emits_long_premium...` FAILS with options leg DEFER, inspect
`_build_options_candidates` gates (expiry/strike/pinning) against `_chain_btc` and widen the fixture
(more strikes / higher OI / lower `spread_pct`) until a strike survives — do NOT weaken the engine.

- [ ] **Step 3: (No implementation change expected)**

The engine from Task 3 already implements this. If Step 2 surfaced a real gap, fix `engine.py`
minimally here and show the diff.

- [ ] **Step 4: Run the full native test module**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py -v`
Expected: PASS (all tasks 1–4)

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_derivatives_native.py
git commit -m "test(deriv-native): long-premium options leg + over-filter bypass"
```

---

## Task 5: Wire producer swap in `_both_rows` + `/config/engine` endpoints

**Files:**
- Modify: `backend/app/api/v1/endpoints/derivatives.py`
- Test: `backend/tests/test_derivatives_native.py`

**Context:** `_both_rows` (derivatives.py:245) calls module-level `_decide_both` at line 288. We swap
the callable based on `engine_mode`. `_decide_both` does NOT accept `config`; native does — so branch
the call. Add `GET/POST /config/engine` next to the existing `/config` routes (line ~511+).

- [ ] **Step 1: Write the failing test (endpoint behavior via TestClient)**

Append to `backend/tests/test_derivatives_native.py`:

```python
class TestEngineConfigEndpoints:
    def test_get_and_post_engine_config(self):
        from fastapi.testclient import TestClient
        from app.main import app  # FastAPI instance
        client = TestClient(app)

        r = client.get("/api/v1/derivatives/config/engine")
        assert r.status_code == 200
        assert r.json()["engine_mode"] == "routing_gate"

        r = client.post("/api/v1/derivatives/config/engine", json={
            "engine_mode": "native",
            "active_alpha_sources": ["directional_futures", "vrp_voltiming"],
            "risk_posture": "long_only",
            "validation_method": 1,
        })
        assert r.status_code == 200
        assert r.json()["engine_mode"] == "native"

        r = client.get("/api/v1/derivatives/config/engine")
        assert r.json()["engine_mode"] == "native"
```

> If `app.main:app` is too heavy to import in tests (DB/network on import), instead test the
> producer-selection helper directly: import `get_engine_config`, set `EngineMode.NATIVE` on a
> `_FakeApp`, and assert the branch in Step 3 selects `native_engine.decide_both`. Prefer the
> TestClient test if `app.main` imports cleanly (other tests like `test_phase3_derivatives_api.py`
> already import it — check that file's pattern and match it).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py::TestEngineConfigEndpoints -v`
Expected: FAIL — `404 Not Found` for `/config/engine`

- [ ] **Step 3: Add the endpoints + producer swap**

In `backend/app/api/v1/endpoints/derivatives.py`, add imports near the other engine imports
(top of file, after the existing `from app.engines.derivatives.selector import decide_both as _decide_both`):

```python
from app.engines.derivatives_native import engine as _native_engine
from app.engines.derivatives_native.config import (
    DerivativesEngineConfig, EngineMode, get_engine_config, set_engine_config,
)
```

In `_both_rows`, replace the single `_decide_both(...)` call (currently at lines 288–291):

```python
        dual = _decide_both(
            signal=sig, market=market_cache[ul], chain=chain_cache[ul],
            profile_overrides=overrides,
        )
```

with the mode-aware branch:

```python
        if engine_cfg.engine_mode == EngineMode.NATIVE:
            dual = _native_engine.decide_both(
                signal=sig, market=market_cache[ul], chain=chain_cache[ul],
                profile_overrides=overrides, config=engine_cfg,
            )
        else:
            dual = _decide_both(
                signal=sig, market=market_cache[ul], chain=chain_cache[ul],
                profile_overrides=overrides,
            )
```

and read the config once near the top of `_both_rows`, right after `overrides = _profile_overrides(request.app)` (line 260):

```python
    engine_cfg = get_engine_config(request.app)
```

Add the endpoints after `patch_config_global` (after line 591):

```python
@router.get("/config/engine", response_model=DerivativesEngineConfig)
async def get_engine_config_ep(request: Request) -> DerivativesEngineConfig:
    return get_engine_config(request.app)


@router.post("/config/engine", response_model=DerivativesEngineConfig)
async def set_engine_config_ep(
    body: DerivativesEngineConfig, request: Request
) -> DerivativesEngineConfig:
    return set_engine_config(request.app, body)
```

- [ ] **Step 4: Run test to verify it passes + regression check**

Run: `cd backend && .venv/bin/python -m pytest tests/test_derivatives_native.py -v`
Expected: PASS (all)
Run: `cd backend && .venv/bin/python -m pytest tests/test_phase3_derivatives_api.py tests/test_phase2_selector.py -v`
Expected: PASS (no regression — routing_gate path unchanged)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/derivatives.py backend/tests/test_derivatives_native.py
git commit -m "feat(deriv-native): producer swap in _both_rows + /config/engine endpoints"
```

---

## Task 6: Frontend — engine mode toggle + source/risk selectors

**Files:**
- Modify: `frontend/src/hooks/useDerivatives.ts`
- Modify: `frontend/src/components/derivatives/DerivativesPanel.tsx`

**Context:** Backend now serves `GET/POST /api/v1/derivatives/config/engine`. Match the existing
fetch/patch idioms in `useDerivatives.ts` (read the file first; mirror how it calls `/config`).

- [ ] **Step 1: Add engine-config hook**

In `frontend/src/hooks/useDerivatives.ts`, add (mirroring the existing config fetch pattern):

```typescript
export type EngineMode = "routing_gate" | "native";
export type RiskPosture = "long_only" | "defined_risk" | "naked";

export interface DerivativesEngineConfig {
  engine_mode: EngineMode;
  active_alpha_sources: string[];
  risk_posture: RiskPosture;
  validation_method: 1 | 2 | 3;
}

export async function fetchEngineConfig(): Promise<DerivativesEngineConfig> {
  const r = await fetch("/api/v1/derivatives/config/engine");
  if (!r.ok) throw new Error(`engine config ${r.status}`);
  return r.json();
}

export async function patchEngineConfig(
  cfg: DerivativesEngineConfig,
): Promise<DerivativesEngineConfig> {
  const r = await fetch("/api/v1/derivatives/config/engine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  if (!r.ok) throw new Error(`engine config patch ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: Add the controls to `DerivativesPanel.tsx`**

In `frontend/src/components/derivatives/DerivativesPanel.tsx`, add a settings row that:
- loads config via `fetchEngineConfig()` on mount (useEffect + useState),
- renders a **mode toggle** (`routing_gate` ↔ `native`),
- renders **alpha-source checkboxes** for `directional_futures` (default-checked), `vrp_voltiming`, `skew_put`, `gex_pinning`,
- renders a **risk-tier `<select>`** with `long_only` (default), `defined_risk`, `naked`; selecting `naked` shows an inline warning span `"Naked short vol — uncapped tail risk"` and (2a) is non-submittable / disabled with a "Phase 2d" note,
- calls `patchEngineConfig(next)` on change and updates local state from the response.

```tsx
const [engineCfg, setEngineCfg] = useState<DerivativesEngineConfig | null>(null);
useEffect(() => { fetchEngineConfig().then(setEngineCfg).catch(() => {}); }, []);

async function update(patch: Partial<DerivativesEngineConfig>) {
  if (!engineCfg) return;
  const next = { ...engineCfg, ...patch };
  setEngineCfg(await patchEngineConfig(next));
}

// in JSX:
{engineCfg && (
  <div className="deriv-engine-settings">
    <label>
      Engine:
      <select value={engineCfg.engine_mode}
              onChange={(e) => update({ engine_mode: e.target.value as EngineMode })}>
        <option value="routing_gate">Routing Gate (existing)</option>
        <option value="native">Native (new)</option>
      </select>
    </label>
    {(["directional_futures","vrp_voltiming","skew_put","gex_pinning"] as const).map((s) => (
      <label key={s}>
        <input type="checkbox"
               checked={engineCfg.active_alpha_sources.includes(s)}
               onChange={(e) => update({ active_alpha_sources: e.target.checked
                 ? [...engineCfg.active_alpha_sources, s]
                 : engineCfg.active_alpha_sources.filter((x) => x !== s) })} />
        {s}
      </label>
    ))}
    <label>
      Risk:
      <select value={engineCfg.risk_posture}
              onChange={(e) => update({ risk_posture: e.target.value as RiskPosture })}>
        <option value="long_only">Long premium only</option>
        <option value="defined_risk">Defined risk (Phase 2b)</option>
        <option value="naked">Naked short (Phase 2d)</option>
      </select>
    </label>
    {engineCfg.risk_posture === "naked" && (
      <span className="warn">Naked short vol — uncapped tail risk</span>
    )}
  </div>
)}
```

- [ ] **Step 3: Type-check the frontend**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useDerivatives.ts frontend/src/components/derivatives/DerivativesPanel.tsx
git commit -m "feat(deriv-native): FE engine-mode toggle + alpha-source/risk selectors"
```

---

## Task 7: Cleanup + full regression

**Files:**
- Delete: `backend/_surface_probe.py` (ad-hoc live-surface probe from design)

- [ ] **Step 1: Remove the ad-hoc probe**

```bash
git rm --cached backend/_surface_probe.py 2>/dev/null; rm -f backend/_surface_probe.py
```

- [ ] **Step 2: Run the full backend derivatives suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -k "deriv or selector or native" -v`
Expected: PASS (native + existing derivatives tests green).

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore(deriv-native): remove ad-hoc surface probe; 2a green"
```

---

## Self-Review notes

- **Spec coverage:** engine_mode toggle (Task 5), global config engine_mode/active_alpha_sources/risk_posture/validation_method (Tasks 1–2,5), native producer reusing output contract (Task 3), directional_futures default-on + long-premium options (Tasks 3–4), over-filter bypass demonstrated (Task 4), FE toggle+source+risk selectors (Task 6). **Deferred (own plans):** multi-leg `DerivativesStructure`/defined_risk (2b), validation-method report endpoints + forward IV collector (2c), VRP/IV-percentile regime + naked tier (2d). `validation_method` is stored in 2a but not yet wired to a study run — that is 2c.
- **No naked path reachable in 2a:** risk_posture beyond `long_only` falls back to long_only with a warning (Task 3) and the FE marks those options as later-phase (Task 6).
- **Default unchanged:** `engine_mode` defaults to `routing_gate`; Task 5 regression run asserts the existing path is untouched.
