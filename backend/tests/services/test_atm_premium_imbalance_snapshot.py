"""The snapshot's blockers.

The board decides whether to offer the arm button from this list, so a missing
blocker is worse than a wrong one: it presents a configuration as ready when the
broker will reject it. Under the API tests the pair never resolves (no broker
account), so the lot-size rule needs resolution stubbed to be exercised at all.
"""
import pytest

import app.services.atm_premium_imbalance as svc
from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, InstrumentRef, OptionPairRef,
)


def _pair(lot_size=20):
    def leg(ot):
        return InstrumentRef(instrument_id="1", tradingsymbol=f"SENSEX77600{ot}",
                             option_type=ot, strike=77600.0, expiry="2026-08-27",
                             lot_size=lot_size, tick_size=0.05, upper_circuit=1745.45)
    return OptionPairRef(underlying="SENSEX", expiry="2026-08-27", strike=77600.0,
                         ce=leg("CE"), pe=leg("PE"))


@pytest.fixture
def resolving(monkeypatch):
    box = {"pair": _pair()}

    async def resolve(uid, cfg):
        return box["pair"]

    monkeypatch.setattr(svc, "resolve_option_pair", resolve)
    return box


def _with_quantity(monkeypatch, quantity):
    cfg = ATMPremiumImbalanceConfig(enabled=True, sizing_mode="QUANTITY", quantity=quantity)
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg)


def _with_lots(monkeypatch, lots, **kw):
    cfg = ATMPremiumImbalanceConfig(enabled=True, sizing_mode="LOTS", lots=lots, **kw)
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg)


@pytest.mark.asyncio
async def test_a_fraction_of_a_lot_is_reported_as_a_blocker(monkeypatch, resolving):
    _with_quantity(monkeypatch, 5)                      # lot size is 20
    out = await svc.snapshot("u1")
    assert any("not a whole multiple of the lot size 20" in b for b in out["blockers"])


@pytest.mark.asyncio
async def test_whole_lots_are_not_blocked(monkeypatch, resolving):
    _with_quantity(monkeypatch, 40)
    out = await svc.snapshot("u1")
    assert out["blockers"] == []


@pytest.mark.asyncio
async def test_an_unset_quantity_is_reported_once_not_twice(monkeypatch, resolving):
    """quantity 0 is "not set"; it must not also be called a bad lot multiple."""
    _with_quantity(monkeypatch, 0)
    out = await svc.snapshot("u1")
    assert out["blockers"] == ["quantity not set"]


@pytest.mark.asyncio
async def test_a_lot_size_of_one_never_blocks(monkeypatch, resolving):
    """Some instruments trade in single units; every quantity is whole there."""
    resolving["pair"] = _pair(lot_size=1)
    _with_quantity(monkeypatch, 7)
    out = await svc.snapshot("u1")
    assert out["blockers"] == []


@pytest.mark.asyncio
async def test_lots_are_reported_as_the_quantity_they_become(monkeypatch, resolving):
    """The board should show what will actually be ordered, not just "2 lots"."""
    _with_lots(monkeypatch, 2)
    out = await svc.snapshot("u1")
    assert out["sizing"] == {"mode": "LOTS", "lot_size": 20, "quantity": 40}
    assert out["blockers"] == []


@pytest.mark.asyncio
async def test_lots_cannot_be_a_fraction_of_a_lot_by_construction(monkeypatch, resolving):
    """Whatever the lot count, the result is whole lots -- that is the point."""
    for n in (1, 3, 7):
        _with_lots(monkeypatch, n)
        out = await svc.snapshot("u1")
        assert out["sizing"]["quantity"] % 20 == 0
        assert out["blockers"] == []


@pytest.mark.asyncio
async def test_unset_lots_say_lots_not_quantity(monkeypatch, resolving):
    """The message has to match the box the operator is looking at."""
    _with_lots(monkeypatch, 0)
    out = await svc.snapshot("u1")
    assert out["blockers"] == ["lots not set"]


@pytest.mark.asyncio
async def test_too_many_lots_is_reported_in_quantity(monkeypatch, resolving):
    _with_lots(monkeypatch, 100, max_quantity=500)
    out = await svc.snapshot("u1")
    assert any("exceeds the cap of 500" in b for b in out["blockers"])


@pytest.mark.asyncio
async def test_the_suggested_quantity_actually_works(monkeypatch, resolving):
    """The advice must be usable: feed it back and the blocker goes away."""
    _with_quantity(monkeypatch, 25)
    out = await svc.snapshot("u1")
    assert "use 20 or 40" in out["blockers"][0]
    _with_quantity(monkeypatch, 40)
    assert (await svc.snapshot("u1"))["blockers"] == []
