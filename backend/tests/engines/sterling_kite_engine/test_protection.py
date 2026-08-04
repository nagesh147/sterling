"""Every automatic SELL path, and the one that must NOT fire.

Three verified defects are pinned here, all of the same family: the account ending
up SHORT an option it never sold on purpose.

1. With ``stop_mode="both"`` the broker GTT and the tick monitor were armed at the
   IDENTICAL price. Market data reaches us before a fill postback does, so on a
   price breach the GTT has very likely already fired and its SELL is live at the
   exchange — and the monitor placed a second one. `_exiting` never guarded this:
   it only serialises OUR coroutines, and Zerodha's GTT engine never takes it.
2. A protective GTT armed against an entry that was then REJECTED was never
   cancelled — a resting SELL with no position behind it.
3. ``filled_quantity`` was never read, so a partial fill left the system believing
   it held the full intended quantity and arming exits for all of it.

Plus the new surface: a hand-placed order is now registered and armed like an
auto-executed one, and a target is enforced BROKER-side as the second leg of an
OCO so stop and target can never both fire.
"""
from __future__ import annotations

import pytest

from app.services.kite_engine import monitor
from app.services.kite_engine import positions as pos
from app.services.kite_engine import protection, protective_stop
import app.services.exchanges.kite.ticker_manager as _ticker_manager


class _FakeClient:
    """Records what was sent to the broker. ``cancel_error`` makes delete_gtt fail
    the way Zerodha would for a trigger that has already fired."""

    def __init__(self, cancel_error: str | None = None):
        self.sells: list = []
        self.cancelled: list = []
        self.gtts: list = []
        self.modified: list = []
        self.calls: list = []          # ordered log of every broker call
        self.cancel_error = cancel_error

    async def place_order_option(self, sym, side, size, **kw):
        self.sells.append((sym, side, size))
        self.calls.append("sell")
        return {"order_id": "EXIT-1"}

    async def place_order_future(self, sym, side, size, **kw):
        self.calls.append("sell_future")
        return {"order_id": "EXIT-F"}

    async def delete_gtt(self, tid):
        self.calls.append("cancel")
        if self.cancel_error:
            raise RuntimeError(self.cancel_error)
        self.cancelled.append(tid)
        return {"trigger_id": tid}

    async def place_gtt(self, **kw):
        self.gtts.append(kw)
        return {"trigger_id": 4242}

    async def modify_gtt(self, tid, **kw):
        self.modified.append((tid, kw))
        return {"trigger_id": tid}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    async def _noop(uid, tokens, **kw):
        return {"ok": True}
    monkeypatch.setattr(_ticker_manager, "unsubscribe", _noop)
    monkeypatch.setattr(_ticker_manager, "subscribe", _noop)
    monkeypatch.setattr("app.services.kite_engine.monitor.state.clear_auto_open",
                        lambda *a, **k: None)


def _held(uid="p1", *, gtt_id=555, stop=80.0, target=0.0, status=None, qty=50):
    pos.reset(uid)
    return pos.register(pos.OpenPosition(
        uid=uid, symbol="NIFTY24JUN24000CE", exchange="NFO", token=777,
        qty=qty, lot_size=50, entry_premium=100.0, stop_premium=stop,
        order_id="O1", status=status or pos.OPEN, gtt_id=gtt_id,
        guard_key="NIFTY24JUN24000CE", target_premium=target))


# ── 1. the double-sell ────────────────────────────────────────────────────────

