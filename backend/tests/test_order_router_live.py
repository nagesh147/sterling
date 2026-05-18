"""
Issue 18 — live OrderRouter integration tests with a stateful DummyLiveAdapter.

The existing `test_order_router.py` covers single-shot paper/shadow/live dispatch
with mocks. This file exercises the live path against a stateful dummy adapter
that simulates a real exchange:
  * idempotency: identical re-submissions return the prior order_id
  * retry-queue enqueue on adapter exception
  * leverage failure tolerated (non-fatal)
  * shadow mode records both live + paper

These tests are the "battle test, not real exchange" sign-off the handoff doc
references — they prove the dispatch pipeline doesn't NotImplementedError on
realistic adapter behavior.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from app.services import live_safety
from app.services.execution.order_router import (
    OrderRouter, OrderRouterRequest, RouterDeps, RouterMode,
)


@dataclass
class _Inst:
    underlying: str = "BTC"
    delta_perp_symbol: str = "BTCUSD"


@dataclass
class DummyLiveAdapter:
    """Stateful in-memory exchange. Tracks placed orders and lets tests
    inspect the call sequence."""
    last_index_price: float = 50_000.0
    place_order_calls: List[Dict[str, Any]] = field(default_factory=list)
    set_leverage_calls: List[Dict[str, Any]] = field(default_factory=list)
    next_order_id: int = 100
    fail_next_n: int = 0    # raise on the next N place_order calls
    fail_leverage: bool = False

    async def get_index_price(self, inst: Any) -> float:
        return self.last_index_price

    async def get_product_id(self, symbol: str) -> int:
        # Trivial deterministic mapping
        return 27 if symbol.startswith("BTC") else 13

    async def set_leverage(self, product_id: int, leverage: float) -> None:
        self.set_leverage_calls.append({"product_id": product_id, "leverage": leverage})
        if self.fail_leverage:
            raise RuntimeError("simulated set_leverage failure")

    async def place_order(self, **kwargs: Any) -> Dict[str, Any]:
        if self.fail_next_n > 0:
            self.fail_next_n -= 1
            raise RuntimeError("simulated exchange 5xx")
        oid = f"DUM{self.next_order_id}"
        self.next_order_id += 1
        self.place_order_calls.append({**kwargs, "id": oid})
        return {"id": oid, "average_fill_price": self.last_index_price + 1.5}

    async def place_order_option(self, **kwargs: Any) -> Dict[str, Any]:
        return await self.place_order(**kwargs)


def _resolve(_sym: str) -> _Inst:
    return _Inst()


def _make_deps() -> RouterDeps:
    return RouterDeps(
        list_open_positions=lambda: [],
        create_paper_position=lambda *_a, **_k: "PP_99",
    )


def _basic_req(**overrides: Any) -> OrderRouterRequest:
    base: Dict[str, Any] = dict(
        underlying="BTC", direction="long",
        instrument_type="futures", size=1, leverage=5,
        order_type="market",
    )
    base.update(overrides)
    return OrderRouterRequest(**base)


@pytest.fixture(autouse=True)
def _reset_safety():
    live_safety.reset_all_for_tests()


@pytest.mark.asyncio
async def test_live_dispatch_calls_adapter_and_records_order_id():
    adapter = DummyLiveAdapter()
    router = OrderRouter(
        mode=RouterMode.LIVE,
        adapter=adapter,
        deps=_make_deps(),
        instrument_resolver=_resolve,
    )
    resp = await router.submit(_basic_req(client_order_id="LIVE_T1"))
    assert resp.accepted
    assert resp.mode == "live"
    assert resp.order_id and resp.order_id.startswith("DUM")
    assert resp.entry_price == pytest.approx(50_001.5)
    assert len(adapter.place_order_calls) == 1


@pytest.mark.asyncio
async def test_live_dispatch_idempotency_returns_prior_order_id():
    adapter = DummyLiveAdapter()
    router = OrderRouter(
        mode=RouterMode.LIVE, adapter=adapter, deps=_make_deps(),
        instrument_resolver=_resolve,
    )
    req = _basic_req(client_order_id="LIVE_IDEM")
    resp1 = await router.submit(req)
    resp2 = await router.submit(req)
    assert resp1.order_id == resp2.order_id
    # Only one real call should have hit the exchange.
    assert len(adapter.place_order_calls) == 1


@pytest.mark.asyncio
async def test_live_dispatch_exception_enqueues_retry():
    adapter = DummyLiveAdapter(fail_next_n=1)
    router = OrderRouter(
        mode=RouterMode.LIVE, adapter=adapter, deps=_make_deps(),
        instrument_resolver=_resolve,
    )
    resp = await router.submit(_basic_req(client_order_id="LIVE_RETRY"))
    assert not resp.accepted
    assert resp.code == "exchange_error"
    assert resp.retry_id  # retry queue id surfaced


@pytest.mark.asyncio
async def test_live_dispatch_tolerates_set_leverage_failure():
    adapter = DummyLiveAdapter(fail_leverage=True)
    router = OrderRouter(
        mode=RouterMode.LIVE, adapter=adapter, deps=_make_deps(),
        instrument_resolver=_resolve,
    )
    resp = await router.submit(_basic_req(client_order_id="LIVE_LEV"))
    assert resp.accepted, "set_leverage failure is non-fatal per spec"
    assert len(adapter.set_leverage_calls) == 1
    assert len(adapter.place_order_calls) == 1


@pytest.mark.asyncio
async def test_shadow_mode_records_paper_and_live():
    """Shadow places a real order AND records a paper position for diff."""
    adapter = DummyLiveAdapter()
    deps = _make_deps()
    paper_calls: List[Any] = []
    deps.create_paper_position = (
        lambda *a, **k: (paper_calls.append((a, k)) or "PP_SHADOW")
    )
    router = OrderRouter(
        mode=RouterMode.SHADOW, adapter=adapter, deps=deps,
        instrument_resolver=_resolve,
    )
    resp = await router.submit(_basic_req(client_order_id="SHADOW_T1"))
    assert resp.accepted
    assert resp.mode == "shadow"
    assert resp.order_id and resp.order_id.startswith("DUM")
    assert resp.paper_position_id == "PP_SHADOW"
    assert len(paper_calls) == 1
