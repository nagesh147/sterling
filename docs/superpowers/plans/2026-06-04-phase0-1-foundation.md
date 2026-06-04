# Phase 0 + 1: Foundation (Safety Net + Formalized Contracts) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the zero-regression safety net (Phase 0) and formalize the broker order contract + registry + canonical domain models (Phase 1), all additive, with the existing 153-test suite as the gate.

**Architecture:** Strangler-fig / additive-in-place. No working file moves. New `TradingExchangeAdapter` ABC lifts the *already-implemented* Delta order methods into an enforced contract; a `registry.json` + loader provides broker metadata while delegating construction to the untouched factory; a new `app/domain/` package gives a canonical contracts surface. Every task ends green on `make verify`.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, pytest (`backend/.venv/bin/pytest`), React/Vite (`tsc --noEmit`).

**Spec:** `docs/superpowers/specs/2026-06-04-modular-trading-architecture-hardening-design.md`

**Conventions for all tasks:**
- Run backend tests from `backend/`: `cd backend && .venv/bin/pytest <args>`
- "Baseline" = the full-suite pass count recorded in Task 0.2; no task may reduce it.
- Commit after each task. Branch: `feat/modular-architecture-hardening` (already created).

---

## File Structure (locked decisions)

| File | Responsibility | Phase |
|---|---|---|
| `backend/app/engines/scalping/` (delete) | stale empty dir from rename | 0 |
| `Makefile` (modify) | add `verify` target | 0 |
| `backend/tests/test_golden_smoke_delta.py` (create) | pin current Delta paper-path + factory behavior | 0 |
| `backend/app/services/exchanges/trading_base.py` (create) | `TradingExchangeAdapter` ABC — enforced order contract | 1 |
| `backend/app/services/exchanges/adapters/delta_india.py` (modify line 85) | inherit the new ABC (declaration-only) | 1 |
| `backend/tests/test_broker_contract.py` (create) | every trading adapter satisfies the contract | 1 |
| `backend/app/domain/__init__.py` (create) | package marker + canonical exports | 1 |
| `backend/app/domain/models.py` (create) | `Signal`, `TradeEvent` + re-export of canonical schemas | 1 |
| `backend/app/domain/interfaces.py` (create) | `BrokerProtocol`, `MarketAdapterProtocol`, `StrategyProtocol`, `RiskRuleProtocol` | 1 |
| `backend/tests/test_domain_models.py` (create) | domain models construct + protocols match Delta | 1 |
| `backend/config/registry.json` (create) | declarative broker/market metadata | 1 |
| `backend/app/services/exchanges/registry.py` (create) | loader: metadata + class resolution + parity delegate | 1 |
| `backend/tests/test_broker_registry.py` (create) | registry loads, paths import, parity with factory | 1 |

---

# PHASE 0 — Safety Net & Cleanup (zero behavior change)

## Task 0.1: Remove rename leftovers

**Files:**
- Delete: `backend/app/engines/scalping/` (contains only stale `__pycache__`)
- Modify: `backend/tests/test_scalping_backtest.py:1` (docstring only)

- [ ] **Step 1: Confirm nothing imports the old path**

Run:
```bash
cd /home/nageshmadaram/Sterling && grep -rnE 'engines\.scalping|engines/scalping' backend/app backend/tests
```
Expected: ONLY one match — the docstring in `backend/tests/test_scalping_backtest.py`. If any non-docstring import appears, STOP and report (do not delete).

- [ ] **Step 2: Confirm the dir is package-less and stale**

Run:
```bash
ls -A backend/app/engines/scalping/
```
Expected: only `__pycache__` (no `__init__.py`, no `.py` sources). If `.py` sources exist, STOP and report.

- [ ] **Step 3: Delete the stale dir**

Run:
```bash
rm -rf backend/app/engines/scalping/
```

- [ ] **Step 4: Fix the stale docstring**

