"""Tick-driven runner: intent execution, gating and the no-double-order lock."""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, InstrumentRef, OptionPairRef,
    OrderReport, OrderStatus,
)
import app.services.atm_premium_imbalance_runner as R

IST = timezone(timedelta(hours=5, minutes=30))


class FakeBroker(R.BrokerPort):
    def __init__(self, entry_fill=133.40, exit_fill=156.85, fail_place=False, fail_cancel=False):
        self.entry_fill, self.exit_fill = entry_fill, exit_fill
        self.fail_place, self.fail_cancel = fail_place, fail_cancel
        self.placed, self.cancelled = [], []
        self._n = 0

    async def place(self, *, instrument_id, side, quantity, limit_price, tag):
        if self.fail_place:
            return None, "broker down"
        self._n += 1
        oid = f"O{self._n}"
        self.placed.append({"id": oid, "side": side, "qty": quantity,
                            "price": limit_price, "tag": tag})
        return oid, None

    async def status(self, order_id):
        rec = next((p for p in self.placed if p["id"] == order_id), None)
        if rec is None:
            return None
        px = self.entry_fill if rec["side"] == "BUY" else self.exit_fill
        return OrderReport(order_id=order_id, status=OrderStatus.COMPLETE,
                           transaction=rec["side"], average_price=px,
                           filled_quantity=rec["qty"])

    async def cancel(self, order_id):
        if self.fail_cancel:
            return False
        self.cancelled.append(order_id)
        return True


def _pair():
    def leg(ot, token):
        return InstrumentRef(instrument_id=token, tradingsymbol=f"SENSEX77600{ot}",
                             option_type=ot, strike=77600.0, expiry="2026-07-30",
                             lot_size=20, tick_size=0.05, upper_circuit=1745.45)
    return OptionPairRef(underlying="SENSEX", expiry="2026-07-30", strike=77600.0,
                         ce=leg("CE", "111"), pe=leg("PE", "222"))


def _session(protection_mode="NONE", quantity=20):
    pair = _pair()
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=quantity,
                                    protection_mode=protection_mode).validate()
    strat = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=quantity, trade_id="t")
    return R.Session(user_id="u1", cfg=cfg, pair=pair, strategy=strat,
                     session_date=datetime.now(IST).date(), ce_token=111, pe_token=222)


def tick(token, ltp, bid, ask):
    return {"instrument_token": token, "last_price": ltp,
            "depth": {"buy": [{"price": bid, "quantity": 100}],
                      "sell": [{"price": ask, "quantity": 100}]}}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    R.clear()
    monkeypatch.setattr(R, "_is_market_open", lambda: True)
    yield
    R.clear()


# ------------------------------------------------------------- gating

@pytest.mark.asyncio
async def test_no_session_is_inactive():
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "inactive"


@pytest.mark.asyncio
async def test_market_closed_is_refused(monkeypatch):
    R.register(_session())
    monkeypatch.setattr(R, "_is_market_open", lambda: False)
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "market_closed"


@pytest.mark.asyncio
async def test_a_stale_session_date_is_dropped():
    s = _session()
    s.session_date = datetime.now(IST).date() - timedelta(days=1)
    R.register(s)
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "session_rolled"
    assert R.active_session("u1") is None


@pytest.mark.asyncio
async def test_no_broker_means_no_orders():
    R.register(_session())
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], None) == "no_broker"


@pytest.mark.asyncio
async def test_foreign_tokens_are_ignored():
    s = _session(); R.register(s)
    b = FakeBroker()
    await R.on_ticks("u1", [tick(999, 50.0, 49.5, 50.5)], b)
    assert b.placed == []
    assert s.strategy.phase.value == "idle"


# ------------------------------------------------------- full lifecycle

@pytest.mark.asyncio
async def test_end_to_end_entry_and_exit_without_protection():
    s = _session(); R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=156.85)

    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    assert s.strategy.trade.entry_price == 133.40
    assert s.strategy.trade.target_price == 148.40
    buys = [p for p in b.placed if p["side"] == "BUY"]
    assert len(buys) == 1 and buys[0]["price"] == 168.00     # ask 167.50 + 0.50

    out = await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    assert out == "complete"
    sells = [p for p in b.placed if p["side"] == "SELL"]
    assert len(sells) == 1 and sells[0]["price"] == 148.70   # bid 149.2 - 0.50
    assert s.strategy.trade.points == 23.45
    assert s.strategy.trade.pnl == 469.0
    assert s.finished is True


