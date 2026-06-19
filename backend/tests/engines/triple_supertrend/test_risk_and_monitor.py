"""Tests for workstreams F (sizing), E (fill tracking), C/D (tick-driven exit)."""
import pytest

from app.services.kite_engine import sizing
from app.services.kite_engine import positions as pos
from app.services.kite_engine import monitor


# ── F: risk sizing ───────────────────────────────────────────────────────────
class TestSizing:
    def test_sizes_to_risk_budget(self):
        # entry 100, stop 80 → ₹20/share × 50 lot = ₹1000 risk/lot.
        # 1% of ₹500,000 = ₹5000 budget → 5 lots.
        r = sizing.size_position(entry_premium=100, stop_premium=80, lot_size=50,
                                 available_capital=500_000, risk_pct=1.0, max_lots=10)
        assert r.lots == 5
        assert r.qty == 250
        assert r.risk_per_lot == pytest.approx(1000.0)
        assert r.est_risk == pytest.approx(5000.0)

    def test_floors_at_one_lot_when_risk_too_big(self):
        # risk/lot ₹1000 > budget (1% of ₹50,000 = ₹500) → floor 1 lot.
        r = sizing.size_position(entry_premium=100, stop_premium=80, lot_size=50,
                                 available_capital=50_000, risk_pct=1.0, max_lots=10)
        assert r.lots == 1
        assert "floored to 1 lot" in r.reason

    def test_capped_by_max_lots(self):
        r = sizing.size_position(entry_premium=10, stop_premium=9, lot_size=50,
                                 available_capital=10_000_000, risk_pct=5.0, max_lots=10)
        assert r.lots == 10
        assert "max_lots" in r.reason

    def test_capped_by_margin_affordability(self):
        # risk allows many lots, but only ~3 lots affordable by outlay.
        # entry 100 × 50 = ₹5000/lot; capital ₹16,000 → 3 lots affordable.
        r = sizing.size_position(entry_premium=100, stop_premium=99, lot_size=50,
                                 available_capital=16_000, risk_pct=50.0, max_lots=100)
        assert r.lots == 3
        assert "margin affords" in r.reason

    def test_stop_above_entry_defaults_one_lot(self):
        r = sizing.size_position(entry_premium=100, stop_premium=120, lot_size=50,
                                 available_capital=500_000, risk_pct=1.0, max_lots=10)
        assert r.lots == 1
        assert "risk undefined" in r.reason

    def test_zero_lot_size_yields_nothing(self):
        r = sizing.size_position(entry_premium=100, stop_premium=80, lot_size=0,
                                 available_capital=500_000, risk_pct=1.0, max_lots=10)
        assert r.lots == 0 and r.qty == 0


# ── C/D: pure exit predicate ─────────────────────────────────────────────────
class TestExitPredicate:
    def test_exits_when_premium_breaches_trail(self):
        assert pos.should_exit(stop_premium=80, ltp=79.5) is True
        assert pos.should_exit(stop_premium=80, ltp=80.0) is True  # at trail = breach

    def test_holds_above_trail(self):
        assert pos.should_exit(stop_premium=80, ltp=80.5) is False

    def test_no_stop_never_exits(self):
        assert pos.should_exit(stop_premium=0, ltp=10) is False

    def test_stale_tick_ignored(self):
        assert pos.should_exit(stop_premium=80, ltp=0) is False


# ── E + C/D: monitor against a fake client ───────────────────────────────────
class _FakeClient:
    def __init__(self):
        self.sells = []
        self.cancelled = []
    async def place_order_option(self, sym, side, size, **kw):
        self.sells.append((sym, side, size))
        return {"order_id": "EXIT-1"}
    async def delete_gtt(self, tid):
        self.cancelled.append(tid)
        return {"trigger_id": tid}