class TestBrokerStopWinsThePriceRace:
    @pytest.mark.asyncio
    async def test_no_second_sell_when_the_gtt_could_not_be_cancelled(self):
        """The exact naked-short sequence: price hits the shared trigger, the GTT has
        already fired (so the cancel fails), and we must NOT add a second SELL."""
        _held("p1")
        client = _FakeClient(cancel_error="Trigger already triggered")

        out = await monitor.on_tick("p1", 777, 79.0, client=client)

        assert out is None, "the monitor reported an exit it did not place"
        assert client.sells == [], "second SELL placed while the broker's was already live"
        held = pos.get("p1", "NIFTY24JUN24000CE")
        assert held.status == pos.OPEN, (
            "position must stay open until the broker's fill postback reconciles it — "
            "closing it here would lose the position we still hold"
        )

    @pytest.mark.asyncio
    async def test_cancel_happens_before_the_sell(self):
        """Ordering is the fix. Cancelling AFTER selling cannot prevent anything."""
        _held("p2")
        client = _FakeClient()

        await monitor.on_tick("p2", 777, 79.0, client=client)

        assert client.calls == ["cancel", "sell"]
        assert client.cancelled == [555]
        assert client.sells == [("NIFTY24JUN24000CE", "sell", 50)]
        assert pos.get("p2", "NIFTY24JUN24000CE").status == pos.CLOSED

    @pytest.mark.asyncio
    async def test_non_price_exit_still_sells_even_if_the_cancel_fails(self):
        """A red-count / target / expiry exit will NEVER be executed by the GTT, so
        skipping our own SELL there would leave the position with no exit at all."""
        p = _held("p3", stop=80.0)
        pos.update_health("p3", p.symbol, red_count=3, exit_mode="one_red")
        client = _FakeClient(cancel_error="network unreachable")

        # price is nowhere near the stop, so this can only be the red-count exit
        out = await monitor.on_tick("p3", 777, 150.0, client=client)

        assert out == "NIFTY24JUN24000CE"
        assert client.sells == [("NIFTY24JUN24000CE", "sell", 50)]
        assert "red count" in pos.get("p3", "NIFTY24JUN24000CE").exit_reason

    @pytest.mark.asyncio
    async def test_position_with_no_gtt_is_unaffected(self):
        """stop_mode="monitor" has no broker stop to race with."""
        _held("p4", gtt_id=0)
        client = _FakeClient()

        out = await monitor.on_tick("p4", 777, 79.0, client=client)

        assert out == "NIFTY24JUN24000CE"
        assert client.calls == ["sell"]


# ── 2. the orphaned GTT ───────────────────────────────────────────────────────

class TestRejectedEntryLeavesNothingArmed:
    @pytest.mark.asyncio
    async def test_rejected_entry_cancels_its_protective_gtt(self):
        _held("r1", status=pos.PENDING)
        client = _FakeClient()

        await monitor.on_order_update(
            "r1", {"tradingsymbol": "NIFTY24JUN24000CE", "status": "REJECTED",
                   "order_id": "O1", "filled_quantity": 0}, client=client)

        assert client.cancelled == [555], "an armed SELL was left resting at Zerodha"
        held = pos.get("r1", "NIFTY24JUN24000CE")
        assert held.status == pos.REJECTED
        assert held.gtt_id == 0, "registry still points at a GTT that no longer exists"

    @pytest.mark.asyncio
    async def test_a_failed_cancel_is_reported_not_swallowed(self):
        """The operator has to be told to go look — this is the one case the code
        cannot fix by itself."""
        _held("r2", status=pos.PENDING)
        client = _FakeClient(cancel_error="gateway timeout")
        logged: list = []

        from app.services.kite_engine import state as kstate
        original = kstate.log
        kstate.log = lambda uid, kind, msg: logged.append(msg)
        try:
            await monitor.on_order_update(
                "r2", {"tradingsymbol": "NIFTY24JUN24000CE", "status": "REJECTED",
                       "order_id": "O1", "filled_quantity": 0}, client=client)
        finally:
            kstate.log = original

        assert any("could NOT be" in m for m in logged)


# ── 3. partial fills ─────────────────────────────────────────────────────────