@pytest.mark.asyncio
async def test_protection_is_placed_then_cancelled_before_the_exit():
    s = _session(protection_mode="RESTING_TARGET_LIMIT"); R.register(s)
    b = FakeBroker()

    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    protect = [p for p in b.placed if p["tag"] == "api-protect"]
    assert len(protect) == 1
    assert protect[0]["price"] == 148.40 and protect[0]["side"] == "SELL"

    await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    # the resting sell was cancelled before our own sell went out
    assert b.cancelled == [protect[0]["id"]]
    exits = [p for p in b.placed if p["tag"] == "api-exit"]
    assert len(exits) == 1
    assert s.strategy.trade.points == 23.45


@pytest.mark.asyncio
async def test_a_failed_protection_cancel_halts_before_sending_a_second_sell():
    s = _session(protection_mode="RESTING_TARGET_LIMIT"); R.register(s)
    b = FakeBroker(fail_cancel=True)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    out = await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    assert out.startswith("halt:")
    assert [p for p in b.placed if p["tag"] == "api-exit"] == []


@pytest.mark.asyncio
async def test_one_trade_per_session_then_inactive():
    s = _session(); R.register(s)
    b = FakeBroker()
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    n = len(b.placed)
    assert await R.on_ticks("u1", [tick(111, 200.0, 199.5, 200.5)], b) == "inactive"
    assert len(b.placed) == n


@pytest.mark.asyncio
async def test_a_dead_broker_does_not_open_a_position():
    s = _session(); R.register(s)
    b = FakeBroker(fail_place=True)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    assert s.strategy.trade.entry_price is None
    assert b.placed == []


@pytest.mark.asyncio
async def test_concurrent_ticks_cannot_start_a_second_order():
    """The lock is the guard against a tick arriving mid-order."""
    import asyncio
    s = _session(); R.register(s)
    b = FakeBroker()
    lock = R._lock_for("u1")
    await lock.acquire()
    try:
        assert await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50)], b) == "busy"
        assert b.placed == []
    finally:
        lock.release()


# ------------------------------------------------------ tick normalisation

def test_tick_normalisation_keeps_depth_and_both_timestamps():
    q = R._tick_to_quote("BSE_FO|1", tick(111, 167.50, 167.0, 167.9), now_ms=1234)
    assert (q.ltp, q.bid, q.ask) == (167.50, 167.0, 167.9)
    assert q.received_ts_ms == 1234
    assert q.source == "kite_ticker"


def test_missing_depth_yields_no_bid_or_ask_rather_than_ltp():
    """Synthesising depth from the last trade would change entry and exit prices."""
    q = R._tick_to_quote("BSE_FO|1", {"instrument_token": 111, "last_price": 167.5}, now_ms=1)
    assert q.ltp == 167.5
    assert q.bid is None and q.ask is None


# --------------------------------------------- timestamp handling (defect 1)

SESSION_OPEN = datetime(2026, 8, 21, 9, 15, tzinfo=IST)
SESSION_OPEN_MS = int(SESSION_OPEN.timestamp() * 1000)
PRIOR_TRADE = datetime(2026, 8, 20, 15, 33, tzinfo=IST)
PRIOR_TRADE_MS = int(PRIOR_TRADE.timestamp() * 1000)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        (0, None),
        (SESSION_OPEN, SESSION_OPEN_MS),                       # datetime
        (int(SESSION_OPEN.timestamp()), SESSION_OPEN_MS),      # epoch SECONDS (Kite binary)
        (SESSION_OPEN_MS, SESSION_OPEN_MS),                    # already ms
        ("nonsense", None),
    ],
)
def test_epoch_normalisation_accepts_every_form_kite_sends(raw, expected):
    assert R._epoch_ms(raw) == expected


