"""Adaptive Edge execution: entry, protection, exit, reconcile.

Every test here guards a path that moves money or decides whether money is
protected. The recurring shape is "the wrong behaviour is silent": a position
recorded without an order, a stop that exists only on screen, an exit that sells
twice, a reconcile that abandons real positions on a transient API failure.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.engines.adaptive_edge import AdaptiveEdgeConfig
from app.engines.adaptive_edge.state_machine import StrategyState
from app.services import adaptive_edge_positions as positions
from app.services import adaptive_edge_runner as runner


@pytest.fixture(autouse=True)
def store(monkeypatch):
    """In-memory config store, and a clean position cache per test."""
    data: dict[str, str] = {}
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key, default="": data.get(key, default))
    monkeypatch.setattr(db, "set_config", lambda key, value: data.__setitem__(key, value))
    positions.reset()
    runner.clear()
    yield data
    positions.reset()
    runner.clear()


@pytest.fixture(autouse=True)
def allow_everything(monkeypatch):
    """Paper account, safety open, evidence granted — so each test isolates the
    behaviour it is actually about rather than re-testing the gates.

    The evidence gate is stubbed here on purpose. It genuinely blocks arming
    until the engine has earned the right to trade from its own live readings,
    which is correct and is covered in test_adaptive_edge_evidence.py. These
    tests are about what happens once that permission exists.
    """
    monkeypatch.setattr(runner, "is_paper", lambda uid: True)
    monkeypatch.setattr(runner, "_safety", lambda uid, key: (True, ""))
    monkeypatch.setattr(runner, "_is_market_open", lambda cfg: True)
    monkeypatch.setattr(runner, "evidence_permits_arming",
                        lambda uid: (True, "granted for this test"))


class FakeClient:
    """Records every call, so ordering assertions are possible."""

    def __init__(self, *, order_id: str = "OID-1", raise_on_place: bool = False,
                 status: str = "COMPLETE", average: float = 0.0,
                 broker_positions: Any = None):
        self.calls: list[tuple[str, Any]] = []
        self._order_id = order_id
        self._raise = raise_on_place
        self._status = status
        self._average = average
        self._broker_positions = broker_positions if broker_positions is not None else {"net": []}

    async def place_order(self, symbol, side, qty, **kwargs):
        self.calls.append((f"place:{side}", symbol))
        if self._raise:
            raise RuntimeError("broker refused")
        return {"order_id": self._order_id} if self._order_id else {}

    async def get_order_history(self, order_id):
        return [{"status": self._status, "average_price": self._average}]

    async def get_positions(self):
        return self._broker_positions

    async def quote(self, keys):
        return {k: {"last_price": 100.0} for k in keys}


def _signal(**over):
    row = {"signal_id": "SIG-1", "symbol": "NIFTY26090325000CE", "token": 111,
           "underlying": "NIFTY", "option_type": "CE", "lot_size": 50,
           "last_price": 120.0, "expiry": "2026-09-03"}
    row.update(over)
    return row


def _prime_scan(uid="u1", **over):
    runner._scan_states[uid] = {"candidates": [], "signals": [_signal(**over)]}


def _arm(uid="u1", client=None, monkeypatch=None, cfg=None):
    client = client or FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    if cfg is not None:
        monkeypatch.setattr(runner, "get_config", lambda: cfg)
    monkeypatch.setattr(runner, "_place_protection",
                        lambda u, c, p, k: _async(4242))
    return asyncio.run(runner.arm(uid, "SIG-1")), client


async def _await(value):
    return value


def _async(value):
    async def inner(*args, **kwargs):
        return value
    return inner()


# ------------------------------------------------------------------ entry

def test_arm_actually_places_an_order(monkeypatch):
    """A position record with no order behind it is worse than no position:
    the board shows a holding that does not exist."""
    _prime_scan()
    result, client = _arm(monkeypatch=monkeypatch)
    assert result["ok"] is True
    assert ("place:buy", "NFO:NIFTY26090325000CE") in client.calls


def test_arm_records_the_position_before_confirming_the_fill(monkeypatch):
    """If the process dies between send and confirm, the position that may exist
    at the broker must be one we can find again."""
    _prime_scan()
    seen: dict[str, Any] = {}
    client = FakeClient()

    async def confirm(c, order_id):
        seen["persisted"] = positions.get("u1", "NIFTY26090325000CE") is not None
        return "COMPLETE", 121.0

    monkeypatch.setattr(runner, "_confirm_fill", confirm)
    _arm(client=client, monkeypatch=monkeypatch)
    assert seen["persisted"] is True


def test_arm_reanchors_the_stop_to_the_actual_fill(monkeypatch):
    """Sizing the stop off the limit price is how it ends up against a price
    nobody traded at."""
    _prime_scan()
    client = FakeClient(status="COMPLETE", average=100.0)
    result, _ = _arm(client=client, monkeypatch=monkeypatch)
    # 30% default stop off the 100.0 fill, not off the 120.0 limit.
    assert result["entry"] == pytest.approx(100.0)
    assert result["stop"] == pytest.approx(70.0)


def test_arm_refuses_when_the_broker_rejects(monkeypatch):
    _prime_scan()
    client = FakeClient(status="REJECTED")
    result, _ = _arm(client=client, monkeypatch=monkeypatch)
    assert result["ok"] is False and "rejected" in result["reason"]
    assert positions.get("u1", "NIFTY26090325000CE").state == StrategyState.REJECTED.value


def test_arm_refuses_when_the_broker_returns_no_order_id(monkeypatch):
    """No id and no exception is the dangerous case: an order may exist."""
    _prime_scan()
    client = FakeClient(order_id="")
    result, _ = _arm(client=client, monkeypatch=monkeypatch)
    assert result["ok"] is False
    assert "no order id" in result["reason"]


def test_arm_refuses_when_placing_raises(monkeypatch):
    _prime_scan()
    client = FakeClient(raise_on_place=True)
    result, _ = _arm(client=client, monkeypatch=monkeypatch)
    assert result["ok"] is False and "broker refused" in result["reason"]


def test_arm_will_not_double_up_on_a_contract_already_held(monkeypatch):
    _prime_scan()
    _arm(monkeypatch=monkeypatch)
    result, _ = _arm(monkeypatch=monkeypatch)
    assert result["ok"] is False and "already holding" in result["reason"]


def test_arm_respects_the_daily_loss_cap(monkeypatch):
    """The cap is denominated in rupees against this engine's own closed
    positions, not the shared USD breaker that reads zero for an INR book."""
    _prime_scan()
    cfg = AdaptiveEdgeConfig(max_daily_loss=1000.0).validate()
    closed = positions.AdaptiveEdgePosition(
        symbol="OLD", token=1, underlying="NIFTY", direction="CE", quantity=50,
        lot_size=50, entry_price=100.0, stop_price=70.0, target_price=None,
        state=StrategyState.CLOSED.value, exit_price=60.0)
    positions.load("u1")["OLD"] = closed
    positions.persist("u1")

    result, _ = _arm(monkeypatch=monkeypatch, cfg=cfg)
    assert result["ok"] is False
    assert "daily loss cap" in result["reason"]


# ------------------------------------------------------------------- exit

def _open_position(uid="u1", **over):
    base = dict(symbol="SYM", token=7, underlying="NIFTY", direction="CE", quantity=50,
                lot_size=50, entry_price=100.0, stop_price=70.0, target_price=200.0,
                state=StrategyState.OPEN.value, peak_price=100.0, gtt_id=99)
    base.update(over)
    pos = positions.AdaptiveEdgePosition(**base)
    positions.put(uid, pos)
    return pos


def test_exit_cancels_the_broker_stop_before_selling(monkeypatch):
    """Selling while a GTT is armed is how one position gets sold twice."""
    order: list[str] = []
    pos = _open_position()
    client = FakeClient()

    async def cancel(uid, c, p):
        order.append("cancel")
        p.gtt_id = 0

    monkeypatch.setattr(runner, "_cancel_protection", cancel)
    original = client.place_order

    async def place(*a, **k):
        order.append("sell")
        return await original(*a, **k)

    client.place_order = place
    ok = asyncio.run(runner._exit_position("u1", client, pos,
                                           AdaptiveEdgeConfig().validate(),
                                           price=80.0, reason="stop"))
    assert ok is True
    assert order == ["cancel", "sell"]


def test_a_failed_exit_re_arms_the_protection_it_cancelled(monkeypatch):
    """Leaving it down turns a failed exit into an unprotected position."""
    pos = _open_position()
    client = FakeClient(raise_on_place=True)
    replaced: list[str] = []
    monkeypatch.setattr(runner, "_cancel_protection", lambda u, c, p: _async(None))
    monkeypatch.setattr(runner, "_place_protection",
                        lambda u, c, p, k: (replaced.append("re-armed"), _async(1))[1])
    ok = asyncio.run(runner._exit_position("u1", client, pos,
                                           AdaptiveEdgeConfig().validate(),
                                           price=80.0, reason="stop"))
    assert ok is False
    assert replaced == ["re-armed"]
    assert pos.exiting is False


def test_a_second_exit_caller_is_refused_while_one_is_in_flight(monkeypatch):
    """The tick monitor and the square-off must not both sell the same position."""
    pos = _open_position(exiting=True)
    client = FakeClient()
    ok = asyncio.run(runner._exit_position("u1", client, pos,
                                           AdaptiveEdgeConfig().validate(),
                                           price=80.0, reason="stop"))
    assert ok is False
    assert not any(call[0].startswith("place") for call in client.calls)


def test_the_exit_reason_is_recorded_as_given_not_inferred(monkeypatch):
    """A stop and a square-off can happen at the same price; recording the wrong
    one makes the exit ledger useless for calibration."""
    pos = _open_position()
    client = FakeClient()
    monkeypatch.setattr(runner, "_cancel_protection", lambda u, c, p: _async(None))
    asyncio.run(runner._exit_position("u1", client, pos, AdaptiveEdgeConfig().validate(),
                                      price=70.0, reason="square_off"))
    assert positions.get("u1", "SYM").exit_reason == "square_off"


# -------------------------------------------------------------- tick loop

def _ticks(token=7, price=100.0):
    return [{"instrument_token": token, "last_price": price}]


def test_ticks_exit_on_the_stop(monkeypatch):
    _open_position()
    client = FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_cancel_protection", lambda u, c, p: _async(None))
    assert asyncio.run(runner.on_ticks("u1", _ticks(price=69.0))) == "exited"
    assert positions.get("u1", "SYM").exit_reason == "stop"


def test_ticks_exit_on_the_target(monkeypatch):
    _open_position()
    client = FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_cancel_protection", lambda u, c, p: _async(None))
    asyncio.run(runner.on_ticks("u1", _ticks(price=210.0)))
    assert positions.get("u1", "SYM").exit_reason == "target"


def test_ticks_flatten_after_the_session_window(monkeypatch):
    _open_position()
    client = FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_is_market_open", lambda cfg: False)
    monkeypatch.setattr(runner, "_cancel_protection", lambda u, c, p: _async(None))
    asyncio.run(runner.on_ticks("u1", _ticks(price=120.0)))
    assert positions.get("u1", "SYM").exit_reason == "session_end"


def test_the_trail_ratchets_up_and_never_widens(monkeypatch):
    """Widening a stop is an expansion of risk the position never authorized."""
    _open_position(stop_price=70.0)
    client = FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_sync_trail", lambda u, c, p, k: _async(None))

    asyncio.run(runner.on_ticks("u1", _ticks(price=180.0)))
    raised = positions.get("u1", "SYM").stop_price
    assert raised > 70.0

    asyncio.run(runner.on_ticks("u1", _ticks(price=150.0)))
    assert positions.get("u1", "SYM").stop_price == raised


def test_no_open_position_is_idle(monkeypatch):
    assert asyncio.run(runner.on_ticks("u1", _ticks())) == "idle"


# -------------------------------------------------------------- reconcile

def test_reconcile_closes_a_position_the_broker_no_longer_holds(monkeypatch):
    """Closed behind our back — by a GTT, by hand, or by the exchange. Leaving it
    open blocks the next entry and reports a P&L that is not real."""
    _open_position()
    client = FakeClient(broker_positions={"net": []})
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    out = asyncio.run(runner.reconcile("u1"))
    assert out["closed"] == 1
    assert positions.get("u1", "SYM").is_open is False


def test_reconcile_keeps_a_position_the_broker_still_holds(monkeypatch):
    _open_position()
    client = FakeClient(broker_positions={"net": [{"tradingsymbol": "SYM", "quantity": 50}]})
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    out = asyncio.run(runner.reconcile("u1"))
    assert out["closed"] == 0
    assert positions.get("u1", "SYM").is_open is True


def test_reconcile_does_not_abandon_positions_when_the_broker_is_unreachable(monkeypatch):
    """Unknown broker state is not an empty one. Closing here would abandon real
    positions on a transient API failure."""
    _open_position()

    class Broken(FakeClient):
        async def get_positions(self):
            raise RuntimeError("api down")

    monkeypatch.setattr(runner, "_client", lambda u: _async(Broken()))
    out = asyncio.run(runner.reconcile("u1"))
    assert out["closed"] == 0
    assert out["errors"]
    assert positions.get("u1", "SYM").is_open is True


def test_reconcile_re_protects_a_position_that_lost_its_broker_stop(monkeypatch):
    """The whole point of running reconcile on a restart."""
    _open_position(gtt_id=0)
    client = FakeClient(broker_positions={"net": [{"tradingsymbol": "SYM", "quantity": 50}]})
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_place_protection", lambda u, c, p, k: _async(555))
    out = asyncio.run(runner.reconcile("u1"))
    assert out["reprotected"] == 1


# ------------------------------------------------------------ square off

def test_square_off_flattens_everything(monkeypatch):
    _open_position()
    client = FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_cancel_protection", lambda u, c, p: _async(None))
    out = asyncio.run(runner.square_off_all("u1"))
    assert out["closed"] == 1
    assert positions.get("u1", "SYM").exit_reason == "square_off"


def test_square_off_is_a_no_op_when_flat():
    assert asyncio.run(runner.square_off_all("u1"))["closed"] == 0


def test_past_square_off_uses_the_configured_time(monkeypatch):
    cfg = AdaptiveEdgeConfig(square_off_time="15:15").validate()
    monkeypatch.setattr(runner, "_hhmm_now", lambda: "15:20")
    assert runner.past_square_off(cfg) is True
    monkeypatch.setattr(runner, "_hhmm_now", lambda: "14:00")
    assert runner.past_square_off(cfg) is False


# ----------------------------------------------------------------- adopt

def test_adopt_protects_the_position_it_takes_over(monkeypatch):
    """A hand-placed position this engine manages but has not protected is the
    worst of both worlds: nobody is watching and everybody assumes somebody is."""
    client = FakeClient()
    monkeypatch.setattr(runner, "_client", lambda u: _async(client))
    monkeypatch.setattr(runner, "_place_protection", lambda u, c, p, k: _async(777))
    result = asyncio.run(runner.adopt("u1", "TAKEN", 50, 100.0))
    assert result["ok"] is True and result["gtt_id"] == 777
    assert positions.get("u1", "TAKEN").is_open is True
    assert positions.get("u1", "TAKEN").stop_price == pytest.approx(70.0)


def test_adopt_refuses_a_contract_already_managed(monkeypatch):
    _open_position(symbol="TAKEN")
    result = asyncio.run(runner.adopt("u1", "TAKEN", 50, 100.0))
    assert result["ok"] is False and "already managing" in result["reason"]


def test_adopt_refuses_nonsense_quantities():
    assert asyncio.run(runner.adopt("u1", "X", 0, 100.0))["ok"] is False
    assert asyncio.run(runner.adopt("u1", "X", 50, 0.0))["ok"] is False
