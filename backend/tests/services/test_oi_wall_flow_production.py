"""The production order path: durability, the safety gate, and broker truth."""
from __future__ import annotations

import pytest

from app.engines.oi_wall_flow import InstrumentRef, OIWallFlowConfig, PositionState
from app.services import oi_wall_flow_positions as store


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("STERLING_DB_PATH", str(tmp_path / "t.db"))
    from app.services import db
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "t.db"), raising=False)
    db.init()
    store.reset()
    yield
    store.reset()


def inst(symbol="RELIANCE26SEP1300CE") -> InstrumentRef:
    return InstrumentRef(instrument_id="12345", tradingsymbol=symbol, option_type="CE",
                         strike=1300.0, expiry="2026-09-29", lot_size=500, tick_size=0.05)


def pos(**kw) -> PositionState:
    i = kw.pop("instrument", inst())
    base = dict(signal_id="s1", option_type="CE", strike=1300.0, entry=53.0, stop=45.0,
                target=80.0, quantity=500, lots=1, entered_ms=1, entry_day="2026-09-20",
                underlying_invalidation=1200.0, tradingsymbol=i.tradingsymbol,
                instrument=i, order_id="o1")
    base.update(kw)
    return PositionState(**base)


class TestDurability:
    def test_a_position_survives_a_restart(self):
        store.put("u1", pos())
        store.reset()
        back = store.get("u1", "RELIANCE26SEP1300CE")
        assert back is not None
        assert back.entry == 53.0 and back.stop == 45.0 and back.quantity == 500
        assert back.instrument.tradingsymbol == "RELIANCE26SEP1300CE"

    def test_open_positions_excludes_closed_ones(self):
        store.put("u1", pos())
        assert len(store.open_positions("u1")) == 1
        store.close("u1", "RELIANCE26SEP1300CE", "stop")
        assert store.open_positions("u1") == []

    def test_one_unreadable_row_does_not_lose_the_rest(self):
        store.put("u1", pos())
        store.put("u1", pos(instrument=inst("OTHER26SEP1CE"),
                            tradingsymbol="OTHER26SEP1CE"))
        import json
        from app.services import db
        raw = json.loads(db.get_config("oi_wall_flow_positions_u1"))
        raw.append({"garbage": True})
        db.set_config("oi_wall_flow_positions_u1", json.dumps(raw))
        store.reset()
        assert len(store.load("u1")) == 2


class TestBrokerTruth:
    def test_a_sent_order_is_not_yet_a_position(self):
        p = store.put("u1", pos())
        assert p.status == "pending"
        assert p.is_open

    def test_a_worse_fill_moves_the_stop_with_it(self):
        store.put("u1", pos(entry=53.0, stop=45.0))
        p = store.mark_filled("u1", "RELIANCE26SEP1300CE", 56.0)
        assert p.fill_price == 56.0
        assert p.stop == 48.0
        assert p.effective_entry == 56.0
        assert p.status == "open"

    def test_effective_entry_falls_back_to_the_intended_price(self):
        assert store.put("u1", pos()).effective_entry == 53.0

    def test_a_rejection_is_recorded_not_silently_dropped(self):
        store.put("u1", pos())
        p = store.mark_rejected("u1", "RELIANCE26SEP1300CE", "REJECTED")
        assert p.status == "rejected" and not p.is_open


class TestSafetyGate:
    def test_the_kill_switch_stops_an_entry(self, monkeypatch):
        from app.services import oi_wall_flow_runner as runner
        monkeypatch.setattr("app.services.live_safety.kill_switch_state",
                            lambda: {"enabled": True, "reason": "manual halt"})
        ok, why = runner._safety("u1", "key-1")
        assert ok is False and "Kill switch" in why

    def test_it_fails_closed_when_it_cannot_be_evaluated(self, monkeypatch):
        from app.services import oi_wall_flow_runner as runner
        def boom(*a, **k):
            raise RuntimeError("safety subsystem down")
        monkeypatch.setattr("app.services.live_safety.assert_safe_to_trade", boom)
        ok, why = runner._safety("u1", "key-1")
        assert ok is False and "unavailable" in why


class TestModeIsReadNotStored:
    def test_config_carries_no_mode_fields(self):
        names = OIWallFlowConfig.field_names()
        assert "execution_mode" not in names
        assert "protection_mode" not in names
        assert "is_paper" not in names

    def test_is_paper_defaults_safe_without_an_account(self):
        from app.services import oi_wall_flow_runner as runner
        assert runner.is_paper("nobody") is True
        assert runner.auto_execute("nobody") is False

    def test_is_paper_follows_the_account(self, monkeypatch):
        from app.services import oi_wall_flow_runner as runner

        class Acct:
            is_paper = False
        monkeypatch.setattr("app.services.exchanges.kite.accounts.get_active",
                            lambda uid: Acct())
        assert runner.is_paper("u1") is False


class TestDefaultsDoNotOverrideIntent:
    def test_a_stored_off_state_survives_the_new_default(self):
        import json
        from app.services import db
        from app.services.oi_wall_flow import get_config
        db.set_config("oi_wall_flow_config", json.dumps({"enabled": False}))
        assert get_config().enabled is False

    def test_unreadable_config_falls_back_off(self):
        from app.services import db
        from app.services.oi_wall_flow import get_config
        db.set_config("oi_wall_flow_config", "{not json")
        assert get_config().enabled is False

    def test_empty_stored_string_is_the_real_default(self):
        from app.services import db
        from app.services.oi_wall_flow import get_config
        db.set_config("oi_wall_flow_config", "")
        assert get_config().enabled is True


class TestPowerSwitch:
    """Settings say off means nothing is scanned and no order is placed."""

    def test_scan_is_a_noop_when_disabled(self, monkeypatch):
        import asyncio
        from app.engines.oi_wall_flow import OIWallFlowConfig
        from app.services import oi_wall_flow_runner as runner
        monkeypatch.setattr(runner, "get_config",
                            lambda: OIWallFlowConfig(enabled=False).validate())
        called = []
        async def boom(*a, **k):
            called.append(1)
            return []
        monkeypatch.setattr("app.services.oi_wall_flow_scanner.scan_once", boom)
        out = asyncio.run(runner.scan_once("u1"))
        assert called == []
        assert out["scanned"] == 0 and out["armed"] == 0
        assert "switched off" in out["message"]

    def test_arm_refuses_when_disabled(self, monkeypatch):
        import asyncio
        from app.engines.oi_wall_flow import OIWallFlowConfig
        from app.services import oi_wall_flow_runner as runner
        monkeypatch.setattr(runner, "get_config",
                            lambda: OIWallFlowConfig(enabled=False).validate())
        out = asyncio.run(runner.arm("u1", "BSE:2026-09-29"))
        assert out["ok"] is False
        assert "switched off" in out["message"]