def test_the_trade_clock_is_never_substituted_with_receipt_time():
    """The defect: epoch-seconds ints failed an isinstance(datetime) check and the
    receipt time was written into the exchange stamp, destroying the evidence."""
    tick = {"instrument_token": 111, "last_price": 379.0,
            "last_trade_time": int(PRIOR_TRADE.timestamp()),
            "exchange_timestamp": int(SESSION_OPEN.timestamp()),
            "ohlc": {"open": 356.7, "high": 356.7, "low": 318.0, "close": 366.6},
            "volume_traded": 0}
    q = R._tick_to_quote("212614405", tick, now_ms=SESSION_OPEN_MS)
    assert q.last_trade_ts_ms == PRIOR_TRADE_MS        # preserved, not overwritten
    assert q.exchange_ts_ms == SESSION_OPEN_MS
    assert q.received_ts_ms == SESSION_OPEN_MS
    assert q.official_open == 356.7
    assert q.prev_close == 366.6
    # and the quote dates itself correctly
    assert q.is_session_origin(SESSION_OPEN_MS) is False


def test_a_tick_with_no_trade_stamp_reports_unknown_not_fresh():
    q = R._tick_to_quote("212614405", {"instrument_token": 111, "last_price": 356.7},
                         now_ms=SESSION_OPEN_MS)
    assert q.last_trade_ts_ms is None
    assert q.is_session_origin(SESSION_OPEN_MS) is None


# ------------------------------------- end to end: the stale tick is refused

def _pin_clock(monkeypatch, at_ms):
    monkeypatch.setattr(R, "_now_ms", lambda: at_ms)


def _session_on(monkeypatch, at_ms, **kw):
    """A session registered for the same day the clock is pinned to.

    The day-rollover check reads the session's own clock, so a fixture pinned to
    2026-08-21 with a session dated today would correctly be treated as rolled
    over — which is a broken fixture, not a finding.
    """
    _pin_clock(monkeypatch, at_ms)
    s = _session(**kw)
    s.session_date = datetime.fromtimestamp(at_ms / 1000, tz=IST).date()
    R.register(s)
    return s


def full_tick(token, ltp, bid, ask, *, traded_at, official_open=356.7, volume=222120):
    return {"instrument_token": token, "last_price": ltp,
            "last_trade_time": int(traded_at.timestamp()),
            "exchange_timestamp": int(traded_at.timestamp()),
            "ohlc": {"open": official_open, "high": 545.6, "low": 318.0, "close": 366.6},
            "volume_traded": volume,
            "depth": {"buy": [{"price": bid, "quantity": 100}],
                      "sell": [{"price": ask, "quantity": 100}]}}


@pytest.mark.asyncio
async def test_a_previous_session_price_places_no_order(monkeypatch):
    """The real 2026-08-21 fault, driven through the runner."""
    s = _session_on(monkeypatch, SESSION_OPEN_MS + 1000)
    b = FakeBroker()
    out = await R.on_ticks("u1", [
        full_tick(111, 500.00, 499.5, 500.5, traded_at=PRIOR_TRADE),
        full_tick(222, 379.00, 378.5, 379.5, traded_at=PRIOR_TRADE),
    ], b)
    assert out == "idle"
    assert b.placed == []                              # nothing was sent
    assert s.strategy.trade is None