class TestPartialFills:
    @pytest.mark.asyncio
    async def test_a_partial_fill_is_a_position_not_a_rejection(self):
        """CANCELLED after 1 of 3 lots filled means we HOLD 1 lot. Treating it as a
        rejection dropped a real position out of the registry — unguarded, invisible,
        and never squared off at expiry."""
        _held("f1", status=pos.PENDING, qty=150)
        client = _FakeClient()

        await monitor.on_order_update(
            "f1", {"tradingsymbol": "NIFTY24JUN24000CE", "status": "CANCELLED",
                   "order_id": "O1", "filled_quantity": 50, "average_price": 101.5},
            client=client)

        held = pos.get("f1", "NIFTY24JUN24000CE")
        assert held.status == pos.OPEN
        assert held.qty == 50, "still believes it holds the intended quantity"
        assert held.fill_price == pytest.approx(101.5)
        assert client.cancelled == [], "the stop must stay armed on what we do hold"

    @pytest.mark.asyncio
    async def test_a_full_fill_records_the_broker_quantity(self):
        _held("f2", status=pos.PENDING, qty=150)
        client = _FakeClient()

        await monitor.on_order_update(
            "f2", {"tradingsymbol": "NIFTY24JUN24000CE", "status": "COMPLETE",
                   "order_id": "O1", "filled_quantity": 100, "average_price": 99.0},
            client=client)

        held = pos.get("f2", "NIFTY24JUN24000CE")
        assert (held.status, held.qty) == (pos.OPEN, 100)

    @pytest.mark.asyncio
    async def test_the_exit_sells_only_what_is_held(self):
        """The whole point of reading the fill: the exit quantity follows it."""
        _held("f3", status=pos.PENDING, qty=150)
        client = _FakeClient()
        await monitor.on_order_update(
            "f3", {"tradingsymbol": "NIFTY24JUN24000CE", "status": "COMPLETE",
                   "order_id": "O1", "filled_quantity": 50, "average_price": 100.0},
            client=client)

        await monitor.on_tick("f3", 777, 79.0, client=client)

        assert client.sells == [("NIFTY24JUN24000CE", "sell", 50)]


# ── the target, enforced by the exchange ──────────────────────────────────────

class TestTargetIsAnOcoLeg:
    @pytest.mark.asyncio
    async def test_stop_and_target_go_out_as_one_two_leg_trigger(self):
        client = _FakeClient()
        tid = await protective_stop.place_stop(
            client, tradingsymbol="X", exchange="NFO", qty=50,
            trigger_premium=80.0, last_price=100.0, direction="long",
            target_premium=160.0)

        assert tid == 4242
        sent = client.gtts[0]
        assert sent["trigger_type"] == "two-leg"
        assert sent["trigger_values"] == [80.0, 160.0], "OCO triggers must ascend"
        assert len(sent["orders"]) == 2

    @pytest.mark.asyncio
    async def test_a_target_on_the_wrong_side_of_the_stop_is_refused(self):
        """A "target" below a long's stop would fire instantly for a loss. Fall back
        to a plain stop rather than arming nonsense."""
        client = _FakeClient()
        await protective_stop.place_stop(
            client, tradingsymbol="X", exchange="NFO", qty=50,
            trigger_premium=80.0, last_price=100.0, direction="long",
            target_premium=70.0)

        assert client.gtts[0]["trigger_type"] == "single"
        assert client.gtts[0]["trigger_values"] == [80.0]

    @pytest.mark.asyncio
    async def test_trailing_keeps_the_target_leg(self):
        """A GTT modify rewrites the whole trigger, so a move that forgot the target
        would silently drop it the first time the trail ratcheted."""
        client = _FakeClient()
        await protective_stop.move_stop(
            client, trigger_id=99, tradingsymbol="X", exchange="NFO", qty=50,
            trigger_premium=90.0, last_price=120.0, direction="long",
            target_premium=160.0)

        _tid, sent = client.modified[0]
        assert sent["trigger_type"] == "two-leg"
        assert sent["trigger_values"] == [90.0, 160.0]

    @pytest.mark.asyncio
    async def test_the_monitor_does_not_also_chase_a_target_the_broker_holds(self):
        """Two sell paths for one exit is the bug this whole file is about."""
        _held("t1", target=160.0, gtt_id=555)
        client = _FakeClient()

        out = await monitor.on_tick("t1", 777, 165.0, client=client)

        assert out is None and client.sells == []

    @pytest.mark.asyncio
    async def test_the_monitor_books_the_target_when_no_gtt_holds_it(self):
        """stop_mode="monitor" has no broker leg, so the target is ours to enforce."""
        _held("t2", target=160.0, gtt_id=0)
        client = _FakeClient()

        out = await monitor.on_tick("t2", 777, 165.0, client=client)

        assert out == "NIFTY24JUN24000CE"
        assert "target reached" in pos.get("t2", "NIFTY24JUN24000CE").exit_reason

    @pytest.mark.asyncio
    async def test_a_bar_that_hits_both_is_booked_as_the_stop(self):
        """Never resolve an ambiguous tick in our own favour."""
        _held("t3", stop=80.0, target=160.0, gtt_id=0)
        client = _FakeClient()

        await monitor.on_tick("t3", 777, 79.0, client=client)

        assert "trail breach" in pos.get("t3", "NIFTY24JUN24000CE").exit_reason