In `backend/tests/test_scalping_backtest.py` line 1, change `engines.scalping.backtest` to `engines.sterling_engine.backtest`. Use Edit:
- old: `"""Tests for the honest scalping replay engine (engines.scalping.backtest).`
- new: `"""Tests for the honest scalping replay engine (engines.sterling_engine.backtest).`

- [ ] **Step 5: Run the full suite to confirm no regression**

Run:
```bash
cd backend && .venv/bin/pytest tests/ -q 2>&1 | tail -15
```
Expected: same pass/fail counts as before this task (record the numbers; they become provisional baseline confirmed in Task 0.2).

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add -A && git commit -m "chore(phase0): remove scalping rename leftovers + fix stale docstring

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 0.2: Add `make verify` and record the baseline

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add the `verify` target**

Add `verify` to the `.PHONY` line and append this target to `Makefile`:
```makefile
verify:
	cd backend && .venv/bin/pytest tests/ -q
	cd frontend && npx tsc --noEmit
	@echo "VERIFY OK"
```

- [ ] **Step 2: Run it and capture the baseline**

Run:
```bash
cd /home/nageshmadaram/Sterling && make verify 2>&1 | tail -20
```
Expected: backend pytest summary line (e.g. `N passed, M skipped`), then `tsc` exits clean (no output), then `VERIFY OK`. Record `N passed` — this is **the baseline**. If `tsc` reports pre-existing errors unrelated to our work, note them and treat the current count as the frozen baseline (do not fix unrelated FE type errors in this plan).

- [ ] **Step 3: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add Makefile && git commit -m "chore(phase0): add 'make verify' (pytest + tsc) as the regression gate

Baseline: <N> backend tests passing.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
(Replace `<N>` with the recorded count.)

---

## Task 0.3: Delta India golden smoke test

Pins two things that must never silently change: (a) the factory returns a real `DeltaIndiaAdapter` for a `delta_india` config, constructed offline; (b) the `OrderRouter` paper path returns the stable response contract.

**Files:**
- Create: `backend/tests/test_golden_smoke_delta.py`

- [ ] **Step 1: Write the golden smoke test**

```python
"""
GOLDEN SMOKE — Delta India integration baseline.

Locks the current, working behavior so the architecture-hardening phases
cannot silently regress it. Offline only (no network): DeltaIndiaAdapter
construction is network-free; OrderRouter PAPER mode never calls the exchange.
"""
from __future__ import annotations

import pytest

from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges.adapter_factory import create_account_adapter
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services import live_safety
from app.services.execution.order_router import (
    OrderRouter, OrderRouterRequest, RouterDeps, RouterMode,
)


@pytest.fixture(autouse=True)
def _reset_safety():
    live_safety.reset_all_for_tests()
    yield
    live_safety.reset_all_for_tests()


def _delta_cfg() -> ExchangeConfig:
    return ExchangeConfig(
        id="smoke-delta", name="delta_india",
        api_key="k", api_secret="s", is_paper=True,
    )


class _Inst:
    underlying = "BTC"
    delta_perp_symbol = "BTCUSD"


def test_factory_builds_delta_adapter_offline():
    adapter = create_account_adapter(_delta_cfg())
    assert isinstance(adapter, DeltaIndiaAdapter)
    assert adapter._is_paper is True


@pytest.mark.asyncio
async def test_order_router_paper_contract_is_stable():
    deps = RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *_a, **_k: "PP_SMOKE",
    )
    router = OrderRouter(
        mode=RouterMode.PAPER, adapter=None, deps=deps,
        instrument_resolver=lambda _s: _Inst(),
    )
    resp = await router.submit(OrderRouterRequest(
        underlying="BTC", direction="long", instrument_type="futures",
        size=1, leverage=5, order_type="market",
    ))
    assert resp.accepted is True
    assert resp.mode == "paper"
    assert resp.status == "filled"
    assert resp.symbol == "BTCUSD"
    assert resp.side == "buy"
    assert resp.size == 1
    assert resp.paper_position_id == "PP_SMOKE"
```

