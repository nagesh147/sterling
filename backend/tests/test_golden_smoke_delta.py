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