# ── re-entry must not double-arm ──────────────────────────────────────────────

class TestArmingIsIdempotentPerSymbol:
    @pytest.mark.asyncio
    async def test_re_arming_cancels_the_previous_trigger(self):
        """`positions.register` overwrites by symbol, so without this the old gtt_id
        was dropped and a SECOND trigger armed for one position — two SELLs, net short."""
        _held("a1", gtt_id=555)
        client = _FakeClient()

        await protection.arm_position(
            client, "a1", symbol="NIFTY24JUN24000CE", exchange="NFO", token=777,
            qty=50, lot_size=50, entry_premium=100.0, stop_premium=80.0,
            order_id="O2", stop_mode="both")

        assert client.cancelled == [555]
        assert pos.get("a1", "NIFTY24JUN24000CE").gtt_id == 4242

    @pytest.mark.asyncio
    async def test_arming_reports_what_it_actually_armed(self):
        pos.reset("a2")
        client = _FakeClient()

        armed = await protection.arm_position(
            client, "a2", symbol="X24JUN100CE", exchange="NFO", token=1,
            qty=50, lot_size=50, entry_premium=100.0, stop_premium=80.0,
            order_id="O3", stop_mode="both", target_premium=160.0)

        assert armed.protected is True
        assert "GTT #4242" in armed.describe() and "target" in armed.describe()

    @pytest.mark.asyncio
    async def test_no_stop_means_not_protected_and_says_so(self):
        pos.reset("a3")
        client = _FakeClient()

        armed = await protection.arm_position(
            client, "a3", symbol="X24JUN100CE", exchange="NFO", token=1,
            qty=50, lot_size=50, entry_premium=100.0, stop_premium=0.0,
            order_id="O4", stop_mode="both")

        assert armed.protected is False
        assert client.gtts == []
        assert "no stop" in armed.describe()


# ── the hand-placed order ─────────────────────────────────────────────────────