@pytest.mark.asyncio
async def test_a_session_price_prices_off_the_real_open(monkeypatch):
    """Same instant, same legs, but stamped inside the session.

    356.70 x 1.10 = 392.37 -> 392.4, against the 416.90 the stale tick produced.
    """
    s = _session_on(monkeypatch, SESSION_OPEN_MS + 1000, quantity=80)
    s.strategy.cfg = ATMPremiumImbalanceConfig(
        # 80 x ~392 is above the Rs25,000 default risk ceiling; the recorded size
        # is the fixture, so the ceiling is stated rather than the trade shrunk.
        enabled=True, quantity=80, entry_price_policy="FIRST_TICK_PERCENT",
        entry_through_pct=0.10, max_premium_at_risk_inr=40000.0).validate()
    b = FakeBroker(entry_fill=340.10, exit_fill=400.0)
    traded = SESSION_OPEN + timedelta(milliseconds=900)
    await R.on_ticks("u1", [
        full_tick(111, 500.00, 499.5, 500.5, traded_at=traded),
        full_tick(222, 356.70, 356.2, 357.2, traded_at=traded),
    ], b)
    buys = [p for p in b.placed if p["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["price"] == 392.40
    assert s.strategy.trade.option_type == "PE"        # 356.70 < 500.00


# ------------------------------------------- releasing the tick subscriptions

class FakeTM:
    """Records release/subscribe calls the way ticker_manager would act on them."""

    def __init__(self):
        self.released: list[tuple[list[int], str]] = []
        self.subscribed: list[tuple[list[int], str, str | None]] = []

    async def release(self, user_id, tokens, owner):
        self.released.append(([int(t) for t in tokens], owner))
        return {"ok": True, "unsubscribed": [int(t) for t in tokens]}

    async def subscribe(self, user_id, tokens, mode="quote", owner=None):
        self.subscribed.append(([int(t) for t in tokens], mode, owner))
        return {"ok": True}


@pytest.fixture
def fake_tm(monkeypatch):
    tm = FakeTM()
    import app.services.exchanges.kite as kite_pkg
    monkeypatch.setattr(kite_pkg, "ticker_manager", tm, raising=False)
    return tm


@pytest.mark.asyncio
async def test_completing_a_trade_gives_the_legs_back(fake_tm):
    """A finished session must not keep two tokens of the shared set forever."""
    s = _session(); R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=156.85)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    assert await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b) == "complete"
    assert fake_tm.released == [([111, 222], R.TICKER_OWNER)]


@pytest.mark.asyncio
async def test_release_happens_once_however_often_it_is_asked(fake_tm):
    sess = _session()
    await R.release_subscriptions(sess)
    await R.release_subscriptions(sess)
    assert len(fake_tm.released) == 1
    assert sess.released is True


@pytest.mark.asyncio
async def test_a_rolled_over_session_releases_before_it_is_discarded(fake_tm):
    """The session holds the only record of which tokens were ours.

    Dropping it first leaked both legs until the backend restarted.
    """
    from datetime import date
    sess = _session()
    sess.session_date = date(2020, 1, 1)
    R.register(sess)

    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "session_rolled"
    assert fake_tm.released == [([111, 222], R.TICKER_OWNER)]
    assert R.active_session("u1") is None


@pytest.mark.asyncio
async def test_a_failing_release_never_breaks_the_tick_loop(monkeypatch):
    class Boom:
        async def release(self, *a, **k):
            raise RuntimeError("socket gone")

    import app.services.exchanges.kite as kite_pkg
    monkeypatch.setattr(kite_pkg, "ticker_manager", Boom(), raising=False)
    sess = _session()
    await R.release_subscriptions(sess)          # must not raise
    assert sess.released is True


@pytest.mark.asyncio
async def test_a_halt_also_gives_the_legs_back(fake_tm):
    """A halted session is finished too -- it must not hold the legs either."""
    s = _session(protection_mode="RESTING_TARGET_LIMIT"); R.register(s)
    b = FakeBroker(fail_cancel=True)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    assert (await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)).startswith("halt:")
    assert fake_tm.released == [([111, 222], R.TICKER_OWNER)]


def _pair_at(strike, ce_token, pe_token):
    def leg(ot, token):
        return InstrumentRef(instrument_id=token, tradingsymbol=f"SENSEX{int(strike)}{ot}",
                             option_type=ot, strike=float(strike), expiry="2026-07-30",
                             lot_size=20, tick_size=0.05, upper_circuit=1745.45)
    return OptionPairRef(underlying="SENSEX", expiry="2026-07-30", strike=float(strike),
                         ce=leg("CE", ce_token), pe=leg("PE", pe_token))


@pytest.fixture
def arming(monkeypatch):
    """arm() with the config and pair resolution stubbed, market open."""
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=20).validate()
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)
    monkeypatch.setattr(R, "_is_market_open", lambda: True)
    box = {"pair": _pair_at(77600, "111", "222")}

    async def resolve(user_id, c):
        return box["pair"]

    monkeypatch.setattr(svc, "resolve_option_pair", resolve, raising=False)
    return box


@pytest.mark.asyncio
async def test_arming_claims_the_legs_for_this_strategy(fake_tm, arming):
    out = await R.arm("u1")
    assert out["status"] == "armed"
    assert fake_tm.subscribed == [([111, 222], "full", R.TICKER_OWNER)]