- [ ] **Step 2: Run it — expect PASS (this pins existing behavior)**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_golden_smoke_delta.py -v 2>&1 | tail -20
```
Expected: 2 passed. (If `test_order_router_paper_contract_is_stable` fails on `resp.symbol`, the instrument resolver shape differs — inspect `OrderRouter._symbol_for` and adjust `_Inst.delta_perp_symbol`. It should be `BTCUSD` per `order_router.py:477`.)

- [ ] **Step 3: Run full suite — confirm baseline intact**

Run:
```bash
cd backend && .venv/bin/pytest tests/ -q 2>&1 | tail -5
```
Expected: baseline + 2 (the new tests).

- [ ] **Step 4: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/tests/test_golden_smoke_delta.py && git commit -m "test(phase0): Delta India golden smoke (factory + paper router contract)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

# PHASE 1 — Formalized Contracts, Registry, Domain Models (additive)

## Task 1.1: `TradingExchangeAdapter` ABC + make Delta conform

**Files:**
- Create: `backend/app/services/exchanges/trading_base.py`
- Modify: `backend/app/services/exchanges/adapters/delta_india.py:85`
- Create: `backend/tests/test_broker_contract.py`

- [ ] **Step 1: Write the failing contract test**

```python
"""
BROKER CONTRACT — every adapter that supports order placement must expose the
TradingExchangeAdapter surface, so a new broker that forgets cancel_order fails
CI instead of production.
"""
import inspect

from app.services.exchanges.trading_base import TradingExchangeAdapter
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter

REQUIRED_ABSTRACT = {"place_order", "place_order_option", "cancel_order", "get_product_id"}


def test_trading_base_declares_required_order_methods():
    assert REQUIRED_ABSTRACT.issubset(TradingExchangeAdapter.__abstractmethods__)


def test_delta_is_a_trading_adapter():
    assert issubclass(DeltaIndiaAdapter, TradingExchangeAdapter)


def test_delta_can_instantiate_with_contract_satisfied():
    # All abstract methods implemented → construction must succeed offline.
    adapter = DeltaIndiaAdapter(api_key="k", api_secret="s", is_paper=True)
    for name in REQUIRED_ABSTRACT:
        assert inspect.iscoroutinefunction(getattr(adapter, name))
```

- [ ] **Step 2: Run — expect FAIL (ImportError)**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_broker_contract.py -q 2>&1 | tail -10
```
Expected: FAIL — `ModuleNotFoundError: app.services.exchanges.trading_base`.

- [ ] **Step 3: Create `trading_base.py`**

```python
"""
TradingExchangeAdapter — the enforced order-placement contract.

Lifts the methods that today live only on the concrete DeltaIndiaAdapter (and
the informal _AsyncAdapterShim inside order_router.py) into an abstract base so
EVERY order-capable broker has a checked surface. Signatures mirror what Delta
already implements — this is a formalization, not a behavior change.

Optional capability methods (set_leverage, set_margin_mode, cancel_replace_stop,
market_reduce_close) default to NotImplementedError so a partial adapter still
boots; OrderRouter feature-detects / guards each call (see order_router.py).
"""
from abc import abstractmethod
from typing import Optional

from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter


class TradingExchangeAdapter(AuthenticatedExchangeAdapter):
    # ── required order surface ────────────────────────────────────────────
    @abstractmethod
    async def get_product_id(self, symbol: str) -> int:
        ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market_order",
        limit_price: Optional[float] = None,
        time_in_force: str = "gtc",
        post_only: bool = False,
        reduce_only: bool = False,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trail_amount: Optional[float] = None,
        **kwargs,
    ) -> dict:
        ...

    @abstractmethod
    async def place_order_option(
        self,
        option_symbol: str,
        side: str,
        size: float,
        order_type: str = "market_order",
        limit_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> dict:
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, product_id: int) -> dict:
        ...

    # ── optional capabilities (override where supported) ──────────────────
    async def set_leverage(self, product_id: int, leverage: float) -> None:
        raise NotImplementedError("set_leverage not supported by this adapter")

    async def set_margin_mode(self, product_id: int, mode: str) -> None:
        raise NotImplementedError("set_margin_mode not supported by this adapter")

    async def cancel_replace_stop(self, **kwargs) -> dict:
        raise NotImplementedError("cancel_replace_stop not supported by this adapter")

    async def market_reduce_close(self, **kwargs) -> dict:
        raise NotImplementedError("market_reduce_close not supported by this adapter")
```

