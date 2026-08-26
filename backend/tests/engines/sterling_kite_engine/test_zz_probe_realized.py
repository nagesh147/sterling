"""Throwaway probes for the exactly-once realized-PnL booking."""
import json
import pytest

from app.services.kite_engine import monitor, positions as pos, state
from app.services.exchanges.kite import ticker_manager as _ticker_manager
from tests.engines.sterling_kite_engine.test_risk_and_monitor import _FakeClient


@pytest.fixture(autouse=True)
def _patch_ticker_unsubscribe(monkeypatch):
    async def _noop(uid, tokens):
        return {"ok": True}
    monkeypatch.setattr(_ticker_manager, "unsubscribe", _noop)


def _mk(uid, sym="NIFTY24JUN24000CE", **kw):
    d = dict(uid=uid, symbol=sym, exchange="NFO", token=777, qty=50,
             entry_premium=100, stop_premium=80, order_id="ENTRY-1",
             status=pos.OPEN, direction="long", gtt_id=0, guard_key="NIFTY")
    d.update(kw)
    return pos.register(pos.OpenPosition(**d))


# ── H1: guards run BEFORE the claim (no poison) ──────────────────────────────
def test_zero_exit_price_does_not_poison_the_claim():
    uid = "probe1"
    pos.reset(uid); state.reset(uid)
    p = _mk(uid)
    monitor._record_realized(uid, p, 0.0)          # no exit price yet
    assert state.daily_realized_pnl(uid) == 0.0
    assert pos.get(uid, p.symbol).realized_booked is False, "claim was poisoned"
    monitor._record_realized(uid, p, 80.0)
    assert state.daily_realized_pnl(uid) == pytest.approx(-1000.0)


def test_qty_zero_does_not_poison_the_claim():
    uid = "probe1b"
    pos.reset(uid); state.reset(uid)
    p = _mk(uid, qty=0)
    monitor._record_realized(uid, p, 80.0)
    assert pos.get(uid, p.symbol).realized_booked is False


# ── H2: mid-placement postback with avg == 0 ─────────────────────────────────
@pytest.mark.asyncio
async def test_mid_placement_postback_without_avg_price(monkeypatch):
    uid = "probe2"
    pos.reset(uid); state.reset(uid)
    monkeypatch.setattr("app.services.kite_engine.monitor.state.clear_auto_open",
                        lambda *a, **k: None)
    p = _mk(uid)

    class _C(_FakeClient):
        async def place_order_option(self, sym, side, size, **kw):
            r = await super().place_order_option(sym, side, size, **kw)
            await monitor.on_order_update(uid, {
                "tradingsymbol": sym, "status": "COMPLETE", "transaction_type": "SELL",
                "order_id": r["order_id"]})           # no average_price
            return r

    await monitor._exit_position(_C(), uid, p, 80.0, reason="tick breach")
    print("day pnl:", state.daily_realized_pnl(uid),
          "booked:", pos.get(uid, p.symbol).realized_booked)
    assert state.daily_realized_pnl(uid) == pytest.approx(-1000.0)


# ── H3: re-entry after a booked close books a second time ────────────────────
@pytest.mark.asyncio
async def test_reentry_after_booked_close_books_again(monkeypatch):
    uid = "probe3"
    pos.reset(uid); state.reset(uid)
    monkeypatch.setattr("app.services.kite_engine.monitor.state.clear_auto_open",
                        lambda *a, **k: None)
    p = _mk(uid)
    await monitor._exit_position(_FakeClient(), uid, p, 80.0, reason="r1")
    assert state.daily_realized_pnl(uid) == pytest.approx(-1000.0)
    # re-enter the same contract
    p2 = _mk(uid, entry_premium=60, stop_premium=50, order_id="ENTRY-2")
    assert pos.get(uid, p2.symbol).realized_booked is False, "stale claim blocks re-entry"
    await monitor._exit_position(_FakeClient(), uid, p2, 50.0, reason="r2")
    assert state.daily_realized_pnl(uid) == pytest.approx(-1500.0)


# ── H4: persistence round-trip ───────────────────────────────────────────────
def test_realized_booked_round_trips(monkeypatch):
    uid = "probe4"
    pos.reset(uid); state.reset(uid)
    store = {}
    monkeypatch.setattr(pos.db, "set_config", lambda k, v: store.__setitem__(k, v))
    monkeypatch.setattr(pos.db, "get_config", lambda k: store.get(k))
    p = _mk(uid)
    assert pos.claim_realized(uid, p.symbol) is True
    raw = json.loads(store[f"kite_engine_positions_{uid}"])
    assert raw[0]["realized_booked"] is True
    pos.reset(uid)                      # simulate restart
    assert pos.get(uid, p.symbol).realized_booked is True
    assert pos.claim_realized(uid, p.symbol) is False


def test_legacy_row_without_the_field_loads_false(monkeypatch):
    uid = "probe5"
    pos.reset(uid); state.reset(uid)
    legacy = [{"uid": uid, "symbol": "S", "exchange": "NFO", "token": 1, "qty": 50,
               "entry_premium": 100.0, "stop_premium": 80.0, "status": pos.CLOSED}]
    monkeypatch.setattr(pos.db, "get_config",
                        lambda k: json.dumps(legacy) if k.endswith(uid) else None)
    monkeypatch.setattr(pos.db, "set_config", lambda k, v: None)
    assert pos.get(uid, "S").realized_booked is False


# ── H5: scale-in mid-exit ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scale_in_during_exit_await(monkeypatch):
    """A second entry registers a NEW row while _exit_position is awaiting."""
    uid = "probe6"
    pos.reset(uid); state.reset(uid)
    monkeypatch.setattr("app.services.kite_engine.monitor.state.clear_auto_open",
                        lambda *a, **k: None)
    p = _mk(uid)

    class _C(_FakeClient):
        async def place_order_option(self, sym, side, size, **kw):
            # scale-in lands mid-flight: registry row replaced, qty doubled
            _mk(uid, qty=100, entry_premium=100, order_id="ENTRY-2", status=pos.OPEN)
            return await super().place_order_option(sym, side, size, **kw)

    await monitor._exit_position(_C(), uid, p, 80.0, reason="tick breach")
    row = pos.get(uid, p.symbol)
    print("qty sold:", 50, "registry qty:", row.qty, "status:", row.status,
          "booked flag:", row.realized_booked, "day pnl:", state.daily_realized_pnl(uid))