@pytest.mark.asyncio
async def test_tick_exit_sells_and_cancels_gtt(monkeypatch):
    pos.reset("m1")
    # avoid DB + auto_open coupling noise
    monkeypatch.setattr("app.services.kite_engine.monitor.state.clear_auto_open",
                        lambda *a, **k: None)
    p = pos.register(pos.OpenPosition(
        uid="m1", symbol="NIFTY24JUN24000CE", exchange="NFO", token=777,
        qty=50, lot_size=50, entry_premium=100, stop_premium=80,
        order_id="O1", status=pos.OPEN, gtt_id=555, guard_key="NIFTY24JUN24000CE"))
    client = _FakeClient()

    # tick above trail → no exit
    out = await monitor.on_tick("m1", 777, 85.0, client=client)
    assert out is None and client.sells == []

    # tick at/below trail → exit + GTT cancel + position closed
    out = await monitor.on_tick("m1", 777, 79.0, client=client)
    assert out == "NIFTY24JUN24000CE"
    assert client.sells == [("NIFTY24JUN24000CE", "sell", 50)]
    assert client.cancelled == [555]
    assert pos.get("m1", "NIFTY24JUN24000CE").status == pos.CLOSED


@pytest.mark.asyncio
async def test_pending_position_not_exited():
    pos.reset("m2")
    pos.register(pos.OpenPosition(
        uid="m2", symbol="X", exchange="NFO", token=1, qty=50,
        entry_premium=100, stop_premium=80, status=pos.PENDING))
    client = _FakeClient()
    out = await monitor.on_tick("m2", 1, 10.0, client=client)  # way below trail
    assert out is None and client.sells == []  # not filled yet → not protected


@pytest.mark.asyncio
async def test_order_update_confirms_fill():
    pos.reset("m3")
    pos.register(pos.OpenPosition(
        uid="m3", symbol="Y", exchange="NFO", token=2, qty=50,
        entry_premium=100, stop_premium=80, order_id="O9", status=pos.PENDING))
    await monitor.on_order_update("m3", {
        "tradingsymbol": "Y", "status": "COMPLETE", "average_price": 101.5, "order_id": "O9"})
    p = pos.get("m3", "Y")
    assert p.status == pos.OPEN and p.fill_price == pytest.approx(101.5)


@pytest.mark.asyncio
async def test_order_update_rejection_releases_guard(monkeypatch):
    pos.reset("m4")
    released = []
    monkeypatch.setattr("app.services.kite_engine.monitor.state.clear_auto_open",
                        lambda uid, key: released.append((uid, key)))
    pos.register(pos.OpenPosition(
        uid="m4", symbol="Z", exchange="NFO", token=3, qty=50,
        status=pos.PENDING, guard_key="Z"))
    await monitor.on_order_update("m4", {"tradingsymbol": "Z", "status": "REJECTED"})
    assert pos.get("m4", "Z").status == pos.REJECTED
    assert released == [("m4", "Z")]


@pytest.mark.asyncio
async def test_unknown_order_ignored():
    pos.reset("m5")
    # no registered position — must be a no-op, not raise
    await monitor.on_order_update("m5", {"tradingsymbol": "UNKNOWN", "status": "COMPLETE"})
    assert pos.get("m5", "UNKNOWN") is None


# ── C: broker-side protective GTT stop ───────────────────────────────────────
class _GttClient:
    def __init__(self):
        self.placed = []
        self.modified = []
    async def place_gtt(self, **kw):
        self.placed.append(kw)
        return {"trigger_id": 909}
    async def modify_gtt(self, tid, **kw):
        self.modified.append((tid, kw))
        return {"trigger_id": tid}


@pytest.mark.asyncio
async def test_protective_stop_places_single_leg_sell():
    from app.services.kite_engine import protective_stop as ps
    client = _GttClient()
    tid = await ps.place_stop(client, tradingsymbol="NIFTY24JUN24000CE", exchange="NFO",
                              qty=50, trigger_premium=80, last_price=100)
    assert tid == 909
    body = client.placed[0]
    assert body["trigger_values"] == [80.0]
    order = body["orders"][0]
    assert order["transaction_type"] == "SELL" and order["quantity"] == 50


@pytest.mark.asyncio
async def test_protective_stop_skips_when_no_stop():
    from app.services.kite_engine import protective_stop as ps
    client = _GttClient()
    assert await ps.place_stop(client, tradingsymbol="X", exchange="NFO",
                               qty=50, trigger_premium=0, last_price=100) is None
    assert client.placed == []