@pytest.mark.asyncio
async def test_re_arming_on_a_new_strike_gives_back_only_the_old_legs(fake_tm, arming):
    await R.arm("u1")
    R.active_session("u1").finished = True          # yesterday's trade is done

    arming["pair"] = _pair_at(77700, "333", "444")
    assert (await R.arm("u1"))["status"] == "armed"

    assert fake_tm.released == [([111, 222], R.TICKER_OWNER)]
    assert fake_tm.subscribed[-1] == ([333, 444], "full", R.TICKER_OWNER)


@pytest.mark.asyncio
async def test_re_arming_never_releases_a_leg_the_new_pair_reuses(fake_tm, arming):
    """One owner tag per strategy, so releasing a carried-over token would
    revoke the claim the *new* session depends on."""
    await R.arm("u1")
    R.active_session("u1").finished = True

    arming["pair"] = _pair_at(77600, "111", "999")   # CE carried over, PE moved
    assert (await R.arm("u1"))["status"] == "armed"

    assert fake_tm.released == [([222], R.TICKER_OWNER)]


@pytest.mark.asyncio
async def test_a_replaced_session_cannot_later_yank_the_live_legs(fake_tm, arming):
    """The outgoing session is marked released, so a stray release is a no-op."""
    await R.arm("u1")
    stale = R.active_session("u1")
    stale.finished = True
    arming["pair"] = _pair_at(77600, "111", "222")   # same pair, re-armed
    await R.arm("u1")

    fake_tm.released.clear()
    await R.release_subscriptions(stale)
    assert fake_tm.released == []


@pytest.mark.asyncio
async def test_a_live_session_is_not_re_armed(fake_tm, arming):
    await R.arm("u1")
    assert (await R.arm("u1"))["status"] == "already_armed"
    assert len(fake_tm.subscribed) == 1
    assert fake_tm.released == []


@pytest.mark.asyncio
async def test_refusals_claim_nothing(fake_tm, arming, monkeypatch):
    """A refusal must not subscribe: no quantity, no claim."""
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=0)
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)
    assert (await R.arm("u1"))["status"] == "no_quantity"
    assert fake_tm.subscribed == []


@pytest.mark.asyncio
async def test_a_fraction_of_a_lot_is_refused_before_the_open(fake_tm, arming, monkeypatch):
    """The broker would reject this, and it would reject it at the open."""
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=5).validate()   # lot is 20
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)

    out = await R.arm("u1")
    assert out["status"] == "invalid_size"
    assert "lot size 20" in out["message"]
    assert "use 20" in out["message"]          # and it names a size that works
    assert fake_tm.subscribed == []          # a refusal claims nothing
    assert R.active_session("u1") is None


@pytest.mark.asyncio
async def test_whole_lots_are_accepted(fake_tm, arming, monkeypatch):
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=40).validate()
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)
    assert (await R.arm("u1"))["status"] == "armed"


@pytest.mark.asyncio
async def test_lots_mode_multiplies_by_the_contract_lot_size(fake_tm, arming, monkeypatch):
    """Saying "2 lots" must order 40 -- the operator should not have to know 20."""
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, sizing_mode="LOTS", lots=2).validate()
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)

    out = await R.arm("u1")
    assert out["status"] == "armed"
    assert out["quantity"] == 40 and out["lots"] == 2
    assert R.active_session("u1").strategy.quantity == 40


@pytest.mark.asyncio
async def test_lots_mode_still_refuses_an_unset_size(fake_tm, arming, monkeypatch):
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, sizing_mode="LOTS", lots=0).validate()
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)
    assert (await R.arm("u1"))["status"] == "no_quantity"


@pytest.mark.asyncio
async def test_lots_mode_respects_the_quantity_cap(fake_tm, arming, monkeypatch):
    """The cap is in quantity, so lots have to be converted before comparing."""
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, sizing_mode="LOTS", lots=100,
                                    max_quantity=500).validate()
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)
    out = await R.arm("u1")
    assert out["status"] == "invalid_size"
    assert "exceeds the cap of 500" in out["message"]