- [ ] **Step 4: Make `DeltaIndiaAdapter` inherit it (declaration-only)**

In `backend/app/services/exchanges/adapters/delta_india.py`, add the import near the other adapter imports at the top of the file:
```python
from app.services.exchanges.trading_base import TradingExchangeAdapter
```
Then change line 85 from:
```python
class DeltaIndiaAdapter(AuthenticatedExchangeAdapter):
```
to:
```python
class DeltaIndiaAdapter(TradingExchangeAdapter):
```
(Delta already implements every abstract method, so nothing else changes. If `AuthenticatedExchangeAdapter` is no longer referenced elsewhere in the file, leave its import — `TradingExchangeAdapter` subclasses it, so existing `isinstance(x, AuthenticatedExchangeAdapter)` checks still pass.)

- [ ] **Step 5: Run the contract test + full suite — expect PASS**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_broker_contract.py -q && .venv/bin/pytest tests/ -q 2>&1 | tail -5
```
Expected: contract test 3 passed; full suite ≥ baseline. Critically, verify `tests/test_order_router*.py` and any `isinstance(..., AuthenticatedExchangeAdapter)` checks still pass (they do — `TradingExchangeAdapter` IS an `AuthenticatedExchangeAdapter`).

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/app/services/exchanges/trading_base.py backend/app/services/exchanges/adapters/delta_india.py backend/tests/test_broker_contract.py && git commit -m "feat(phase1): TradingExchangeAdapter ABC; DeltaIndiaAdapter conforms

Formalizes the order-placement contract (place_order/place_order_option/
cancel_order/get_product_id) that previously lived only on the concrete
adapter. Declaration-only for Delta; contract test guards future brokers.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.2: `app/domain/` — canonical models + interfaces

**Files:**
- Create: `backend/app/domain/__init__.py`
- Create: `backend/app/domain/models.py`
- Create: `backend/app/domain/interfaces.py`
- Create: `backend/tests/test_domain_models.py`

- [ ] **Step 1: Write the failing domain test**

```python
"""DOMAIN — canonical contracts surface (additive; no I/O)."""
from app.domain.models import Signal, TradeEvent
from app.domain.interfaces import BrokerProtocol
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter


def test_signal_constructs_market_agnostic():
    sig = Signal(
        underlying="BTC", direction="long", instrument_type="futures",
        score=82.5, strength="STRONG", stop_loss=49000.0, take_profit=53000.0,
        source="sterling_engine",
    )
    assert sig.underlying == "BTC"
    assert sig.direction == "long"
    assert sig.score == 82.5


def test_trade_event_has_type_and_timestamp():
    ev = TradeEvent(event_type="SignalRaised", payload={"underlying": "BTC"})
    assert ev.event_type == "SignalRaised"
    assert ev.timestamp_ms > 0
    assert ev.payload["underlying"] == "BTC"


def test_canonical_schema_reexports_are_importable():
    from app.domain.models import Candle, InstrumentMeta, AccountPosition  # noqa: F401


def test_delta_adapter_satisfies_broker_protocol():
    adapter = DeltaIndiaAdapter(api_key="k", api_secret="s", is_paper=True)
    assert isinstance(adapter, BrokerProtocol)
```

- [ ] **Step 2: Run — expect FAIL (ImportError)**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_domain_models.py -q 2>&1 | tail -10
```
Expected: FAIL — `ModuleNotFoundError: app.domain`.