class TestManualOrdersAreProtected:
    """`positions.register` used to have exactly ONE call site — the auto-exec path.
    An order placed by hand from the signal board got no registry entry, no broker
    stop, no tick monitor and no expiry square-off, while the board went on showing
    it an SL, a TSL and a Target. The display was the dangerous part."""

    @staticmethod
    def _board_row(symbol="BANKNIFTY26AUG57000CE", *, stop=255.0, target=540.0):
        from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow, OptionLeg
        leg = OptionLeg(
            moneyness="ATM", option_type="CE", option_symbol=symbol, strike=57_000.0,
            expiry="2026-08-25", lot_size=35, token=9_001, premium_spot=320.0,
            entry_sl=210.0, premium_sl=stop, premium_target=target, is_active=True)
        return EngineSignalRow(
            underlying="NIFTY BANK", token=260_105, exchange="NFO", regime="BULL",
            alignment=AlignmentChip(fast=1, mid=1, slow=1), direction="long",
            option_type="CE", legs=[leg], spot=57_100.0, underlying_spot=57_100.0,
            stop_loss=56_900.0, score=85.0, timestamp_ms=1_785_404_700_000,
            is_active=True, is_fresh=True, source="spot")

    @pytest.fixture()
    def _wired(self, monkeypatch):
        """A live account + warm client + one row on the board."""
        from app.services.exchanges.kite import accounts as kite_accounts
        from app.services.kite_engine import service as ksvc
        from app.services.kite_engine.scanner import scanner

        client = _FakeClient()

        class _Acct:
            user_id, id, is_paper, connected = "m-user", 1, False, True

        async def _order(symbol, side, qty, **kw):
            client.calls.append(f"entry:{side}")
            return {"order_id": "ENTRY-9"}

        client.place_order_option_entry = _order
        monkeypatch.setattr(kite_accounts, "get_active", lambda uid: _Acct())
        monkeypatch.setattr(kite_accounts, "acquire_client", lambda acct: _async(client))
        monkeypatch.setattr(ksvc.live_safety, "assert_safe_to_trade",
                            lambda **kw: type("D", (), {"allowed": True, "code": "", "reason": ""})())
        monkeypatch.setattr(ksvc.live_safety, "check_idempotency", lambda key: None)
        monkeypatch.setattr(ksvc.live_safety, "record_idempotency", lambda key, oid: None)
        pos.reset("m-user")
        scanner.snapshot("m-user").rows = [self._board_row()]
        yield client
        scanner._users.pop("m-user", None)

    @pytest.mark.asyncio
    async def test_a_manual_buy_is_registered_and_armed_from_the_boards_plan(self, _wired):
        from app.services.kite_engine import service as ksvc

        res = await ksvc.place_manual_order(
            "m-user", "BANKNIFTY26AUG57000CE", "BUY", 35, exchange="NFO")

        assert res["status"] == "ok"
        assert res["protected"] is True
        held = pos.get("m-user", "BANKNIFTY26AUG57000CE")
        assert held is not None, "a hand-placed order still went unregistered"
        assert held.stop_premium == pytest.approx(255.0), "stop must be the board's own TSL"
        assert held.target_premium == pytest.approx(540.0)
        # and it went to the broker as one OCO carrying both levels
        assert _wired.gtts[0]["trigger_type"] == "two-leg"
        assert _wired.gtts[0]["trigger_values"] == [255.0, 540.0]

    @pytest.mark.asyncio
    async def test_a_contract_not_on_the_board_is_reported_unprotected_not_blocked(self, _wired):
        from app.services.kite_engine import service as ksvc

        res = await ksvc.place_manual_order(
            "m-user", "BANKNIFTY26AUG99000CE", "BUY", 35, exchange="NFO")

        assert res["status"] == "ok", "never block a trade the user asked for"
        assert res["protected"] is False
        assert "no stop to arm" in res["protection"]
        assert _wired.gtts == []

    @pytest.mark.asyncio
    async def test_a_leg_with_no_premium_stop_is_reported_unprotected(self, _wired, monkeypatch):
        from app.services.kite_engine import service as ksvc
        from app.services.kite_engine.scanner import scanner

        scanner.snapshot("m-user").rows = [self._board_row(stop=0.0, target=0.0)]
        # entry_sl is the fallback, so null that too by rebuilding the leg
        scanner.snapshot("m-user").rows[0].legs[0].entry_sl = None

        res = await ksvc.place_manual_order(
            "m-user", "BANKNIFTY26AUG57000CE", "BUY", 35, exchange="NFO")

        assert res["status"] == "ok" and res["protected"] is False
        assert "no premium stop" in res["protection"]

    @pytest.mark.asyncio
    async def test_the_toggle_off_leaves_manual_orders_alone(self, _wired, monkeypatch):
        from app.services.kite_engine import service as ksvc

        cfg = ksvc.state.get_config("m-user")
        monkeypatch.setattr(ksvc.state, "get_config",
                            lambda uid: cfg.model_copy(update={"protect_manual_orders": False}))

        res = await ksvc.place_manual_order(
            "m-user", "BANKNIFTY26AUG57000CE", "BUY", 35, exchange="NFO")

        assert res["protected"] is False
        assert "switched off" in res["protection"]
        assert pos.get("m-user", "BANKNIFTY26AUG57000CE") is None

    @pytest.mark.asyncio
    async def test_a_manual_sell_of_a_held_position_goes_through_the_exit_path(self, _wired):
        """One SELL, one close, one realized PnL — and it takes the same `_exiting`
        claim an automatic exit takes, so the two can never both sell."""
        from app.services.kite_engine import service as ksvc

        pos.register(pos.OpenPosition(
            uid="m-user", symbol="BANKNIFTY26AUG57000CE", exchange="NFO", token=9_001,
            qty=35, lot_size=35, entry_premium=320.0, stop_premium=255.0,
            order_id="ENTRY-1", status=pos.OPEN, gtt_id=555))

        res = await ksvc.place_manual_order(
            "m-user", "BANKNIFTY26AUG57000CE", "SELL", 35, exchange="NFO")

        assert res["status"] == "ok"
        held = pos.get("m-user", "BANKNIFTY26AUG57000CE")
        assert held.status == pos.CLOSED
        assert "manual exit" in held.exit_reason
        assert _wired.sells == [("BANKNIFTY26AUG57000CE", "sell", 35)]
        assert _wired.cancelled == [555], "the broker stop must not outlive the position"


def _async(value):
    async def _wrap(*a, **kw):
        return value
    return _wrap()
