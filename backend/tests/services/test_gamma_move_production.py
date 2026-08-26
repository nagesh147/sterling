"""The production order path: durability, the safety gate, and broker truth.

These are the cases that only bite in production — a restart while holding, a
fill that came in worse than the limit, a retry after a timeout — and none of
them show up in a happy-path run.
"""
from __future__ import annotations

import pytest

from app.engines.gamma_move import GammaMoveConfig, InstrumentRef, PositionState
from app.services import gamma_move_positions as store


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
    base = dict(signal_id="s1", instrument=inst(), entry=53.0, stop=45.0, quantity=500,
                lots=1, entered_ms=1, entry_day="2026-09-20", order_id="o1")
    base.update(kw)
    return PositionState(**base)


class TestDurability:
    def test_a_position_survives_a_restart(self):
        """The whole point. A crash while long must not lose the position — the
        process that comes back would never exit something it cannot see."""
        store.put("u1", pos())
        store.reset()                              # simulate the restart
        back = store.get("u1", "RELIANCE26SEP1300CE")
        assert back is not None
        assert back.entry == 53.0 and back.stop == 45.0 and back.quantity == 500
        assert back.instrument.tradingsymbol == "RELIANCE26SEP1300CE"

    def test_open_positions_excludes_closed_ones(self):
        store.put("u1", pos())
        assert len(store.open_positions("u1")) == 1
        store.close("u1", "RELIANCE26SEP1300CE", "stop")
        assert store.open_positions("u1") == []

    def test_one_unreadable_row_does_not_lose_the_rest(self, monkeypatch):
        store.put("u1", pos())
        store.put("u1", pos(instrument=inst("OTHER26SEP1CE")))
        import json
        from app.services import db
        raw = json.loads(db.get_config("gamma_move_positions_u1"))
        raw.append({"garbage": True})
        db.set_config("gamma_move_positions_u1", json.dumps(raw))
        store.reset()
        assert len(store.load("u1")) == 2


class TestBrokerTruth:
    def test_a_sent_order_is_not_yet_a_position(self):
        p = store.put("u1", pos())
        assert p.status == "pending"
        assert p.is_open                          # tracked, but not confirmed

    def test_a_worse_fill_moves_the_stop_with_it(self):
        """The stop was sized against the intended entry. Leaving it where it was
        silently widens the risk past what the sizer allowed."""
        store.put("u1", pos(entry=53.0, stop=45.0))
        p = store.mark_filled("u1", "RELIANCE26SEP1300CE", 56.0)
        assert p.fill_price == 56.0
        assert p.stop == 48.0                      # +3 drift carried onto the stop
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
        from app.services import gamma_move_runner as runner
        monkeypatch.setattr("app.services.live_safety.kill_switch_state",
                            lambda: {"enabled": True, "reason": "manual halt"})
        ok, why = runner._safety("u1", "key-1")
        assert ok is False and "Kill switch" in why

    def test_it_fails_closed_when_it_cannot_be_evaluated(self, monkeypatch):
        """An unavailable safety check is not a passed one."""
        from app.services import gamma_move_runner as runner
        def boom(*a, **k):
            raise RuntimeError("safety subsystem down")
        monkeypatch.setattr("app.services.live_safety.assert_safe_to_trade", boom)
        ok, why = runner._safety("u1", "key-1")
        assert ok is False and "unavailable" in why

    def test_a_duplicate_key_is_refused(self, monkeypatch):
        from app.services import gamma_move_runner as runner
        monkeypatch.setattr("app.services.live_safety.check_idempotency",
                            lambda key: "ORDER-1")
        ok, why = runner._safety("u1", "key-1")
        assert ok is False and "Duplicate" in why


class TestModeIsReadNotStored:
    def test_config_carries_no_mode_fields(self):
        names = GammaMoveConfig.field_names()
        assert "execution_mode" not in names
        assert "protection_mode" not in names

    def test_is_paper_defaults_safe_without_an_account(self):
        from app.services import gamma_move_runner as runner
        assert runner.is_paper("nobody") is True
        assert runner.auto_execute("nobody") is False

    def test_is_paper_follows_the_account(self, monkeypatch):
        from app.services import gamma_move_runner as runner

        class Acct:
            is_paper = False
        monkeypatch.setattr("app.services.exchanges.kite.accounts.get_active",
                            lambda uid: Acct())
        assert runner.is_paper("u1") is False