- [ ] **Step 3: Create `app/domain/__init__.py`**

```python
"""
domain — the canonical contracts surface (pure; no I/O, no FastAPI).

Everything here is broker- and market-agnostic. Infrastructure (adapters,
persistence) and application (agents, router) depend INWARD on this package;
this package depends on nothing else in app/ except the existing schemas it
blesses as canonical.
"""
```

- [ ] **Step 4: Create `app/domain/models.py`**

```python
"""Canonical domain models: new primitives + re-exports of existing schemas."""
from __future__ import annotations

import time
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

# ── Re-export existing canonical schemas (single import surface) ──────────
from app.schemas.market import Candle, OptionSummary  # noqa: F401
from app.schemas.instruments import InstrumentMeta  # noqa: F401
from app.schemas.account import (  # noqa: F401
    AssetBalance, AccountPosition, AccountOrder, AccountFill, PortfolioSnapshot,
)
from app.schemas.risk import RiskParams  # noqa: F401


# ── New primitives ────────────────────────────────────────────────────────
class Signal(BaseModel):
    """Normalized strategy output — independent of broker and market.

    Mirrors the signal-relevant fields the OrderRouter already consumes via
    OrderRouterRequest, so strategies stay broker/market-agnostic.
    """
    underlying: str
    direction: Literal["long", "short"]
    instrument_type: Literal["futures", "options"] = "futures"
    score: float = 0.0
    strength: str = "SIGNAL"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    size_hint: float = 1.0
    option_symbol: Optional[str] = None
    source: str = ""
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class TradeEvent(BaseModel):
    """Base event for the in-process bus (taxonomy extended in Phase 3)."""
    event_type: str
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    payload: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 5: Create `app/domain/interfaces.py`**

```python
"""Structural interfaces (Protocols) for the plug-and-play boundaries.

Runtime-checkable so contract tests can assert an adapter/strategy conforms
without importing concrete types. These describe the SAME surface the existing
ABCs enforce; Protocols add structural checks usable across layers.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from app.domain.models import Signal


@runtime_checkable
class BrokerProtocol(Protocol):
    async def get_product_id(self, symbol: str) -> int: ...
    async def place_order(self, symbol: str, side: str, size: float, **kwargs) -> dict: ...
    async def cancel_order(self, order_id: str, product_id: int) -> dict: ...


@runtime_checkable
class MarketAdapterProtocol(Protocol):
    async def get_index_price(self, instrument) -> float: ...
    async def get_candles(self, instrument, resolution: str, limit: int = 200): ...


@runtime_checkable
class StrategyProtocol(Protocol):
    def generate(self, *args, **kwargs) -> List[Signal]: ...


@runtime_checkable
class RiskRuleProtocol(Protocol):
    def evaluate(self, context) -> Optional[str]:
        """Return None to allow, or a machine-readable breach code to reject."""
        ...
```

- [ ] **Step 6: Run the domain test + full suite — expect PASS**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_domain_models.py -q && .venv/bin/pytest tests/ -q 2>&1 | tail -5
```
Expected: 4 passed in the domain file; full suite ≥ baseline + new tests.

- [ ] **Step 7: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/app/domain backend/tests/test_domain_models.py && git commit -m "feat(phase1): app/domain canonical models (Signal, TradeEvent) + Protocols

Additive contracts surface: re-exports existing schemas + adds the two
missing primitives. BrokerProtocol is runtime-checkable; Delta satisfies it.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: `registry.json` + loader

The registry is the single source of truth for broker **metadata** (markets, capabilities) and **class location**; actual construction is **delegated to the existing factory** so there is exactly one construction code path (DRY) and guaranteed parity. The JSON's adapter paths are verified importable by the test, so they are not dead config.

**Files:**
- Create: `backend/config/registry.json`
- Create: `backend/app/services/exchanges/registry.py`
- Create: `backend/tests/test_broker_registry.py`

- [ ] **Step 1: Write the failing registry test**

```python
"""BROKER REGISTRY — metadata + class resolution + parity with the factory."""
import importlib

import pytest

from app.schemas.exchange_config import ExchangeConfig, SUPPORTED_EXCHANGES
from app.services.exchanges import registry
from app.services.exchanges.adapter_factory import create_account_adapter
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter


def test_registry_lists_all_supported_brokers():
    reg = registry.load_registry()
    assert set(reg["brokers"]).issuperset({"delta_india", "zerodha", "binance", "deribit", "okx"})


def test_every_adapter_path_imports():
    reg = registry.load_registry()
    for name, meta in reg["brokers"].items():
        module_path, cls_name = meta["adapter"].split(":")
        mod = importlib.import_module(module_path)
        assert hasattr(mod, cls_name), f"{name}: {cls_name} missing in {module_path}"


def test_resolve_adapter_class_returns_delta():
    assert registry.resolve_adapter_class("delta_india") is DeltaIndiaAdapter


def test_broker_meta_exposes_markets():
    meta = registry.broker_meta("delta_india")
    assert "crypto" in meta["markets"]


def test_load_account_adapter_parity_with_factory():
    cfg = ExchangeConfig(id="r", name="delta_india", api_key="k", api_secret="s", is_paper=True)
    via_registry = registry.load_account_adapter(cfg)
    via_factory = create_account_adapter(cfg)
    assert type(via_registry) is type(via_factory) is DeltaIndiaAdapter


def test_unknown_broker_raises():
    cfg = ExchangeConfig(id="r", name="nope", api_key="", api_secret="", is_paper=True)
    with pytest.raises(ValueError):
        registry.load_account_adapter(cfg)
```

- [ ] **Step 2: Run — expect FAIL**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_broker_registry.py -q 2>&1 | tail -10
```
Expected: FAIL — `ImportError: cannot import name 'registry'` (or `module ... has no attribute`).

- [ ] **Step 3: Create `backend/config/registry.json`**

```json
{
  "brokers": {
    "delta_india": {
      "adapter": "app.services.exchanges.adapters.delta_india:DeltaIndiaAdapter",
      "markets": ["crypto"],
      "capabilities": ["futures", "options"],
      "auth": "hmac"
    },
    "zerodha": {
      "adapter": "app.services.exchanges.adapters.zerodha:ZerodhaAdapter",
      "markets": ["equities", "commodities"],
      "capabilities": ["equity", "futures"],
      "auth": "token"
    },
    "binance": {
      "adapter": "app.services.exchanges.adapters.binance:BinanceAdapter",
      "markets": ["crypto"],
      "capabilities": ["futures"],
      "auth": "hmac"
    },
    "deribit": {
      "adapter": "app.services.exchanges.adapters.deribit:DeribitAdapter",
      "markets": ["crypto"],
      "capabilities": ["options", "futures"],
      "auth": "none"
    },
    "okx": {
      "adapter": "app.services.exchanges.adapters.okx:OKXAdapter",
      "markets": ["crypto"],
      "capabilities": ["futures"],
      "auth": "none"
    }
  },
  "markets": {
    "crypto": {"description": "Crypto perps & options"},
    "equities": {"description": "Indian equities"},
    "commodities": {"description": "Commodity futures (incl. natural gas)"},
    "forex": {"description": "FX pairs"},
    "metals": {"description": "Gold / silver"},
    "energy": {"description": "Natural gas / crude"}
  },
  "strategies": {}
}
```

- [ ] **Step 4: Create `backend/app/services/exchanges/registry.py`**

```python
"""
Declarative broker registry.

Single source of truth for broker METADATA (markets, capabilities) and class
location. Construction is delegated to adapter_factory.create_account_adapter so
there is exactly one construction path (DRY) and registry/factory cannot drift.

Falls back gracefully: if registry.json is missing, load_account_adapter still
works via the factory, and resolve/meta raise clear errors.
"""
from __future__ import annotations

import functools
import importlib
import json
from pathlib import Path
from typing import Any, Dict, Type

from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter
from app.services.exchanges.adapter_factory import create_account_adapter

_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "config" / "registry.json"


@functools.lru_cache(maxsize=1)
def load_registry() -> Dict[str, Any]:
    """Load and cache config/registry.json. Empty skeleton if absent."""
    if not _REGISTRY_PATH.exists():
        return {"brokers": {}, "markets": {}, "strategies": {}}
    with _REGISTRY_PATH.open() as fh:
        return json.load(fh)


def broker_meta(name: str) -> Dict[str, Any]:
    meta = load_registry()["brokers"].get(name.lower())
    if meta is None:
        raise ValueError(f"Broker not in registry: {name!r}")
    return meta


def list_brokers() -> Dict[str, Any]:
    return load_registry()["brokers"]


def resolve_adapter_class(name: str) -> Type[AuthenticatedExchangeAdapter]:
    """Dynamically import the adapter class named in the registry."""
    module_path, cls_name = broker_meta(name)["adapter"].split(":")
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)


def load_account_adapter(cfg: ExchangeConfig) -> AuthenticatedExchangeAdapter:
    """Registry-validated construction. Delegates to the factory (one path).

    New code should call this. Existing callers of create_account_adapter
    keep working unchanged.
    """
    return create_account_adapter(cfg)
```

- [ ] **Step 5: Run the registry test + full suite — expect PASS**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_broker_registry.py -q && .venv/bin/pytest tests/ -q 2>&1 | tail -5
```
Expected: registry file all passed; full suite ≥ baseline + new tests. (If `_REGISTRY_PATH` resolves wrong, print `registry._REGISTRY_PATH` and adjust `.parents[N]` — `registry.py` is at `backend/app/services/exchanges/`, so `parents[3]` = `backend/`, and `config/registry.json` sits under `backend/config/`.)

- [ ] **Step 6: Commit**

```bash
cd /home/nageshmadaram/Sterling && git add backend/config/registry.json backend/app/services/exchanges/registry.py backend/tests/test_broker_registry.py && git commit -m "feat(phase1): declarative broker registry (registry.json + loader)

Single source of truth for broker metadata + class location; construction
delegated to the factory (one path, guaranteed parity). Test verifies every
adapter path imports, so the JSON is CI-checked, not dead config.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.4: Phase-gate verification

- [ ] **Step 1: Full `make verify` green**

Run:
```bash
cd /home/nageshmadaram/Sterling && make verify 2>&1 | tail -20
```
Expected: backend pytest ≥ baseline + 15 new tests (smoke 2 + contract 3 + domain 4 + registry 6), `tsc` clean, `VERIFY OK`.

- [ ] **Step 2: Confirm Delta golden smoke still green**

Run:
```bash
cd backend && .venv/bin/pytest tests/test_golden_smoke_delta.py -v 2>&1 | tail -10
```
Expected: 2 passed.

- [ ] **Step 3: Tag the phase**

```bash
cd /home/nageshmadaram/Sterling && git tag phase-1-foundation && echo "Phase 0+1 complete"
```

---

## Self-Review (completed by author)

- **Spec coverage:** Phase 0 (safety net, cleanup, golden smoke) ✓ §7 Phase 0; Phase 1 (TradingExchangeAdapter ✓ §6.1, registry.json ✓ §6.2, domain models ✓ §6.3) all mapped. Phases 2–6 intentionally deferred to their own plans (per spec §7 phasing).
- **Placeholders:** none — every code/test block is complete and runnable.
- **Type consistency:** `Signal`/`TradeEvent` fields used in `test_domain_models.py` match `models.py`; `REQUIRED_ABSTRACT` set matches the `@abstractmethod`s in `trading_base.py`; `resolve_adapter_class`/`broker_meta`/`load_account_adapter`/`load_registry` names consistent across `registry.py` and `test_broker_registry.py`.
- **Risk:** every task ends by running the full suite; Delta behavior pinned by the golden smoke from Task 0.3 onward.
